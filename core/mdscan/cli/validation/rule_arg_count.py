"""V1 — позиционных аргументов ровно один или ни одного (часть 2 §1.3).

Второй позиционный почти всегда означает старую привычку «путь к логу вторым аргументом»,
поэтому текст ошибки сразу показывает, как это делается на самом деле: каталоги — обычные
поля конфигурации (`-logging.dir:` / `-report.dir:`), а не позиции.
"""

from __future__ import annotations

import logging

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class ArgCountRule:
    """Всё, что идёт после цели, обязано начинаться с `-`."""

    HINT = "каталоги задаются как -logging.dir:<путь> / -report.dir:<путь>"

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Найти лишний позиционный аргумент среди хвоста командной строки."""
        for argument in ctx.args.overrides:
            if not argument.startswith("-"):
                _LOG.error("лишний позиционный аргумент: %r", argument)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"лишний аргумент «{argument}»; {self.HINT}",
                )
        return ValidationResult(ok=True)
