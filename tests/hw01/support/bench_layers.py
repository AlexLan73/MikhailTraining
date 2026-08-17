"""Разложение прогона сканера по слоям — прямые замеры без потоков (таск H-04).

Инструмент, а не тест: `pytest` его не собирает (имя файла не `test_*.py`).
Честная картина стоимости конвейера (спека этапа 2, §2.2): профайлер на
многопоточном прогоне даёт `cumtime` > 100 % и вводит в заблуждение, поэтому
каждый слой прогоняется отдельно и замеряется `time.perf_counter`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from core.mdscan.checking.checker_factory import CheckerFactory
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.discovery.markdown_file_finder import MarkdownFileFinder
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.parsing.link_classifier import LinkClassifier
from core.mdscan.parsing.markdown_it_heading_source import MarkdownItHeadingSource
from core.mdscan.parsing.markdown_it_link_extractor import MarkdownItLinkExtractor
from core.mdscan.parsing.markdown_reader import MarkdownReader
from core.mdscan.runtime.null_notifier import NullNotifier

#: Расширения, которые сканер считает Markdown (`scan.md_extensions` по умолчанию).
EXTENSIONS: tuple[str, ...] = (".md", ".markdown")

#: Логгер пакета: на время замера он глушится ровно так же, как это делает
#: `LoggingSetup.start(log_file=None)` при `logging.enabled: false` — иначе `WARNING`
#: о битых ссылках уходил бы в `stderr` через `lastResort` и портил числа.
LOGGER_NAME = "core.mdscan"

T = TypeVar("T")


class _NoGitLister:
    """Заглушка `GitFileLister`: при `respect_gitignore=False` обход её не зовёт.

    Отдельного файла не заслуживает — это три строки вспомогательного кода теста,
    а не класс предметной области (правило «один класс = один файл» касается `core/`).
    """

    def listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]:
        """Пустой список: ветка git в этом замере намеренно не используется."""
        return []


class LayerBench:
    """Стоимость каждого слоя конвейера на одном дереве, последовательно.

    Слои: обход → чтение → извлечение → классификация → проверка (холодный и
    тёплый кэш заголовков) → «полезная нагрузка» одним циклом. Накладные расходы
    считает вызывающий: полный прогон − обход − нагрузка.
    """

    def __init__(self, tree: Path, config: ScanConfig) -> None:
        self._tree = Path(tree)
        self._config = config
        self._reader = MarkdownReader()
        self._extractor = MarkdownItLinkExtractor()
        self._classifier = LinkClassifier.default()

    def measure(self) -> dict[str, float]:
        """Секунды по слоям + размер задачи (`files`, `links`); лог на время замера заглушен."""
        logger = logging.getLogger(LOGGER_NAME)
        handlers, propagate = list(logger.handlers), logger.propagate
        logger.handlers, logger.propagate = [logging.NullHandler()], False
        try:
            return self._measure()
        finally:
            logger.handlers, logger.propagate = handlers, propagate

    def _measure(self) -> dict[str, float]:
        """Сами замеры слоёв (вызывается под заглушенным логом)."""
        files, discover = self._timed(self._discover)
        texts, read = self._timed(lambda: [self._reader.read(path) for path in files])
        batches, extract = self._timed(lambda: [self._extractor.extract(text) for text in texts])
        _, classify = self._timed(lambda: self._classify(batches))
        factory = self._factory()
        _, check_cold = self._timed(lambda: self._check(factory, files, batches))
        _, check_warm = self._timed(lambda: self._check(factory, files, batches))
        _, payload = self._timed(lambda: self._payload(files))
        return {
            "files": float(len(files)),
            "links": float(sum(len(batch) for batch in batches)),
            "discover": discover,
            "read": read,
            "extract": extract,
            "classify": classify,
            "check_cold": check_cold,
            "check_warm": check_warm,
            "payload": payload,
        }

    # ── слои ─────────────────────────────────────────────────────────────────

    def _discover(self) -> tuple[Path, ...]:
        """Стадия 1: `rglob` + `resolve()` каждого файла + отсев вложенных репозиториев."""
        finder = MarkdownFileFinder(_NoGitLister(), EXTENSIONS, False, False)
        return tuple(finder.find(RepoInfo(root=self._tree), []))

    def _classify(self, batches: Sequence[Sequence[MdLink]]) -> int:
        """Проставляет `kind` каждой ссылке; возвращает число обработанных."""
        total = 0
        for batch in batches:
            for link in batch:
                link.kind = self._classifier.classify(link)
                total += 1
        return total

    def _check(
        self, factory: CheckerFactory, files: Sequence[Path], batches: Sequence[Sequence[MdLink]]
    ) -> int:
        """Проверка всех ссылок готовой фабрикой (кэш заголовков живёт в фабрике)."""
        total = 0
        for path, batch in zip(files, batches, strict=True):
            for link in batch:
                factory.for_kind(link.kind).check(link, path)
                total += 1
        return total

    def _payload(self, files: Sequence[Path]) -> int:
        """«Полезная нагрузка» одним циклом: read + extract + classify + check."""
        factory = self._factory()
        total = 0
        for path in files:
            for link in self._extractor.extract(self._reader.read(path)):
                link.kind = self._classifier.classify(link)
                factory.for_kind(link.kind).check(link, path)
                total += 1
        return total

    # ── приватные хелперы ────────────────────────────────────────────────────

    def _factory(self) -> CheckerFactory:
        """Свежая фабрика — значит холодный кэш заголовков `AnchorChecker`."""
        return CheckerFactory(self._config, MarkdownItHeadingSource(), NullNotifier())

    @staticmethod
    def _timed(action: Callable[[], T]) -> tuple[T, float]:
        """Результат действия и время его выполнения в секундах."""
        started = time.perf_counter()
        value = action()
        return value, time.perf_counter() - started
