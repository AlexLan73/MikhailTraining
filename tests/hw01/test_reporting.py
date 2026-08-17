"""T-12 — отчёты: Markdown-файл и вывод в консоль.

Проверяем контракт `MarkdownReportBuilder` / `ConsoleRenderer` / `RendererFactory`
на руками собранных `MdFileResult`: реального прогона тут нет и быть не должно —
отчёт обязан строиться из данных, а не из побочных эффектов конвейера.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from core.mdscan.config.config_draft import ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.models.scan_summary import ScanSummary
from core.mdscan.reporting.markdown_report_builder import MarkdownReportBuilder
from core.mdscan.reporting.plain_console_renderer import PlainConsoleRenderer
from core.mdscan.reporting.renderer_factory import RendererFactory

#: Время старта — фиксированное: отчёт обязан быть детерминированным (инвариант 9).
STARTED_AT = datetime(2026, 8, 16, 5, 0, 12)

#: Заголовки, без которых отчёт считается неполным (ТЗ T-12).
REQUIRED_SECTIONS = (
    "Прогон",
    "Цель",
    "Репозитории",
    "Статистика по типам ссылок",
    "Файлы",
    "Битые локальные ссылки",
    "Битые HTTP-ссылки",
    "Таймауты",
    "Файлы с ошибками",
)


class TtyStream(io.StringIO):
    """Поток, который представляется терминалом — для проверки ANSI-цветов."""

    def isatty(self) -> bool:
        return True


def make_config(title: str = "", target: str = "/repos/alpha") -> ScanConfig:
    """`ScanConfig` из значений по умолчанию с заданными целью и заголовком отчёта."""
    draft = ConfigDraft.from_defaults()
    draft.assign("source.target", target, "c")
    draft.assign("source.targets_resolved", ((target, SourceKind.LOCAL),), "c")
    draft.assign("report.title", title, "c")
    return ScanConfig.from_draft(draft)


def link(
    target: str,
    kind: LinkKind,
    status: CheckStatus,
    line: int = 1,
    detail: str = "",
    http_code: int = 0,
) -> MdLink:
    """Ссылка в состоянии «после проверки» — как её отдаёт чекер (T-07)."""
    return MdLink(
        target=target,
        origin=LinkOrigin.INLINE,
        line=line,
        kind=kind,
        status=status,
        detail=detail,
        http_code=http_code,
    )


@pytest.fixture
def results() -> list[MdFileResult]:
    """Три файла: с битыми ссылками всех видов, чистый и не прочитанный."""
    alpha = RepoInfo(root=Path("/repos/alpha"), web_url="https://github.com/org/alpha")
    beta = RepoInfo(root=Path("/repos/beta"), is_nested=True)
    guide = MdFileResult(
        repo=alpha,
        md_file=Path("/repos/alpha/docs/guide.md"),
        rel_path="docs/guide.md",
        links=[
            link("intro.md", LinkKind.LOCAL, CheckStatus.OK, line=3),
            link("нет.md", LinkKind.LOCAL, CheckStatus.BROKEN, line=5, detail="файла нет | проверь путь"),
            link("#нет-такого", LinkKind.ANCHOR, CheckStatus.BROKEN, line=7, detail="нет заголовка"),
            link("https://example.org/missing", LinkKind.URL, CheckStatus.BROKEN, 9, "not found", 404),
            link("https://github.com/org/hang", LinkKind.GITHUB, CheckStatus.TIMEOUT, line=11),
            link("mailto:alex@example.org", LinkKind.MAILTO, CheckStatus.SKIPPED, line=13),
        ],
        seconds=0.5,
    )
    readme = MdFileResult(
        repo=alpha,
        md_file=Path("/repos/alpha/README.md"),
        rel_path="README.md",
        links=[link("https://example.org/ok", LinkKind.URL, CheckStatus.OK, line=1, http_code=200)],
    )
    broken_file = MdFileResult(
        repo=beta,
        md_file=Path("/repos/beta/notes.md"),
        rel_path="notes.md",
        error="битая кодировка: 'utf-8' codec can't decode byte 0xff",
    )
    return [readme, broken_file, guide]


@pytest.fixture
def summary() -> ScanSummary:
    """Сводка прогона: целые и дробные счётчики, код возврата 1 (битые есть)."""
    counters = {
        "md_files_total": 3.0,
        "files_failed": 1.0,
        "links_total": 7.0,
        "broken_http": 1.0,
        "timeout_http": 1.0,
        "broken_ratio": 0.4285,
    }
    return ScanSummary(counters=counters, duration_sec=1.234, exit_code=1)


def build(results: Sequence[MdFileResult], summary: ScanSummary, title: str = "") -> str:
    """Собрать отчёт стандартным построителем."""
    return MarkdownReportBuilder(make_config(title), STARTED_AT).build(results, summary)


def sections(report: str) -> dict[str, str]:
    """Разобрать отчёт на секции второго уровня: заголовок → текст секции."""
    found: dict[str, list[str]] = {}
    current = ""
    for text_line in report.splitlines():
        if text_line.startswith("## "):
            current = text_line[3:]
            found[current] = []
        elif current:
            found[current].append(text_line)
    return {name: "\n".join(body) for name, body in found.items()}


def pipes(text_line: str) -> int:
    """Сколько разделителей ячеек в строке таблицы (экранированные `\\|` не в счёт)."""
    return text_line.count("|") - text_line.count("\\|")


# --- 1. все обязательные секции -------------------------------------------------------------


def test_report_contains_all_required_sections(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Тест 1: в отчёте присутствуют все обязательные секции ТЗ."""
    found = sections(build(results, summary))
    assert list(REQUIRED_SECTIONS) == [name for name in REQUIRED_SECTIONS if name in found]
    assert set(REQUIRED_SECTIONS) <= set(found)


