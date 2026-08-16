"""Детерминированное разбиение выборки (правило 08: сплит воспроизводим по сиду)."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def train_test_split(
    items: Sequence[T],
    *,
    test_size: float = 0.25,
    seed: int = 42,
) -> tuple[list[T], list[T]]:
    """Перемешать копию `items` локальным ГПСЧ и разрезать на train/test.

    Локальный `random.Random(seed)` — глобальное состояние не трогаем, результат
    зависит ТОЛЬКО от сида (одинаков между запусками и платформами).
    Вход не мутируется.
    """
    if not 0.0 < test_size < 1.0:
        raise ValueError(f"test_size должен быть в (0, 1), получено {test_size}")

    pool = list(items)
    random.Random(seed).shuffle(pool)
    n_test = max(1, round(len(pool) * test_size)) if pool else 0
    return pool[n_test:], pool[:n_test]
