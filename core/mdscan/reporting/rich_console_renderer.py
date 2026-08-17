"""Вывод итогов через `rich`, когда библиотека установлена (D10).

`rich` — необязательная зависимость: импорт делается **внутри конструктора**,
чтобы сам модуль импортировался на машине без неё, а решение «rich или plain»
принимала `RendererFactory`.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from typing import Any, TextIO

from ..models.md_file_result import MdFileResult
from ..models.scan_summary import ScanSummary
from .console_renderer import broken_rows, summary_rows

_log = logging.getLogger("core.mdscan.reporting")

_SUMMARY_HEADER: tuple[str, ...] = ("показатель", "значение")
_BROKEN_HEADER: tuple[str, ...] = ("файл:строка", "цель", "статус", "код")


class RichConsoleRenderer:
    """Реализация `ConsoleRenderer` поверх `rich.table.Table`.

    Числа и список битых берутся теми же функциями, что и у `PlainConsoleRenderer`
    (`console_renderer`), — различается только отрисовка (правило 07).
    """

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        from rich.console import Console  # noqa: PLC0415 — опциональная зависимость

        self._console: Any = Console(file=stream, highlight=False)

    def render(self, results: Sequence[MdFileResult], summary: ScanSummary) -> None:
        """Две таблицы `rich`: итоги прогона и битые ссылки с кодами."""
        rows = summary_rows(results, summary)
        broken = broken_rows(results)
        totals = self._table("mdscan — итоги", _SUMMARY_HEADER)
        for name, value, bad in rows:
            totals.add_row(name, f"[red]{value}[/red]" if bad else value)
        self._console.print(totals)
        if broken:
            table = self._table("Битые ссылки", _BROKEN_HEADER)
            for row in broken:
                table.add_row(*row)
            self._console.print(table)
        else:
            self._console.print("[green]Битых ссылок нет[/green]")
        _log.info("консоль (rich): строк итогов %d, битых ссылок %d", len(rows), len(broken))

    @staticmethod
    def _table(title: str, header: Sequence[str]) -> Any:
        """Пустая таблица `rich` с заголовком и колонками."""
        from rich.table import Table  # noqa: PLC0415 — опциональная зависимость

        table = Table(title=title)
        for column in header:
            table.add_column(column, overflow="fold")
        return table
