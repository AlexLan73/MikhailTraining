"""Вывод итогов без внешних зависимостей: ASCII-таблица + ANSI-цвета (D10).

Основной путь: базовый каркас обязан работать на машине, где `rich` не стоит.
Цвета включаются только для терминала (`stream.isatty()`); при перенаправлении
в файл или в тест остаётся чистый текст.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from typing import TextIO

from ..models.md_file_result import MdFileResult
from ..models.scan_summary import ScanSummary
from .console_renderer import SummaryRow, broken_rows, summary_rows

_log = logging.getLogger("core.mdscan.reporting")

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_GREEN = "\033[32m"

_SUMMARY_HEADER: tuple[str, str] = ("показатель", "значение")
_BROKEN_HEADER: tuple[str, str, str, str] = ("файл:строка", "цель", "статус", "код")


class PlainConsoleRenderer:
    """Реализация `ConsoleRenderer` на stdlib: рисует сама, ничего не импортирует.

    Печать идёт **только** через переданный поток (`stream.write`), а не `print`:
    поток — это и stdout прогона, и `io.StringIO` в тесте.
    """

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        self._stream = stream

    def render(self, results: Sequence[MdFileResult], summary: ScanSummary) -> None:
        """Таблица итогов и список битых ссылок с кодами ответа."""
        color = _is_tty(self._stream)
        rows = summary_rows(results, summary)
        broken = broken_rows(results)
        self._line(_paint("mdscan — итоги", _BOLD, color))
        self._table(_SUMMARY_HEADER, [(name, value) for name, value, _ in rows])
        self._legend(rows, color)
        self._line("")
        self._line(_paint("Битые ссылки", _BOLD, color))
        if broken:
            self._table(_BROKEN_HEADER, broken)
        else:
            self._line(_paint("  нет", _GREEN, color))
        _log.info("консоль: строк итогов %d, битых ссылок %d", len(rows), len(broken))

    def _legend(self, rows: Sequence[SummaryRow], color: bool) -> None:
        """Проблемные показатели — отдельной цветной строкой (в таблице цвет ломает ширину)."""
        problems = [f"{name}={value}" for name, value, bad in rows if bad]
        text = "  проблемы: " + (", ".join(problems) if problems else "нет")
        self._line(_paint(text, _RED if problems else _GREEN, color))

    def _table(self, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
        """ASCII-таблица с выравниванием по самой длинной ячейке столбца."""
        widths = [len(cell) for cell in header]
        for row in rows:
            widths = [max(width, len(cell)) for width, cell in zip(widths, row, strict=True)]
        separator = "  " + "-+-".join("-" * width for width in widths)
        self._line("  " + " | ".join(cell.ljust(width) for cell, width in zip(header, widths, strict=True)))
        self._line(separator)
        for row in rows:
            self._line("  " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)))

    def _line(self, text: str) -> None:
        """Одна строка в поток вывода (единственное место записи в этом классе)."""
        self._stream.write(f"{text}\n")


def _paint(text: str, code: str, color: bool) -> str:
    """Обернуть в ANSI-последовательность, если поток — терминал."""
    return f"{code}{text}{_RESET}" if color else text


def _is_tty(stream: TextIO) -> bool:
    """Терминал ли это. Подменённый/закрытый поток — не повод падать (D2.1)."""
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError) as exc:
        _log.warning("не удалось определить TTY (%s: %s) — печатаем без цветов", type(exc).__name__, exc)
        return False
