"""Цепочка правил V1…V10 (Chain of Responsibility): первый не-`ok` останавливает прогон.

Порядок правил — закон (часть 2 §1.3) и меняться не может: переопределения
`-поле:значение` (V3) накладываются до проверок каталогов (V9/V10), а нормализация пути
(V4) — до проверок существования (V5…V8).

Справка (`-h` / `--help` / `-?` / нет аргументов) выполняет только V1…V3: переопределения
из командной строки должны попасть в печатаемую конфигурацию (колонка источника `c`),
но каталоги при этом создаваться не должны — запуск ничего не сканирует.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .rule import ValidationRule
from .rule_arg_count import ArgCountRule
from .rule_first_arg_is_target import FirstArgIsTargetRule
from .rule_git_repository import GitRepositoryRule
from .rule_output_dir import OutputDirRule
from .rule_override_syntax import OverrideSyntaxRule
from .rule_path_is_directory import PathIsDirectoryRule
from .rule_path_normalization import PathNormalizationRule
from .rule_path_readable import PathReadableRule
from .rule_target_kind import TargetKindRule
from .rule_write_permission import WritePermissionRule
from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class ValidationChain:
    """Последовательный прогон правил над одним контекстом."""

    #: Сколько первых правил (V1…V3) выполняется при запросе справки.
    HELP_RULES = 3

    def __init__(self, rules: Sequence[ValidationRule]) -> None:
        self._rules = tuple(rules)

    @classmethod
    def default(cls) -> ValidationChain:
        """Штатный состав V1…V10 в порядке части 2 §1.3 (T-13 список не дублирует)."""
        return cls(
            (
                ArgCountRule(),
                FirstArgIsTargetRule(),
                OverrideSyntaxRule(),
                PathNormalizationRule(),
                TargetKindRule(),
                PathIsDirectoryRule(),
                PathReadableRule(),
                GitRepositoryRule(),
                OutputDirRule(),
                WritePermissionRule(),
            )
        )

    def run(self, ctx: ValidationContext) -> ValidationResult:
        """Выполнить правила по порядку; первый не-`ok` останавливает цепочку."""
        for rule in self._rules_for(ctx):
            result = rule.validate(ctx)
            if not result.ok:
                _LOG.error("проверка %s не пройдена: %s", type(rule).__name__, result.message)
                return result
        return ValidationResult(ok=True)

    def _rules_for(self, ctx: ValidationContext) -> Sequence[ValidationRule]:
        if not ctx.args.help_requested:
            return self._rules
        _LOG.debug("запрошена справка — выполняются только первые %d правил", self.HELP_RULES)
        return self._rules[: self.HELP_RULES]
