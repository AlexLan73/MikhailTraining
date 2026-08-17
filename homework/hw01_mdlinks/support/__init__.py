"""Вспомогательный код ДЗ hw01: генератор тестовых деревьев Markdown и его ожидания.

Живёт в пакете ДЗ (а не в `tests/`), потому что зовут его двое: pytest (фикстура
`reference_tree`) и `python run_hw.py hw01` — из продуктивного кода импорт из `tests/`
невозможен (спека разработки §2.6).

Пакет `homework.hw01_mdlinks` — namespace-пакет: собственный `__init__.py` у него
появится вместе с самим ДЗ (T-14).
"""

from __future__ import annotations

from .expectations import (
    FILES_TOTAL,
    REFERENCE_BROKEN,
    REFERENCE_EXPECTATIONS,
    REFERENCE_LINKS,
    Expectations,
    ReferenceTree,
)
from .fixture_tree_builder import REFERENCE_FILES, FixtureTreeBuilder

__all__ = [
    "FILES_TOTAL",
    "REFERENCE_BROKEN",
    "REFERENCE_EXPECTATIONS",
    "REFERENCE_FILES",
    "REFERENCE_LINKS",
    "Expectations",
    "FixtureTreeBuilder",
    "ReferenceTree",
]
