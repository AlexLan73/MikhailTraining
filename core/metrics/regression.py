"""Метрики регрессии."""

from __future__ import annotations

import math
from collections.abc import Sequence


def _pairs(y_true: Sequence[float], y_pred: Sequence[float]) -> list[tuple[float, float]]:
    if len(y_true) != len(y_pred):
        raise ValueError(f"длины не совпадают: {len(y_true)} != {len(y_pred)}")
    if not y_true:
        raise ValueError("пустая выборка")
    return [(float(t), float(p)) for t, p in zip(y_true, y_pred, strict=True)]


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Средняя абсолютная ошибка: (1/N)·Σ|y − ŷ|."""
    data = _pairs(y_true, y_pred)
    return sum(abs(t - p) for t, p in data) / len(data)


def mse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Средний квадрат ошибки: (1/N)·Σ(y − ŷ)²."""
    data = _pairs(y_true, y_pred)
    return sum((t - p) ** 2 for t, p in data) / len(data)


def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Корень из MSE — в единицах целевой переменной."""
    return math.sqrt(mse(y_true, y_pred))


def r2_score(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Коэффициент детерминации: 1 − SS_res/SS_tot. Постоянный y_true → 0.0."""
    data = _pairs(y_true, y_pred)
    mean = sum(t for t, _ in data) / len(data)
    ss_tot = sum((t - mean) ** 2 for t, _ in data)
    ss_res = sum((t - p) ** 2 for t, p in data)
    return 1.0 - ss_res / ss_tot if ss_tot else 0.0
