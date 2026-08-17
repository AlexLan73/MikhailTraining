"""V6 — локальная цель обязана быть каталогом; путь к `.git` поднимается к родителю.

Проверка нужна даже после V5: при `-source.kind:local` детекция не выполняется вовсе,
и «локальной» может оказаться опечатка в пути. Отдельный случай — перетаскивание в
консоль каталога `.git`: сканировать его бессмысленно, но и ошибкой это не является,
поэтому цель молча заменяется на родителя (часть 2 §1.3).
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...config.config_draft import SOURCE_CMDLINE
from ...enums.source_kind import SourceKind
from .validation_context import TARGETS_RESOLVED, ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")

_GIT_DIR = ".git"


class PathIsDirectoryRule:
    """Каждая цель вида `LOCAL` существует и является каталогом."""

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Заменить `.git` на родителя; не каталог → код 2."""
        resolved = list(ctx.resolved_targets)
        changed = False
        for index, (address, kind) in enumerate(resolved):
            if kind is not SourceKind.LOCAL:
                continue
            path = Path(address)
            if path.name == _GIT_DIR and path.parent.is_dir():
                path = path.parent
                resolved[index] = (str(path), kind)
                changed = True
                _LOG.info("цель указывала на %s, поднялись к репозиторию: %s", _GIT_DIR, path)
            if not path.is_dir():
                _LOG.error("локальная цель не является каталогом: %s", path)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"локальная цель «{path}» не существует или не является каталогом",
                )
        if changed:
            ctx.draft.assign(TARGETS_RESOLVED, resolved, SOURCE_CMDLINE)
            if not ctx.yaml_branch:
                ctx.draft.assign("source.target", resolved[0][0], SOURCE_CMDLINE)
        return ValidationResult(ok=True)
