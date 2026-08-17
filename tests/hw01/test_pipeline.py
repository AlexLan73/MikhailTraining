"""Тесты конвейера (T-10): очереди, сентинелы, worker, наблюдатель.

Свойства, которые здесь доказываются, — это те, из-за которых конвейеры виснут и
тихо теряют данные (инварианты 2–5, 7, 11, 14, 18–20, 25):

- ничего не потеряно: N задач → N результатов;
- на каждый `get()` есть `task_done()`, включая сентинел и ошибочную ветку;
- ошибка одного файла публикуется событием и не роняет прогон;
- после `put()` объект-владелец не изменяется;
- после завершения наших потоков в процессе не остаётся.

Реальные markdown-it, диск и сеть не нужны: все чужие контракты — заглушки
(duck typing, без наследования, §3.3). Любой `join()` — с таймаутом, `sleep`
для синхронизации нет: ожидание только через `Event` (§3.2).
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.errors import MarkdownReadError
from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.md_task import MdTask
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.runtime.collecting_observer import CollectingObserver
from core.mdscan.runtime.markdown_worker import MarkdownWorker
from core.mdscan.runtime.queues import ResultQueue, TaskQueue
from core.mdscan.runtime.sentinels import END_DISCOVERY, END_RESULTS, _Sentinel
from core.mdscan.runtime.statistics_collector import StatisticsCollector

#: Запас на любое ожидание в тестах: тест обязан падать, а не висеть (§3.3).
_TIMEOUT_SEC = 30.0


# --------------------------------------------------------------------------
# заглушки чужих контрактов
# --------------------------------------------------------------------------


class _Reader:
    """Заглушка `MarkdownReader`: текст из имени файла, перечисленные — с ошибкой чтения."""

    def __init__(self, broken: frozenset[str] = frozenset()) -> None:
        self._broken = broken

    def read(self, path: Path) -> str:
        if path.name in self._broken:
            raise MarkdownReadError(f"{path}: не UTF-8 — байт 0xff в позиции 0")
        return f"# {path.stem}\n"


class _Extractor:
    """Заглушка `LinkExtractor`: фиксированное число ссылок на файл."""

    def __init__(self, links_per_file: int = 2) -> None:
        self._count = links_per_file

    def extract(self, text: str) -> tuple[MdLink, ...]:
        return tuple(
            MdLink(target=f"docs/a{index}.md", origin=LinkOrigin.INLINE, line=index + 1)
            for index in range(self._count)
        )


class _Classifier:
    """Заглушка `LinkClassifier`: одна категория на все ссылки."""

    def __init__(self, kind: LinkKind = LinkKind.LOCAL) -> None:
        self._kind = kind

    def classify(self, link: MdLink) -> LinkKind:
        return self._kind


class _Checker:
    """Заглушка `LinkChecker`: ставит статус, умеет ждать `Event` и падать."""

    def __init__(
        self,
        status: CheckStatus = CheckStatus.OK,
        gate: threading.Event | None = None,
        boom: bool = False,
    ) -> None:
        self._status = status
        self._gate = gate
        self._boom = boom

    def check(self, link: MdLink, md_file: Path) -> None:
        if self._gate is not None:
            assert self._gate.wait(timeout=_TIMEOUT_SEC), "чекер не дождался разрешения"
        if self._boom:
            raise RuntimeError("чекер упал на ссылке")
        link.status = self._status


class _Checkers:
    """Заглушка `CheckerFactory`: один общий чекер на любую категорию."""

    def __init__(self, checker: _Checker) -> None:
        self._checker = checker

    def for_kind(self, kind: LinkKind) -> _Checker:
        return self._checker


class _Notifier:
    """Заглушка `Notifier`: копит строки зоны 2."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self._lock = threading.Lock()

    def show(self, text: str) -> None:
        with self._lock:
            self.messages.append(text)


class _RecordingStats:
    """Заглушка `StatisticsCollector`: запоминает состояние результата в момент приёма."""

    def __init__(self) -> None:
        self.seen: list[tuple[int, tuple[object, ...]]] = []

    def add(self, result: MdFileResult) -> None:
        self.seen.append((id(result), _state(result)))


