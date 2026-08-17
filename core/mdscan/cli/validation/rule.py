"""Контракт одного правила проверки командной строки (Chain of Responsibility).

Контрактом владеет **потребитель** цепочки (T-05), реализуют его десять классов
`rule_*.py`; Composition Root (T-13) собирает список и ничего о конкретных классах
не знает, кроме порядка — а порядок задан частью 2 §1.3 и меняться не может.
"""

from __future__ import annotations

from typing import Protocol

from .validation_context import ValidationContext
from .validation_result import ValidationResult


class ValidationRule(Protocol):
    """Одна проверка: смотрит контекст, при необходимости дополняет его, выносит решение."""

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Вернуть `ok=True`, если проверка пройдена; иначе — код возврата и текст."""
        ...
