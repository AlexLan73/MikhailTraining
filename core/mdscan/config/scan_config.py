"""Неизменяемая конфигурация прогона: `ScanConfig` и её секции.

Модуль конфигурации — исключение из правила «один класс = один файл»
(`.claude/rules/09-oop-design.md` п. 2): секции бессмысленны по отдельности и меняются
всегда вместе. Все секции `frozen=True, slots=True` — конфигурацию читают все потоки,
после сборки она не меняется (D15.2).

Собирается **только** через `ScanConfig.from_draft(draft)`: единственная точка, где
черновик фазы 0 превращается в неизменяемый объект (списки yaml → кортежи).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from ..enums.source_kind import SourceKind
from ..errors import ConfigError
from .config_draft import ConfigDraft


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """Блок `source`: что сканируем и как получаем список репозиториев (часть 2, §2.0)."""

    target: str
    repositories: tuple[str, ...]
    kind: str
    discovery: str
    auth: str
    visibility: str
    include_forks: bool
    include_archived: bool
    page_size: int
    clone_dir: str
    clone_depth: int
    keep_clones: bool
    targets_resolved: tuple[tuple[str, SourceKind], ...] = ()


@dataclass(frozen=True, slots=True)
class ScanSection:
    """Блок `scan`: что считаем Markdown и куда заглядываем внутри репозитория."""

    include_nested_repos: bool
    md_extensions: tuple[str, ...]
    respect_gitignore: bool


@dataclass(frozen=True, slots=True)
class WorkersConfig:
    """Блок `workers`: размеры двух пулов потоков."""

    discover: int
    parse: int


@dataclass(frozen=True, slots=True)
class ParserConfig:
    """Блок `parser`: пресет и плагины markdown-it-py."""

    preset: str
    plugins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChecksConfig:
    """Блок `checks`: какие проверки ссылок включены."""

    local: bool
    anchors: bool


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Блок `http`: проверка внешних ссылок (семафор, таймаут, кэш, User-Agent)."""

    enabled: bool
    timeout_ms: int
    workers: int
    method: str
    cache: bool
    user_agent: str


@dataclass(frozen=True, slots=True)
class ProgressConfig:
    """Блок `progress`: две зоны вывода хода работы в stderr."""

    enabled: bool
    interval_sec: float
    style: str
    message_lines: int
    message_ttl_sec: float


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Блок `logging`: файл лога (имя формируется по метке времени прогона)."""

    enabled: bool
    level: str
    dir: str


@dataclass(frozen=True, slots=True)
class ReportConfig:
    """Блок `report`: каталог и заголовок итогового Markdown-отчёта."""

    dir: str
    title: str
    console: bool = True  # 🔧 р5: печатать ли сводку в stdout


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Блок `run`: поведение прогона (код возврата при битых ссылках)."""

    fail_on_broken: bool


@dataclass(frozen=True, slots=True)
class ScanConfig:
    """Конфигурация прогона целиком; собирается один раз и дальше не меняется."""

    source: SourceConfig
    scan: ScanSection
    workers: WorkersConfig
    parser: ParserConfig
    checks: ChecksConfig
    http: HttpConfig
    progress: ProgressConfig
    logging: LoggingConfig
    report: ReportConfig
    run: RunConfig

    @classmethod
    def from_draft(cls, draft: ConfigDraft) -> ScanConfig:
        """Единственная точка сборки: черновик фазы 0 → неизменяемая конфигурация."""
        data = draft.data
        try:
            source = data["source"]
            scan = data["scan"]
            workers = data["workers"]
            parser = data["parser"]
            checks = data["checks"]
            http = data["http"]
            progress = data["progress"]
            log = data["logging"]
            report = data["report"]
            run = data["run"]
            return cls(
                source=SourceConfig(
                    target=str(source["target"]),
                    repositories=_as_str_tuple(source["repositories"]),
                    kind=str(source["kind"]),
                    discovery=str(source["discovery"]),
                    auth=str(source["auth"]),
                    visibility=str(source["visibility"]),
                    include_forks=bool(source["include_forks"]),
                    include_archived=bool(source["include_archived"]),
                    page_size=int(source["page_size"]),
                    clone_dir=str(source["clone_dir"]),
                    clone_depth=int(source["clone_depth"]),
                    keep_clones=bool(source["keep_clones"]),
                    targets_resolved=_as_targets(source.get("targets_resolved", ())),
                ),
                scan=ScanSection(
                    include_nested_repos=bool(scan["include_nested_repos"]),
                    md_extensions=_as_str_tuple(scan["md_extensions"]),
                    respect_gitignore=bool(scan["respect_gitignore"]),
                ),
                workers=WorkersConfig(
                    discover=int(workers["discover"]),
                    parse=int(workers["parse"]),
                ),
                parser=ParserConfig(
                    preset=str(parser["preset"]),
                    plugins=_as_str_tuple(parser["plugins"]),
                ),
                checks=ChecksConfig(
                    local=bool(checks["local"]),
                    anchors=bool(checks["anchors"]),
                ),
                http=HttpConfig(
                    enabled=bool(http["enabled"]),
                    timeout_ms=int(http["timeout_ms"]),
                    workers=int(http["workers"]),
                    method=str(http["method"]),
                    cache=bool(http["cache"]),
                    user_agent=str(http["user_agent"]),
                ),
                progress=ProgressConfig(
                    enabled=bool(progress["enabled"]),
                    interval_sec=float(progress["interval_sec"]),
                    style=str(progress["style"]),
                    message_lines=int(progress["message_lines"]),
                    message_ttl_sec=float(progress["message_ttl_sec"]),
                ),
                logging=LoggingConfig(
                    enabled=bool(log["enabled"]),
                    level=str(log["level"]),
                    dir=str(log["dir"]),
                ),
                report=ReportConfig(
                    dir=str(report["dir"]),
                    title=str(report["title"]),
                    console=bool(report.get("console", True)),
                ),
                run=RunConfig(fail_on_broken=bool(run["fail_on_broken"])),
            )
        except KeyError as exc:
            raise ConfigError(f"в конфигурации нет обязательного поля: {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"недопустимое значение в конфигурации: {exc}") from exc


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    """Список из yaml → кортеж строк (конфигурация неизменяема)."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    raise ConfigError(f"ожидался список значений, получено: {value!r}")


def _as_targets(value: Any) -> tuple[tuple[str, SourceKind], ...]:
    """`[(адрес, вид), …]` от правила V5 → кортеж пар с `SourceKind`."""
    if not value:
        return ()
    resolved: list[tuple[str, SourceKind]] = []
    for item in value:
        if isinstance(item, str) or not isinstance(item, Sequence) or len(item) != 2:
            raise ConfigError(f"source.targets_resolved: ожидалась пара (адрес, вид), получено: {item!r}")
        address, kind = item
        resolved.append((str(address), kind if isinstance(kind, SourceKind) else SourceKind(str(kind))))
    return tuple(resolved)
