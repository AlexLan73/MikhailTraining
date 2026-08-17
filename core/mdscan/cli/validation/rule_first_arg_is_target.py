"""V2 — если аргументы есть, первый обязан быть целью (закон CLI, пункты 2 и 3).

Здесь проверяется только форма: цель — не ключ `-поле:значение` и не пустая строка.
К какой из четырёх веток она относится, решает V5: до этого ещё не наложены
переопределения (`-source.kind:local` может изменить трактовку).
"""

from __future__ import annotations

import logging

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class FirstArgIsTargetRule:
    """Первый аргумент — цель: каталог, URL репозитория, URL организации или `yaml`."""

    MESSAGE = "первым аргументом должна быть цель: каталог, URL или слово yaml"

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Отсечь запуск вида `python -m core.mdscan -workers.parse:8`."""
        target = ctx.args.target
        if target is None:
            return ValidationResult(ok=True)
        if target.startswith("-") or not target.strip():
            _LOG.error("первый аргумент не является целью: %r", target)
            return ValidationResult(
                ok=False,
                exit_code=2,
                message=f"{self.MESSAGE}; получено: «{target}»",
            )
        return ValidationResult(ok=True)
