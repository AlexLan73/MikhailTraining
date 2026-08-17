"""Выбор реализации `ConsoleRenderer` (Factory Method, D10).

Правило простое: `rich` доступен → `RichConsoleRenderer`, иначе `PlainConsoleRenderer`.
Отсутствие необязательной библиотеки не должно ронять прогон, поэтому и проверка
наличия, и сам импорт защищены — при любой неожиданности берётся plain-путь.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from typing import TextIO

from .console_renderer import ConsoleRenderer
from .plain_console_renderer import PlainConsoleRenderer

_log = logging.getLogger("core.mdscan.reporting")

_RICH = "rich"


class RendererFactory:
    """Создаёт рендерер консоли; поток вывода задаётся один раз при сборке."""

    def __init__(self, stream: TextIO | None = None) -> None:
        # H-10: `sys.stdout` берём в момент вызова, а не импорта — иначе подмена stdout
        # (pytest capsys, перенаправление в файл после импорта) проходит мимо рендерера.
        self._stream = stream if stream is not None else sys.stdout

    def create(self) -> ConsoleRenderer:
        """`rich` установлен → `RichConsoleRenderer`, иначе `PlainConsoleRenderer`."""
        if not self._rich_available():
            return PlainConsoleRenderer(self._stream)
        try:
            from .rich_console_renderer import RichConsoleRenderer  # noqa: PLC0415

            renderer: ConsoleRenderer = RichConsoleRenderer(self._stream)
        except ImportError as exc:
            _log.warning("rich найден, но не импортируется (%s) — вывод обычным рендерером", exc)
            return PlainConsoleRenderer(self._stream)
        _log.info("вывод в консоль: rich")
        return renderer

    @staticmethod
    def _rich_available() -> bool:
        """Есть ли `rich` в окружении; спорный ответ трактуем как «нет» (D2.1)."""
        try:
            return importlib.util.find_spec(_RICH) is not None
        except (ImportError, ValueError) as exc:
            _log.warning("проверка наличия rich не удалась (%s: %s) — берём plain", type(exc).__name__, exc)
            return False
