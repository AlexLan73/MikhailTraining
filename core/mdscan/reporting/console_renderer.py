"""Контракт вывода итогов в консоль — Strategy с двумя реализациями (D10).

Владелец контракта — T-12, потребитель — оркестратор (T-13): он получает
реализацию у `RendererFactory` и зовёт `render(results, summary)`, не зная,
установлен ли `rich`.

Здесь же — **общая** подготовка строк для обеих реализаций: считать одни и те же
числа дважды нельзя (правило 07, один источник истины), а различаться должна
только отрисовка.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..enums.check_status import CheckStatus
from ..models.md_file_result import MdFileResult
from ..models.scan_summary import ScanSummary

#: Строка таблицы итогов: показатель, значение, «это проблема» (для подсветки).
SummaryRow = tuple[str, str, bool]

#: Строка списка битых: файл со строкой, цель, статус, код ответа или причина.
BrokenRow = tuple[str, str, str, str]


class ConsoleRenderer(Protocol):
    """Печатает итоги прогона: таблица чисел + список битых ссылок с кодами.

    Порядок аргументов — как у `MarkdownReportBuilder.build` и в C4: сначала
    результаты (из них берётся список битых), потом сводка (числа и код возврата).
    """

    def render(self, results: Sequence[MdFileResult], summary: ScanSummary) -> None:
        """Вывести итоги в свой поток; ничего не возвращает и не бросает."""
        ...


def summary_rows(results: Sequence[MdFileResult], summary: ScanSummary) -> tuple[SummaryRow, ...]:
    """Таблица итогов: файлы, ссылки, битые, таймауты, ошибки, время, код возврата."""
    links = sum(len(result.links) for result in results)
    broken = _count(results, CheckStatus.BROKEN)
    timeouts = _count(results, CheckStatus.TIMEOUT)
    failed = sum(1 for result in results if not result.ok)
    return (
        ("файлов", str(len(results)), False),
        ("ссылок", str(links), False),
        ("битых", str(broken), broken > 0),
        ("таймаутов", str(timeouts), timeouts > 0),
        ("файлов с ошибкой", str(failed), failed > 0),
        ("длительность, с", f"{summary.duration_sec:.2f}", False),
        ("код возврата", str(summary.exit_code), summary.exit_code != 0),
    )


def broken_rows(results: Sequence[MdFileResult]) -> tuple[BrokenRow, ...]:
    """Битые и таймаутные ссылки в порядке «репозиторий → файл → строка»."""
    rows: list[BrokenRow] = []
    for result in sorted(results, key=lambda item: (str(item.repo.root), item.rel_path)):
        for link in result.links:
            if link.status not in (CheckStatus.BROKEN, CheckStatus.TIMEOUT):
                continue
            code = str(link.http_code) if link.http_code else (link.detail or "—")
            rows.append((f"{result.rel_path}:{link.line}", link.target, link.status.value, code))
    return tuple(rows)


def _count(results: Sequence[MdFileResult], status: CheckStatus) -> int:
    """Сколько ссылок во всех файлах имеют заданный статус."""
    return sum(1 for result in results for link in result.links if link.status is status)
