"""Фабрика прогресса: включён ли он, терминал ли на выходе и чем рисовать (ревью 5)."""

from __future__ import annotations

import importlib.util
import logging
import sys
from typing import Final, TextIO

from ..config.scan_config import ScanConfig
from .plain_progress_view import PlainProgressView
from .progress_reporter import ProgressReporter
from .progress_source import ProgressSource
from .progress_view import ProgressView

LOGGER: Final = logging.getLogger("core.mdscan.runtime.progress")

#: Значение `progress.style`, означающее «прогресс не показывать вовсе».
STYLE_OFF: Final = "off"


class ProgressFactory:
    """Factory Method: три решения о прогрессе собраны здесь, а не в оркестраторе.

    Возвращает `None`, если прогресс не нужен — тогда вызывающий (T-13) берёт
    `NullNotifier` и в коде не появляется ни одного `if notifier is not None`.
    Созданный поток **не стартует**: `start()` зовёт оркестратор в нужной фазе (D4).
    """

    def create(
        self,
        config: ScanConfig,
        source: ProgressSource,
        stream: TextIO = sys.stderr,
    ) -> ProgressReporter | None:
        """Собрать поток прогресса по конфигурации либо вернуть `None`."""
        progress = config.progress
        if not progress.enabled or progress.style == STYLE_OFF:
            LOGGER.info(
                "прогресс выключен конфигурацией: enabled=%s, style=%s",
                progress.enabled,
                progress.style,
            )
            return None
        if not self._is_tty(stream):
            LOGGER.info("прогресс выключен: поток вывода не терминал")
            return None
        view = self._view(stream)
        LOGGER.info(
            "прогресс включён: %s, период %.2f с, строк сообщений %d",
            type(view).__name__,
            progress.interval_sec,
            progress.message_lines,
        )
        return ProgressReporter(
            source=source,
            view=view,
            interval_sec=progress.interval_sec,
            message_lines=progress.message_lines,
            message_ttl_sec=progress.message_ttl_sec,
        )

    @staticmethod
    def _is_tty(stream: TextIO) -> bool:
        """Терминал ли поток; поток без `isatty` или закрытый считаем не-терминалом."""
        try:
            return bool(stream.isatty())
        except Exception:
            LOGGER.exception("не удалось определить тип потока вывода — считаем не-терминалом")
            return False

    @staticmethod
    def _view(stream: TextIO) -> ProgressView:
        """`rich` установлен → красивая отрисовка, иначе — ANSI-строка (D10)."""
        if importlib.util.find_spec("rich") is None:
            return PlainProgressView(stream)
        from .rich_progress_view import RichProgressView

        return RichProgressView(stream)