def test_report_header_shows_start_time_and_duration(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 1 (продолжение): время старта и длительность — из аргументов, не из часов."""
    body = sections(build(results, summary))["Прогон"]
    assert "2026-08-16 05:00:12" in body
    assert "1.23" in body
    assert "| код возврата | 1 |" in body


def test_report_lists_unique_repositories_with_web_url(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 1 (продолжение): репозитории уникальны, отсортированы, с `web_url` (D6.4)."""
    body = sections(build(results, summary))["Репозитории"]
    rows = [row for row in body.splitlines() if row.startswith("| `")]
    assert len(rows) == 2, body
    assert rows[0].index("alpha") < len(rows[0])
    assert "https://github.com/org/alpha" in rows[0]
    assert "beta" in rows[1]


def test_report_link_statistics_counts_kinds(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Тест 1 (продолжение): статистика по типам ссылок считается своими структурами."""
    body = sections(build(results, summary))["Статистика по типам ссылок"]
    assert "| local | 2 | 1 | 1 | 0 | 0 |" in body
    assert "| url | 2 |" in body
    assert "| mailto | 1 |" in body
    assert "| broken_ratio | 0.428 |" in body
    assert "links_total" in body and "| 7 |" in body


def test_report_title_falls_back_to_target_name(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Заголовок берётся из `report.title`, пусто → имя цели."""
    assert build(results, summary).splitlines()[0].endswith("alpha")
    assert build(results, summary, title="Итоги: dsp-gpu").splitlines()[0].endswith("Итоги: dsp-gpu")


# --- 2. битая HTTP-ссылка с кодом -----------------------------------------------------------


def test_broken_http_link_reported_with_status_code(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 2: битая внешняя ссылка попадает в отчёт вместе с кодом ответа."""
    body = sections(build(results, summary))["Битые HTTP-ссылки"]
    rows = [row for row in body.splitlines() if "example.org/missing" in row]
    assert len(rows) == 1
    assert "404" in rows[0]
    assert "9" in rows[0]


def test_broken_local_links_listed_with_line_and_detail(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 2 (продолжение): битые локальные и якорные — с файлом, строкой и причиной."""
    body = sections(build(results, summary))["Битые локальные ссылки"]
    assert "нет.md" in body
    assert "#нет-такого" in body
    assert "нет заголовка" in body
    assert "example.org/missing" not in body


# --- 3. TIMEOUT отдельно --------------------------------------------------------------------


def test_timeout_has_its_own_section(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Тест 3: `TIMEOUT` — в своей секции и не смешан с `BROKEN`."""
    found = sections(build(results, summary))
    assert "github.com/org/hang" in found["Таймауты"]
    assert "github.com/org/hang" not in found["Битые HTTP-ссылки"]
    assert "github.com/org/hang" not in found["Битые локальные ссылки"]


def test_file_with_error_listed_in_errors_section(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Файл, который не прочитался, попадает в секцию ошибок (D2.1)."""
    found = sections(build(results, summary))
    assert "notes.md" in found["Файлы с ошибками"]
    assert "битая кодировка" in found["Файлы с ошибками"]
    assert "README.md" not in found["Файлы с ошибками"]


# --- 4. работа без rich ---------------------------------------------------------------------


def test_factory_falls_back_to_plain_without_rich(
    monkeypatch: pytest.MonkeyPatch, results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 4: `rich` скрыт → фабрика отдаёт `PlainConsoleRenderer`, и он печатает итоги."""
    monkeypatch.setitem(sys.modules, "rich", None)
    stream = io.StringIO()
    renderer = RendererFactory(stream).create()
    assert isinstance(renderer, PlainConsoleRenderer)
    renderer.render(results, summary)
    text = stream.getvalue()
    assert "битых" in text
    assert "404" in text
    assert "\033[" not in text


def test_plain_renderer_colors_only_for_tty(results: list[MdFileResult], summary: ScanSummary) -> None:
    """`PlainConsoleRenderer` красит вывод только для терминала."""
    tty = TtyStream()
    PlainConsoleRenderer(tty).render(results, summary)
    assert "\033[" in tty.getvalue()


def test_rich_renderer_used_when_available(results: list[MdFileResult], summary: ScanSummary) -> None:
    """`rich` установлен → фабрика отдаёт rich-рендерер, и он печатает итоги."""
    pytest.importorskip("rich", reason="rich не установлен — ветка проверяется на машине с rich")
    from core.mdscan.reporting.rich_console_renderer import RichConsoleRenderer

    stream = io.StringIO()
    renderer = RendererFactory(stream).create()
    assert isinstance(renderer, RichConsoleRenderer)
    renderer.render(results, summary)
    assert "итог" in stream.getvalue()


# --- 5. пустой прогон -----------------------------------------------------------------------


def test_empty_run_builds_valid_report() -> None:
    """Тест 5: 0 файлов → отчёт корректен, секции на месте, исключений нет."""
    empty = ScanSummary(counters={}, duration_sec=0.0, exit_code=0)
    report = build([], empty)
    found = sections(report)
    assert set(REQUIRED_SECTIONS) <= set(found)
    assert "_нет_" in found["Файлы"]
    assert "_нет_" in found["Битые HTTP-ссылки"]
    assert "_нет_" in found["Таймауты"]


def test_empty_run_renders_console_without_errors() -> None:
    """Тест 5 (продолжение): консоль на пустом прогоне печатает «нет», а не падает."""
    stream = io.StringIO()
    PlainConsoleRenderer(stream).render([], ScanSummary(counters={}, duration_sec=0.0, exit_code=0))
    text = stream.getvalue()
    assert "файлов" in text
    assert "нет" in text


# --- 6. детерминизм -------------------------------------------------------------------------


def test_report_is_deterministic(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Тест 6: два вызова на тех же данных дают идентичный текст (инвариант 9)."""
    assert build(results, summary) == build(results, summary)


def test_report_order_independent_of_input_order(
    results: list[MdFileResult], summary: ScanSummary
) -> None:
    """Тест 6 (продолжение): порядок результатов от конвейера на отчёт не влияет."""
    assert build(results, summary) == build(list(reversed(results)), summary)


# --- валидность Markdown ---------------------------------------------------------------------


def test_tables_have_consistent_column_count(results: list[MdFileResult], summary: ScanSummary) -> None:
    """Таблицы не разъезжаются: в каждом блоке одинаковое число разделителей."""
    block: list[str] = []
    blocks: list[list[str]] = []
    for text_line in build(results, summary).splitlines():
        if text_line.startswith("|"):
            block.append(text_line)
        elif block:
            blocks.append(block)
            block = []
    if block:
        blocks.append(block)
    assert blocks, "в отчёте нет ни одной таблицы"
    for table in blocks:
        assert len(table) >= 3, table
        assert len({pipes(row) for row in table}) == 1, table


def test_pipe_in_detail_is_escaped(results: list[MdFileResult], summary: ScanSummary) -> None:
    """`|` внутри причины экранируется — иначе строка таблицы разъедется."""
    body = sections(build(results, summary))["Битые локальные ссылки"]
    assert "файла нет \\| проверь путь" in body