class _CountingQueue(queue.Queue):  # type: ignore[type-arg]
    """`TaskQueue` со счётчиками `get()`/`task_done()` — для инвариантов 5 и 18–19."""

    def __init__(self) -> None:
        super().__init__()
        self.gets = 0
        self.dones = 0
        self._counter_lock = threading.Lock()

    def get(self, block: bool = True, timeout: float | None = None) -> object:
        item = super().get(block, timeout)
        with self._counter_lock:
            self.gets += 1
        return item

    def task_done(self) -> None:
        super().task_done()
        with self._counter_lock:
            self.dones += 1


# --------------------------------------------------------------------------
# сборка конвейера
# --------------------------------------------------------------------------


@dataclass(slots=True)
class _Pipeline:
    """Собранный и запущенный конвейер: очереди, воркеры, сборщик."""

    tasks: TaskQueue
    results: ResultQueue
    workers: list[MarkdownWorker]
    collector: CollectingObserver
    stats: object
    notifier: _Notifier
    repo: RepoInfo
    threads: list[threading.Thread] = field(default_factory=list)


def _state(result: MdFileResult) -> tuple[object, ...]:
    """Полное состояние результата — для проверки «после `put()` не изменялся»."""
    links = tuple((link.target, link.kind, link.status, link.detail) for link in result.links)
    return (result.rel_path, result.error, result.seconds, result.thread_name, links)


def _build(
    tmp_path: Path,
    *,
    workers: int = 2,
    reader: _Reader | None = None,
    extractor: _Extractor | None = None,
    checker: _Checker | None = None,
    stats: object | None = None,
    tasks: TaskQueue | None = None,
) -> _Pipeline:
    """Запускает сборщик и `workers` воркеров; возвращает всё нужное тесту."""
    task_queue: TaskQueue = tasks if tasks is not None else queue.Queue()
    result_queue: ResultQueue = queue.Queue()
    statistics = stats if stats is not None else StatisticsCollector()
    notifier = _Notifier()
    collector = CollectingObserver(result_queue, statistics)  # type: ignore[arg-type]
    parse_workers = [
        MarkdownWorker(
            tasks=task_queue,
            results=result_queue,
            name=f"parse-{index + 1}",
            reader=reader or _Reader(),  # type: ignore[arg-type]
            extractor=extractor or _Extractor(),  # type: ignore[arg-type]
            classifier=_Classifier(),  # type: ignore[arg-type]
            checkers=_Checkers(checker or _Checker()),  # type: ignore[arg-type]
            notifier=notifier,
        )
        for index in range(workers)
    ]
    collector.start()
    for worker in parse_workers:
        worker.start()
    return _Pipeline(
        tasks=task_queue,
        results=result_queue,
        workers=parse_workers,
        collector=collector,
        stats=statistics,
        notifier=notifier,
        repo=RepoInfo(root=tmp_path),
        threads=[collector, *parse_workers],
    )


def _submit(pipe: _Pipeline, count: int, names: list[str] | None = None) -> list[MdTask]:
    """Кладёт задачи в `TaskQueue` (файлы на диске не нужны — чтение заглушено)."""
    files = names or [f"file{index}.md" for index in range(count)]
    tasks = [MdTask(repo=pipe.repo, md_file=pipe.repo.root / "docs" / name) for name in files]
    for task in tasks:
        pipe.tasks.put(task)
    return tasks


def _join_queue(q: queue.Queue, label: str) -> None:
    """`Queue.join()` без таймаута — ждём его в отдельном потоке, чтобы тест падал, а не висел."""
    waiter = threading.Thread(target=q.join, name=f"join-{label}", daemon=True)
    waiter.start()
    waiter.join(_TIMEOUT_SEC)
    assert not waiter.is_alive(), f"{label}.join() завис — потерян task_done()"


def _shutdown_tail(pipe: _Pipeline) -> None:
    """Хвост завершения после `TaskQueue.join()`: воркеры → END_RESULTS → сборщик."""
    for worker in pipe.workers:
        worker.join(_TIMEOUT_SEC)
        assert not worker.is_alive(), f"{worker.name} не вышел по сентинелу"
    pipe.results.put(END_RESULTS)
    _join_queue(pipe.results, "ResultQueue")
    pipe.collector.join(_TIMEOUT_SEC)
    assert not pipe.collector.is_alive(), "collector не вышел по сентинелу"


