"""Разбор одного файла `.md`: чтение → извлечение → классификация → проверка → публикация.

Владелец `MdFileResult` от создания до `put()` (C2 вариант A, D3): один поток пишет,
после публикации объект не изменяется — копий и заморозки не нужно (D15.2).
Ошибка **любого** шага не теряется: она становится `result.error`, а результат всё
равно публикуется, иначе файл молча исчезнет из статистики (D2.1).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from core.mdscan.checking.checker_factory import CheckerFactory
from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.md_task import MdTask
from core.mdscan.parsing.link_classifier import LinkClassifier
from core.mdscan.parsing.link_extractor import LinkExtractor
from core.mdscan.parsing.markdown_reader import MarkdownReader
from core.mdscan.runtime.base_observer import BaseObserver
from core.mdscan.runtime.notifier import Notifier
from core.mdscan.runtime.queues import ResultQueue, TaskQueue
from core.mdscan.runtime.sentinels import END_DISCOVERY

logger = logging.getLogger("core.mdscan.runtime")

#: Статусы, которые обязаны быть видны в логе уровня `INFO` (то есть как `WARNING`).
_LOUD_STATUSES = frozenset({CheckStatus.BROKEN, CheckStatus.TIMEOUT})


class MarkdownWorker(BaseObserver):
    """Потребитель `TaskQueue` — поток `parse-N`.

    Всё, что он умеет, приходит через конструктор (DI): чтение, извлечение,
    классификация, чекеры и вывод сообщений — чужие контракты, а не конкретные
    классы. Поэтому конвейер тестируется без markdown-it, диска и сети.
    """

    def __init__(
        self,
        tasks: TaskQueue,
        results: ResultQueue,
        name: str,
        reader: MarkdownReader,
        extractor: LinkExtractor,
        classifier: LinkClassifier,
        checkers: CheckerFactory,
        notifier: Notifier,
    ) -> None:
        super().__init__(tasks, END_DISCOVERY, name)
        self._results = results
        self._reader = reader
        self._extractor = extractor
        self._classifier = classifier
        self._checkers = checkers
        self._notifier = notifier

    def on_item(self, task: MdTask) -> None:
        """Разобрать файл и опубликовать результат — в любом исходе, включая ошибку."""
        started = time.perf_counter()
        result = MdFileResult(
            repo=task.repo,
            md_file=task.md_file,
            rel_path=self._rel_path(task),
            thread_name=self.name,
        )
        if logger.isEnabledFor(logging.DEBUG):  # словарь контекста строится только при DEBUG (G4)
            logger.debug("parse-start", extra=self._log_context(result))
        try:
            result.links = list(self._extractor.extract(self._reader.read(task.md_file)))
            self._check_links(result)
            self._notifier.show(f"[parse] {result.rel_path}: {len(result.links)} ссылок")
        except Exception as exc:  # noqa: BLE001 — ошибка файла не роняет прогон (D2.1)
            logger.exception("разбор файла провален", extra=self._log_context(result))
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            result.seconds = time.perf_counter() - started
            logger.info(
                "parsed links=%d broken=%d elapsed=%.1fms error=%s",
                len(result.links),
                result.broken_count,
                result.seconds * 1000,
                result.error or "-",
                extra=self._log_context(result),
            )
            self._results.put(result)  # после этой строки объект не трогаем (D15.2)

    def _check_links(self, result: MdFileResult) -> None:
        """Категория + проверка каждой ссылки; исход пишется в саму ссылку."""
        for link in result.links:
            link.kind = self._classifier.classify(link)
            self._checkers.for_kind(link.kind).check(link, result.md_file)
            self._log_link(link, result)

    @staticmethod
    def _log_link(link: MdLink, result: MdFileResult) -> None:
        """Хорошая ссылка → `DEBUG`, битая или таймаут → `WARNING` (D2.1).

        Здесь **единственная** запись `WARNING` на битую ссылку за прогон: чекеры
        про свой исход пишут только `DEBUG` (H-06), иначе одна ссылка давала две
        строки, а поля `repo`/`file` формата лога есть лишь тут.

        Кортеж аргументов и словарь контекста строятся **после** проверки уровня:
        при выключенном `DEBUG` целая ссылка не стоит ничего (гипотеза G4).
        """
        loud = link.status in _LOUD_STATUSES
        if not loud and not logger.isEnabledFor(logging.DEBUG):
            return
        write = logger.warning if loud else logger.debug
        write(
            "link %s kind=%s target=%s line=%d http=%d %s",
            link.status.value,
            link.kind.value,
            link.target,
            link.line,
            link.http_code,
            link.detail,
            extra={"repo": result.repo.root.name, "file": result.rel_path},
        )

    @staticmethod
    def _log_context(result: MdFileResult) -> dict[str, str]:
        """Поля `repo`/`file` формата лога (T-04): без них строка неотличима от чужой."""
        return {"repo": result.repo.root.name, "file": result.rel_path}

    @staticmethod
    def _rel_path(task: MdTask) -> str:
        """Путь файла относительно корня репозитория, всегда через `/` (одинаково на обеих ОС)."""
        try:
            return task.md_file.relative_to(task.repo.root).as_posix()
        except ValueError:
            return Path(task.md_file).as_posix()
