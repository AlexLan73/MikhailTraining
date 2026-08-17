"""Сборка итогового Markdown-отчёта прогона (Builder).

Отчёт строит **главный поток после `join()`** (инвариант 25): сюда приходят уже
готовые `MdFileResult` из коллектора и `ScanSummary` из статистики. Никаких
собственных вычислений над временем и никаких походов на диск — только текст.

Детерминизм (инвариант 9): все перечни сортируются, множества не обходятся без
`sorted`, время берётся из `started_at` и `summary.duration_sec`, а не из часов.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from datetime import datetime

from ..config.scan_config import ScanConfig
from ..enums.check_status import CheckStatus
from ..enums.link_kind import LinkKind
from ..models.md_file_result import MdFileResult
from ..models.md_link import MdLink
from ..models.repo_info import RepoInfo
from ..models.scan_summary import ScanSummary

_log = logging.getLogger("core.mdscan.reporting")

#: Заглушка пустой секции: Markdown не любит таблицу без строк.
_EMPTY = "_нет_"

#: Прочерк в ячейке, где значения нет (пустая ячейка выглядит как сбой вёрстки).
_DASH = "—"

#: Категории ссылок, битость которых лечится правкой дерева файлов.
_LOCAL_KINDS = frozenset({LinkKind.LOCAL, LinkKind.ANCHOR})

#: Категории ссылок, которые проверяются по сети (у них есть код ответа).
_HTTP_KINDS = frozenset({LinkKind.URL, LinkKind.GITHUB})
#: Коды «доступ закрыт», а не «страницы нет»: сайт жив, но не пускает автомат (бот-защита, авторизация,
#: лимит запросов). Решение Alex (ревью 6): показывать отдельной секцией, чтобы не смешивать с мёртвыми ссылками.
_ACCESS_DENIED_CODES = frozenset({401, 403, 429})

_SelectedLinks = list[tuple[MdFileResult, MdLink]]


class MarkdownReportBuilder:
    """Строит текст отчёта: цель, репозитории, статистика, файлы, битые ссылки.

    Цель, заголовок и время старта приходят из конфигурации и аргумента
    конструктора (ревью 5): `ScanSummary` знает только числа, а как назывался
    прогон — знает тот, кто его запускал.
    """

    def __init__(self, config: ScanConfig, started_at: datetime) -> None:
        self._config = config
        self._started_at = started_at
        self._title = config.report.title.strip() or self._scope()

    def build(self, results: Sequence[MdFileResult], summary: ScanSummary) -> str:
        """Собрать полный текст отчёта (Markdown, заканчивается переводом строки)."""
        ordered = sorted(results, key=_file_key)
        lines: list[str] = [f"# Отчёт mdscan — {_escape(self._title)}", ""]
        lines += self._run_section(summary)
        lines += self._target_section()
        lines += self._repos_section(ordered)
        lines += self._links_section(ordered, summary)
        lines += self._files_section(ordered)
        lines += self._broken_local_section(ordered)
        lines += self._broken_http_section(ordered)
        lines += self._access_denied_section(ordered)
        lines += self._timeout_section(ordered)
        lines += self._errors_section(ordered)
        _log.info("отчёт собран: файлов %d, строк %d", len(ordered), len(lines))
        return "\n".join(lines) + "\n"

    def _run_section(self, summary: ScanSummary) -> list[str]:
        """Время старта, длительность и код возврата — шапка прогона."""
        rows = [
            ["старт", self._started_at.strftime("%Y-%m-%d %H:%M:%S")],
            ["длительность, с", f"{summary.duration_sec:.2f}"],
            ["код возврата", str(summary.exit_code)],
        ]
        return _block("## Прогон", ("параметр", "значение"), rows)

    def _target_section(self) -> list[str]:
        """Цель прогона: `source.target` и разобранный список целей (правило V5)."""
        source = self._config.source
        rows = [[_code(address), kind.value] for address, kind in source.targets_resolved]
        if not rows and source.target:
            rows = [[_code(source.target), source.kind]]
        return _block("## Цель", ("цель", "вид"), rows)

    def _repos_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """Уникальные репозитории результатов, порядок — по корню (детерминизм)."""
        unique: dict[str, RepoInfo] = {}
        for result in ordered:
            unique.setdefault(str(result.repo.root), result.repo)
        rows = [
            [_code(root), _code(repo.web_url) if repo.web_url else _DASH, _yes_no(repo.is_nested)]
            for root, repo in sorted(unique.items())
        ]
        return _block("## Репозитории", ("корень", "web_url", "вложенный"), rows)

    def _links_section(self, ordered: Sequence[MdFileResult], summary: ScanSummary) -> list[str]:
        """Свои `Counter` по `MdLink.kind` и `CheckStatus` плюс счётчики прогона."""
        totals: Counter[LinkKind] = Counter()
        by_status: Counter[tuple[LinkKind, CheckStatus]] = Counter()
        for result in ordered:
            for link in result.links:
                totals[link.kind] += 1
                by_status[link.kind, link.status] += 1
        rows = [
            [kind.value, str(totals[kind]), *[str(by_status[kind, status]) for status in CheckStatus]]
            for kind in LinkKind
            if totals[kind]
        ]
        header = ("категория", "всего", *[status.value for status in CheckStatus])
        lines = _block("## Статистика по типам ссылок", header, rows)
        counters = [[_escape(name), _number(value)] for name, value in sorted(summary.counters.items())]
        return lines + _block("### Счётчики прогона", ("счётчик", "значение"), counters)

    def _files_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """Таблица файлов: репозиторий · путь · ссылок · статус · ошибка."""
        rows = [
            [
                _code(result.repo.root.name),
                _code(result.rel_path),
                str(len(result.links)),
                _file_status(result),
                _escape(result.error) if result.error else _DASH,
            ]
            for result in ordered
        ]
        header = ("репозиторий", "путь", "ссылок", "статус", "ошибка")
        return _block("## Файлы", header, rows)

    def _broken_local_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """Битые локальные ссылки и якоря: файл · строка · цель · причина."""
        rows = [
            [_file_label(result), str(link.line), _code(link.target), _escape(link.detail) or _DASH]
            for result, link in _select(ordered, _LOCAL_KINDS, CheckStatus.BROKEN)
        ]
        header = ("файл", "строка", "цель", "причина")
        return _block("## Битые локальные ссылки", header, rows)

    def _broken_http_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """Битые внешние ссылки — обязательно с кодом ответа (D11: 404/500/DNS)."""
        rows = [
            [
                _file_label(result),
                str(link.line),
                _code(link.target),
                str(link.http_code) if link.http_code else _DASH,
                _escape(link.detail) or _DASH,
            ]
            for result, link in _select(ordered, _HTTP_KINDS, CheckStatus.BROKEN)
            if link.http_code not in _ACCESS_DENIED_CODES
        ]
        header = ("файл", "строка", "url", "код", "причина")
        return _block("## Битые HTTP-ссылки", header, rows)

    def _access_denied_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """`401`/`403`/`429` — сайт отвечает, но не пускает автомат: вероятно бот-защита или лимит.

        Такие ссылки остаются `BROKEN` в статистике (мы не смогли подтвердить доступность), но в отчёте
        стоят отдельно: чинить их обычно не нужно — нужно открыть глазами.
        """
        rows = [
            [
                _file_label(result),
                str(link.line),
                _code(link.target),
                str(link.http_code),
                _escape(link.detail) or _DASH,
            ]
            for result, link in _select(ordered, _HTTP_KINDS, CheckStatus.BROKEN)
            if link.http_code in _ACCESS_DENIED_CODES
        ]
        header = ("файл", "строка", "url", "код", "причина")
        return _block("## HTTP 401/403/429 — вероятно защита от ботов или лимит (проверить вручную)", header, rows)

    def _timeout_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """`TIMEOUT` — отдельная секция: причина иная, чем у `BROKEN` (D11)."""
        rows = [
            [_file_label(result), str(link.line), _code(link.target), link.kind.value]
            for result, link in _select(ordered, frozenset(LinkKind), CheckStatus.TIMEOUT)
        ]
        header = ("файл", "строка", "цель", "категория")
        return _block("## Таймауты", header, rows)

    def _errors_section(self, ordered: Sequence[MdFileResult]) -> list[str]:
        """Файлы, которые не удалось обработать (ошибка не теряется, D2.1)."""
        rows = [[_file_label(result), _escape(result.error)] for result in ordered if not result.ok]
        return _block("## Файлы с ошибками", ("файл", "ошибка"), rows)

    def _scope(self) -> str:
        """Имя цели для заголовка: последний сегмент пути/URL, пусто → `mdscan`."""
        source = self._config.source
        address = source.target or (source.targets_resolved[0][0] if source.targets_resolved else "")
        tail = address.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return tail or "mdscan"


def _select(
    ordered: Sequence[MdFileResult], kinds: frozenset[LinkKind], status: CheckStatus
) -> _SelectedLinks:
    """Пары «файл + ссылка» нужных категорий и статуса, в порядке файлов и строк."""
    return [
        (result, link)
        for result in ordered
        for link in result.links
        if link.kind in kinds and link.status is status
    ]


def _file_key(result: MdFileResult) -> tuple[str, str]:
    """Ключ сортировки файлов: репозиторий, затем путь внутри него."""
    return str(result.repo.root), result.rel_path


def _file_label(result: MdFileResult) -> str:
    """Файл в трио D6.4 «репозиторий / файл» — одной ячейкой."""
    return _code(f"{result.repo.root.name}/{result.rel_path}")


def _file_status(result: MdFileResult) -> str:
    """Статус файла: ошибка чтения, число битых ссылок или `ok`."""
    if not result.ok:
        return "ошибка"
    return f"битых: {result.broken_count}" if result.broken_count else "ok"


def _yes_no(flag: bool) -> str:
    """Логическое поле по-русски (отчёт читает человек, а не парсер)."""
    return "да" if flag else "нет"


def _number(value: float) -> str:
    """Счётчик в отчёт: целое печатаем без хвоста `.0`, дробное — тремя знаками."""
    return str(int(value)) if float(value).is_integer() else f"{value:.3f}"


def _escape(text: object) -> str:
    """Ячейка таблицы: `|` экранируется, переносы строк убираются — таблица не разъедется."""
    return str(text).replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def _code(text: object) -> str:
    """Длинный путь/URL — в обратных кавычках: не ломает вёрстку и читается как код."""
    inner = str(text).replace("|", r"\|").replace("`", "'")
    return f"`{inner}`"


def _block(heading: str, header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Заголовок + таблица (или `_нет_`, если строк нет) + пустая строка."""
    if not rows:
        return [heading, "", _EMPTY, ""]
    lines = [heading, "", "| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    lines.append("")
    return lines
