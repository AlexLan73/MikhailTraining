"""V5 — классификация целей: каталог · репозиторий · организация (инвариант 23).

Вид цели определяется **один раз, здесь**, и записывается в черновик
(`source.targets_resolved`); `SourceFactory` (T-08) его только читает и второй детекции
не делает — иначе появилось бы два источника истины и они разошлись бы (правило 07).

Что классифицируется:

* обычная цель — первый аргумент CLI (нормализованный путь из V4 либо URL как есть);
* цель `yaml` — `source.target` (если не пуст) **плюс** весь `source.repositories`;
  пусты оба → «цель не задана», код 2 (часть 2 §2.0).

`source.kind` не `auto` снимает детекцию целиком: человек уже сказал, как трактовать
адрес (например каталог с именем `yaml` → `-source.kind:local`).
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...config.config_draft import SOURCE_CMDLINE, ConfigDraft
from ...enums.source_kind import SourceKind
from .validation_context import TARGETS_RESOLVED, URL_MARKERS, ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class TargetKindRule:
    """Определяет `SourceKind` каждой цели и пишет результат в черновик конфигурации."""

    NO_TARGET = "цель не задана: заполни source.target или source.repositories в mdscan.yaml"
    UNKNOWN = "не удалось определить вид цели «{address}»: ожидался существующий каталог, URL репозитория или URL организации"

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Разложить все цели на пары «адрес → вид»; ни одна ветка не подошла → код 2."""
        raw_kind = str(ctx.draft.value_at("source.kind")).strip().lower()
        try:
            forced = None if raw_kind in ("", "auto") else SourceKind(raw_kind)
        except ValueError:
            _LOG.error("недопустимое значение source.kind: %r", raw_kind)
            return ValidationResult(
                ok=False,
                exit_code=2,
                message=f"source.kind: ожидалось auto|local|remote_repo|github_org, получено «{raw_kind}»",
            )
        addresses = self._addresses(ctx)
        if not addresses:
            _LOG.error("цель не задана: source.target и source.repositories пусты")
            return ValidationResult(ok=False, exit_code=2, message=self.NO_TARGET)
        resolved: list[tuple[str, SourceKind]] = []
        for address in addresses:
            kind = forced or self._classify(address)
            if kind is None:
                _LOG.error("вид цели не определён: %r", address)
                return ValidationResult(
                    ok=False, exit_code=2, message=self.UNKNOWN.format(address=address)
                )
            resolved.append((self._normalized(address, kind), kind))
        self._store(ctx, resolved)
        return ValidationResult(ok=True)

    def _addresses(self, ctx: ValidationContext) -> list[str]:
        if ctx.yaml_branch:
            return self._configured(ctx.draft)
        if ctx.target_path is not None:
            return [str(ctx.target_path)]
        return [ctx.args.target] if ctx.args.target else []

    def _configured(self, draft: ConfigDraft) -> list[str]:
        target = str(draft.value_at("source.target")).strip()
        repositories = [str(item).strip() for item in draft.value_at("source.repositories")]
        return [address for address in [target, *repositories] if address]

    def _store(self, ctx: ValidationContext, resolved: list[tuple[str, SourceKind]]) -> None:
        ctx.draft.assign(TARGETS_RESOLVED, resolved, SOURCE_CMDLINE)
        if not ctx.yaml_branch:
            ctx.draft.assign("source.target", resolved[0][0], SOURCE_CMDLINE)
        _LOG.info(
            "цели определены: %s",
            ", ".join(f"{address} ({kind.value})" for address, kind in resolved),
        )

    def _classify(self, address: str) -> SourceKind | None:
        if any(mark in address for mark in URL_MARKERS):
            return self._url_kind(address)
        try:
            return SourceKind.LOCAL if Path(address).expanduser().is_dir() else None
        except (OSError, ValueError):
            _LOG.warning("адрес не похож ни на путь, ни на URL: %r", address)
            return None

    def _url_kind(self, address: str) -> SourceKind | None:
        if address.startswith("git@"):
            _, _, tail = address.partition(":")
            return SourceKind.REMOTE_REPO if len(self._segments(tail)) >= 2 else None
        _, _, rest = address.partition("://")
        host, _, tail = rest.partition("/")
        if not host:
            return None
        segments = self._segments(tail)
        if address.rstrip("/").endswith(".git") or len(segments) >= 2:
            return SourceKind.REMOTE_REPO
        return SourceKind.GITHUB_ORG if len(segments) == 1 else None

    def _segments(self, text: str) -> list[str]:
        return [part for part in text.split("/") if part]

    def _normalized(self, address: str, kind: SourceKind) -> str:
        if kind is not SourceKind.LOCAL:
            return address
        try:
            return str(Path(address).expanduser().resolve())
        except (OSError, ValueError):
            return address
