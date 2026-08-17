"""Фаза 1 прогона: очереди, потребители, обход репозиториев (часть 2, D1).

Вынесена из `ScanOrchestrator` (ТЗ T-13 допускает это явно): оркестратор отвечает
за фазы 0/2/3 и за связывание, а здесь живёт единственная сложная механика прогона —
порядок завершения двух стадий. Он написан ровно один раз и повторяет D1 дословно:

```text
END_DISCOVERY × workers.parse → TaskQueue.join() → parse-worker.join() × N
→ END_RESULTS → ResultQueue.join() → collector.join()
```

Ни один шаг переставить нельзя: ранний сентинел = тихая потеря результатов
(инварианты 3–5, 18–19). Завершение — **только** по сентинелам; `qsize()` служит
исключительно строке прогресса.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..checking.checker_factory import CheckerFactory
from ..config.scan_config import ScanConfig
from ..discovery.markdown_file_finder import MarkdownFileFinder
from ..discovery.nested_repo_finder import NestedRepoFinder
from ..discovery.processed_registry import ProcessedRegistry
from ..models.md_file_result import MdFileResult
from ..models.md_task import MdTask
from ..models.progress_snapshot import ProgressSnapshot
from ..models.repo_info import RepoInfo
from ..parsing.link_classifier import LinkClassifier
from ..parsing.markdown_it_link_extractor import MarkdownItLinkExtractor
from ..parsing.markdown_reader import MarkdownReader
from ..source.git_adapter import GitAdapter
from ..source.repository_source import RepositorySource
from .collecting_observer import CollectingObserver
from .markdown_worker import MarkdownWorker
from .notifier import Notifier
from .queues import ResultQueue, TaskQueue
from .sentinels import END_DISCOVERY, END_RESULTS
from .statistics_collector import StatisticsCollector

logger = logging.getLogger("core.mdscan.runtime.orchestrator")

#: Сколько ждать поток-потребитель при гашении: `join()` без таймаута вешает прогон.
JOIN_TIMEOUT_SEC = 60.0

#: Префикс имён потоков обхода — он же идёт в лог (D2.1) и в проверку «наших потоков нет».
DISCOVER_PREFIX = "discover"


class PipelineRunner:
    """Двухстадийный конвейер одного прогона: обход → разбор → сбор.

    Все потоки создаются здесь и здесь же гасятся; наружу отдаются только
    результаты (`results`), счётчики (`stats`) и срез для прогресса (`snapshot`).
    """

    def __init__(self, config: ScanConfig, notifier: Notifier, checkers: CheckerFactory) -> None:
        self._config = config
        self._tasks: TaskQueue = queue.Queue()
        self._results: ResultQueue = queue.Queue()
        self._stats = StatisticsCollector()
        self._registry = ProcessedRegistry()
        self._nested = NestedRepoFinder()
        self._finder = MarkdownFileFinder(
            GitAdapter(),
            config.scan.md_extensions,
            config.scan.respect_gitignore,
            config.scan.include_nested_repos,
        )
        self._collector = CollectingObserver(self._results, self._stats)
        self._workers = [
            MarkdownWorker(
                self._tasks,
                self._results,
                f"parse-{number}",
                MarkdownReader(),
                MarkdownItLinkExtractor(config.parser.preset, config.parser.plugins),
                LinkClassifier.default(),
                checkers,
                notifier,
            )
            for number in range(1, max(1, config.workers.parse) + 1)
        ]

    @property
    def stats(self) -> StatisticsCollector:
        """Счётчики прогона — источник чисел для отчёта, лога и метрик ДЗ."""
        return self._stats

    @property
    def results(self) -> list[MdFileResult]:
        """Собранные результаты; заполнены полностью только после `run()`."""
        return self._collector.results

    def snapshot(self) -> ProgressSnapshot:
        """Срез счётчиков для зоны 1 прогресса (`qsize` — только для показа)."""
        return self._stats.snapshot(self._tasks.qsize(), self._results.qsize())

    def start(self) -> None:
        """Поднять потребителей: сначала сборщик, затем parse-worker'ы (D4)."""
        self._collector.start()
        for worker in self._workers:
            worker.start()
        logger.info("конвейер запущен: parse-worker'ов %d", len(self._workers))

    def run(self, sources: Sequence[RepositorySource]) -> None:
        """Обойти источники и довести конвейер до полной остановки.

        Гашение — в `finally`: даже если обход упал (нет git, сорвалось раскрытие
        организации), потоки обязаны выйти по сентинелам, иначе прогон повиснет.
        """
        try:
            self._discover(sources)
        finally:
            self._drain()

    def _discover(self, sources: Sequence[RepositorySource]) -> None:
        """Стадия 1: пул обхода; `future.result()` у каждого — иначе ошибка исчезнет молча."""
        workers = max(1, self._config.workers.discover)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=DISCOVER_PREFIX) as pool:
            futures = [pool.submit(self._scan_source, source) for source in sources]
            for future in futures:
                future.result()

    def _scan_source(self, source: RepositorySource) -> None:
        """Один источник: каждый его репозиторий ставится в задачи отдельно."""
        for repo in source.repositories():
            self._scan_repo(repo)

    def _scan_repo(self, repo: RepoInfo) -> None:
        """Репозиторий и найденные под ним вложенные; ошибка одного не роняет остальные."""
        pending = [repo]
        while pending:
            current = pending.pop()
            self._stats.add_repo(current.is_nested)
            try:
                pending.extend(self._queue_files(current))
            except Exception:  # noqa: BLE001 — репозиторий пропускаем, прогон продолжается (D2.1)
                logger.exception("репозиторий пропущен из-за ошибки: %s", current.root)
            finally:
                self._stats.repo_done()

    def _queue_files(self, repo: RepoInfo) -> list[RepoInfo]:
        """Поставить `.md` репозитория в очередь; вернуть вложенные репозитории.

        Вложенные ищутся только при `scan.include_nested_repos` — тогда их файлы
        разбираются как отдельные `RepoInfo`, а главному не отдаются (инвариант 6).
        """
        nested = self._nested.find(repo.root) if self._config.scan.include_nested_repos else []
        queued = 0
        for md_file in self._finder.find(repo, list(nested)):
            if not self._registry.add_if_absent((repo.root, md_file)):
                continue
            self._stats.md_found()
            self._tasks.put(MdTask(repo=repo, md_file=md_file))
            queued += 1
        logger.info("репозиторий %s: задач %d, вложенных %d", repo.root, queued, len(nested))
        return [RepoInfo(root=Path(root), is_nested=True) for root in nested]

    def _drain(self) -> None:
        """Порядок завершения D1 — переставлять шаги нельзя (инварианты 3–5)."""
        for _ in self._workers:
            self._tasks.put(END_DISCOVERY)
        self._tasks.join()
        for worker in self._workers:
            self._join(worker)
        self._results.put(END_RESULTS)
        self._results.join()
        self._join(self._collector)
        logger.info("конвейер остановлен: результатов %d", len(self.results))

    @staticmethod
    def _join(thread: threading.Thread) -> None:
        """`join` с таймаутом: зависший поток даёт `ERROR`, а не вечное ожидание (D4)."""
        thread.join(timeout=JOIN_TIMEOUT_SEC)
        if thread.is_alive():
            logger.error("поток %s не завершился за %.0f с", thread.name, JOIN_TIMEOUT_SEC)
