"""Счётчики прогона: одни и те же числа идут в прогресс, в лог, в отчёт и в метрики ДЗ.

Один источник истины (§9.1): считаем здесь, а не в отчёте и не в консоли — иначе
«битых 7» на экране и «битых 6» в файле разъедутся и никто не поймёт, кто прав.
Класс потокобезопасен: пишет поток `collector`, читает поток прогресса (D3.5).
"""

from __future__ import annotations

import threading
from collections import Counter
from typing import Final

from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.progress_snapshot import ProgressSnapshot
from core.mdscan.models.scan_summary import ScanSummary

#: Категория ссылки → имя счётчика (§9.1). Таблица вместо `if/elif` (правило 09 п.7).
_LINKS_BY_KIND: Final[dict[LinkKind, str]] = {
    LinkKind.LOCAL: "links_local",
    LinkKind.ANCHOR: "links_anchor",
    LinkKind.GITHUB: "links_github",
    LinkKind.URL: "links_url",
    LinkKind.MAILTO: "links_mailto",
    LinkKind.TEL: "links_tel",
    LinkKind.WIKILINK: "links_wikilink",
    LinkKind.FOOTNOTE_URL: "links_footnote",
    LinkKind.UNKNOWN: "links_unknown",
}

#: Категория ссылки со статусом `BROKEN` → имя счётчика битых (`TIMEOUT` — отдельно).
_BROKEN_BY_KIND: Final[dict[LinkKind, str]] = {
    LinkKind.LOCAL: "broken_local",
    LinkKind.ANCHOR: "broken_anchor",
    LinkKind.GITHUB: "broken_http",
    LinkKind.URL: "broken_http",
}

#: Имена §9.1, которые считаются сложением: отчёт всегда получает полный набор, даже нулевой.
_ADDITIVE_COUNTERS: Final[tuple[str, ...]] = (
    "repos_total",
    "repos_nested",
    "md_files_total",
    "files_ok",
    "files_failed",
    "links_total",
    *_LINKS_BY_KIND.values(),
    "broken_local",
    "broken_anchor",
    "broken_http",
    "timeout_http",
    "broken_total",  # 🔧 р5: все BROKEN+TIMEOUT независимо от категории (добавлен в §9.1)
)

#: Служебные счётчики: нужны прогрессу, но в §9.1 их нет — наружу не выдаются.
_INTERNAL_COUNTERS: Final[tuple[str, ...]] = ("repos_done",)


class StatisticsCollector:
    """Накопитель чисел прогона. Ничего не печатает и не строит отчёт (инвариант 25)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        zero = dict.fromkeys(_ADDITIVE_COUNTERS + _INTERNAL_COUNTERS, 0)
        self._counts: Counter[str] = Counter(zero)

    def add(self, result: MdFileResult) -> None:
        """Учесть один разобранный файл со всеми его ссылками."""
        with self._lock:
            self._counts["files_ok" if result.ok else "files_failed"] += 1
            for link in result.links:
                self._add_link(link.kind, link.status)

    def add_repo(self, is_nested: bool) -> None:
        """Найден репозиторий (стадия 1): `repos_total`, вложенные — ещё и `repos_nested`."""
        with self._lock:
            self._counts["repos_total"] += 1
            if is_nested:
                self._counts["repos_nested"] += 1

    def repo_done(self) -> None:
        """Репозиторий обойдён — для строки прогресса «repos n/N»."""
        with self._lock:
            self._counts["repos_done"] += 1

    def md_found(self, count: int = 1) -> None:
        """Найдено `count` файлов `.md` (поставлены в задачи)."""
        with self._lock:
            self._counts["md_files_total"] += count

    def summary(self, duration_sec: float, fail_on_broken: bool) -> ScanSummary:
        """Итоги прогона: счётчики §9.1, время и код возврата."""
        with self._lock:
            counters: dict[str, float] = {name: float(self._counts[name]) for name in _ADDITIVE_COUNTERS}
            broken = self._counts["broken_total"]
            failed = self._counts["files_failed"]
            files = self._counts["files_ok"] + failed
            links = self._counts["links_total"]
        counters["broken_ratio"] = broken / links if links else 0.0
        counters["error_rate"] = failed / files if files else 0.0
        counters["duration_sec"] = duration_sec
        counters["throughput_files_per_sec"] = files / duration_sec if duration_sec > 0 else 0.0
        exit_code = 1 if fail_on_broken and (broken > 0 or failed > 0) else 0
        return ScanSummary(counters=counters, duration_sec=duration_sec, exit_code=exit_code)

    def snapshot(self, task_qsize: int, result_qsize: int) -> ProgressSnapshot:
        """Срез для зоны 1 прогресса. Размеры очередей приходят снаружи: их знает оркестратор."""
        with self._lock:
            return ProgressSnapshot(
                repos_total=self._counts["repos_total"],
                repos_done=self._counts["repos_done"],
                md_found=self._counts["md_files_total"],
                parsed=self._counts["files_ok"] + self._counts["files_failed"],
                task_qsize=task_qsize,
                result_qsize=result_qsize,
                links=self._counts["links_total"],
                broken=self._counts["broken_total"],
            )

    def _add_link(self, kind: LinkKind, status: CheckStatus) -> None:
        """Учесть одну ссылку. Вызывается под уже взятым `self._lock`."""
        self._counts["links_total"] += 1
        self._counts[_LINKS_BY_KIND.get(kind, "links_unknown")] += 1
        if status is CheckStatus.TIMEOUT:
            self._counts["timeout_http"] += 1
        elif status is CheckStatus.BROKEN:
            bucket = _BROKEN_BY_KIND.get(kind)
            if bucket is not None:
                self._counts[bucket] += 1
        else:
            return
        self._counts["broken_total"] += 1