def _shutdown(pipe: _Pipeline) -> None:
    """Порядок завершения из D1: сентинелы по числу воркеров → join → END_RESULTS → join."""
    for _ in pipe.workers:
        pipe.tasks.put(END_DISCOVERY)
    _join_queue(pipe.tasks, "TaskQueue")
    _shutdown_tail(pipe)


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Корень «репозитория»: реальных файлов не создаём — чтение заглушено."""
    return tmp_path


# --------------------------------------------------------------------------
# тесты
# --------------------------------------------------------------------------


def test_all_tasks_produce_results(repo_root: Path) -> None:
    """1. N задач → ровно N результатов у наблюдателя: ничего не потеряно."""
    pipe = _build(repo_root, workers=3)
    tasks = _submit(pipe, 12)
    _shutdown(pipe)

    assert len(pipe.collector.results) == len(tasks)
    assert {result.rel_path for result in pipe.collector.results} == {
        f"docs/file{index}.md" for index in range(12)
    }
    assert all(result.ok for result in pipe.collector.results)
    assert len(pipe.notifier.messages) == 12


def test_slow_worker_result_not_lost(repo_root: Path) -> None:
    """2. Замедленный worker: сентинел не обогнал его результат."""
    gate = threading.Event()
    pipe = _build(repo_root, workers=3, checker=_Checker(gate=gate))
    _submit(pipe, 3)

    for _ in pipe.workers:  # сентинелы кладутся, пока воркеры ещё заняты проверкой ссылок
        pipe.tasks.put(END_DISCOVERY)
    assert pipe.collector.results == [], "результат опубликован раньше проверки ссылок"
    gate.set()

    _join_queue(pipe.tasks, "TaskQueue")
    _shutdown_tail(pipe)

    assert len(pipe.collector.results) == 3
    assert all(result.ok for result in pipe.collector.results)


def test_task_done_matches_get(repo_root: Path) -> None:
    """3. `task_done()` вызван столько же раз, сколько `get()`; ни один `join()` не виснет."""
    counting = _CountingQueue()
    pipe = _build(repo_root, workers=2, tasks=counting)  # type: ignore[arg-type]
    _submit(pipe, 7)
    _shutdown(pipe)

    assert counting.gets == counting.dones
    assert counting.gets == 7 + len(pipe.workers)  # задачи + по сентинелу на воркер


def test_read_error_published_and_others_processed(repo_root: Path) -> None:
    """4. Исключение при чтении одного файла → результат с `error`, остальные обработаны."""
    pipe = _build(repo_root, workers=2, reader=_Reader(broken=frozenset({"bad.md"})))
    _submit(pipe, 4, names=["a.md", "bad.md", "b.md", "c.md"])
    _shutdown(pipe)

    by_path = {result.rel_path: result for result in pipe.collector.results}
    assert len(by_path) == 4
    failed = by_path["docs/bad.md"]
    assert not failed.ok
    assert failed.error.startswith("MarkdownReadError:")
    assert all(by_path[name].ok for name in ("docs/a.md", "docs/b.md", "docs/c.md"))


def test_one_sentinel_per_worker_stops_all(repo_root: Path) -> None:
    """5. `END_DISCOVERY` кладётся ровно `workers.parse` раз — вышли все воркеры."""
    counting = _CountingQueue()
    pipe = _build(repo_root, workers=4, tasks=counting)  # type: ignore[arg-type]
    _submit(pipe, 5)
    _shutdown(pipe)

    assert counting.gets == 5 + 4
    assert len(pipe.collector.results) == 5
    assert all(not worker.is_alive() for worker in pipe.workers)


def test_no_threads_left_after_shutdown(repo_root: Path) -> None:
    """6. После завершения `threading.enumerate()` не содержит наших потоков (инвариант 11)."""
    pipe = _build(repo_root, workers=3)
    _submit(pipe, 6)
    _shutdown(pipe)

    alive = threading.enumerate()
    assert [thread.name for thread in pipe.threads if thread in alive] == []
    assert [thread.name for thread in alive if thread.name.startswith("parse-")] == []
    assert [thread.name for thread in alive if thread.name == "collector"] == []


def test_result_not_modified_after_put(repo_root: Path) -> None:
    """7. После `put()` поток-владелец объект не изменяет (правило владения, D15.2)."""
    recording = _RecordingStats()
    pipe = _build(repo_root, workers=2, stats=recording)
    _submit(pipe, 5)
    _shutdown(pipe)

    at_receipt = dict(recording.seen)
    assert len(at_receipt) == 5, "объекты-результаты должны быть разными"
    for result in pipe.collector.results:
        assert id(result) in at_receipt, "наблюдатель получил не тот объект, что опубликовал worker"
        assert at_receipt[id(result)] == _state(result), "объект изменён после публикации"


def test_task_done_called_for_sentinel(repo_root: Path) -> None:
    """8. `task_done()` вызван и для сентинела: `TaskQueue.join()` не виснет при 3 воркерах."""
    counting = _CountingQueue()
    pipe = _build(repo_root, workers=3, tasks=counting)  # type: ignore[arg-type]
    _submit(pipe, 3)

    for _ in pipe.workers:
        pipe.tasks.put(END_DISCOVERY)
    _join_queue(pipe.tasks, "TaskQueue")  # без task_done на сентинел здесь был бы вечный висяк
    assert counting.dones == 3 + 3
    _shutdown_tail(pipe)


def test_checker_error_published(repo_root: Path) -> None:
    """9. Исключение в чекере (не при чтении) → результат с `error` всё равно опубликован."""
    pipe = _build(repo_root, workers=2, checker=_Checker(boom=True))
    _submit(pipe, 3)
    _shutdown(pipe)

    assert len(pipe.collector.results) == 3
    assert all(not result.ok for result in pipe.collector.results)
    assert all(result.error.startswith("RuntimeError:") for result in pipe.collector.results)


def test_statistics_snapshot_and_summary(repo_root: Path) -> None:
    """10. `snapshot()` отражает результаты; `summary(fail_on_broken=True)` при битых → код 1."""
    stats = StatisticsCollector()
    stats.add_repo(is_nested=False)
    stats.add_repo(is_nested=True)
    stats.repo_done()
    stats.md_found(4)
    pipe = _build(
        repo_root,
        workers=2,
        stats=stats,
        extractor=_Extractor(links_per_file=3),
        checker=_Checker(status=CheckStatus.BROKEN),
    )
    _submit(pipe, 4)
    _shutdown(pipe)

    snap = stats.snapshot(task_qsize=0, result_qsize=0)
    assert (snap.repos_total, snap.repos_done, snap.md_found, snap.parsed) == (2, 1, 4, 4)
    assert (snap.links, snap.broken) == (12, 12)

    summary = stats.summary(duration_sec=2.0, fail_on_broken=True)
    assert summary.exit_code == 1
    assert summary.counters["repos_nested"] == pytest.approx(1.0)
    assert summary.counters["links_total"] == pytest.approx(12.0)
    assert summary.counters["links_local"] == pytest.approx(12.0)
    assert summary.counters["broken_local"] == pytest.approx(12.0)
    assert summary.counters["files_ok"] == pytest.approx(4.0)
    assert summary.counters["broken_ratio"] == pytest.approx(1.0)
    assert summary.counters["error_rate"] == pytest.approx(0.0)
    assert summary.counters["throughput_files_per_sec"] == pytest.approx(2.0)
    assert stats.summary(duration_sec=2.0, fail_on_broken=False).exit_code == 0


def test_sentinels_are_distinct() -> None:
    """Сентинелы — разные объекты своего типа: перепутать очереди нечем (D3)."""
    assert END_DISCOVERY is not END_RESULTS
    assert isinstance(END_DISCOVERY, _Sentinel)
    assert END_DISCOVERY.name == "END_DISCOVERY"
    assert "END_RESULTS" in repr(END_RESULTS)
