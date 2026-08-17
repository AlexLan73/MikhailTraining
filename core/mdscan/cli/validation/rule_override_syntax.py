"""V3 — разбор `-поле:значение` и наложение их на черновик конфигурации.

Стоит **до** проверок каталогов (V9/V10) намеренно: переопределение может задавать сам
каталог (`-logging.dir:…`), и проверять надо уже новое значение (часть 2 §1.3, ревью 3).

Саму механику разбора выполняет `CliOverrideApplier` (T-03) — здесь только перевод его
исключений в код возврата 2: конфигурационная ошибка не должна уходить трейсбеком в лицо.
"""

from __future__ import annotations

import logging

from ...config.cli_override_applier import CliOverrideApplier
from ...errors import ConfigError
from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class OverrideSyntaxRule:
    """Каждый `-поле:значение` разобран, поле существует, тип приведён."""

    def __init__(self, applier: CliOverrideApplier | None = None) -> None:
        self._applier = applier or CliOverrideApplier()

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Наложить переопределения; неизвестное поле или неверный тип → код 2."""
        try:
            self._applier.apply(ctx.draft, list(ctx.args.overrides))
        except ConfigError as exc:
            _LOG.error("переопределения командной строки отклонены: %s", exc)
            return ValidationResult(ok=False, exit_code=2, message=str(exc))
        return ValidationResult(ok=True)
