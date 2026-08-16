"""Метрики классификации (бинарной и многоклассовой).

Реализация на стандартной библиотеке: принимает любые последовательности меток
(списки, numpy-массивы — итерируются одинаково), ничего не мутирует.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _check_same_length(y_true: Sequence[Any], y_pred: Sequence[Any]) -> None:
    if len(y_true) != len(y_pred):
        raise ValueError(f"длины не совпадают: {len(y_true)} != {len(y_pred)}")
    if not y_true:
        raise ValueError("пустая выборка")


def accuracy(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    """Доля правильных ответов: (TP + TN) / N."""
    _check_same_length(y_true, y_pred)
    hits = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)
    return hits / len(y_true)


def confusion_matrix(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
) -> tuple[list[Any], list[list[int]]]:
    """Матрица ошибок. Возвращает (labels, matrix), где matrix[i][j] = истина i, предсказано j."""
    _check_same_length(y_true, y_pred)
    labels = sorted({*y_true, *y_pred}, key=repr)
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred, strict=True):
        matrix[index[t]][index[p]] += 1
    return labels, matrix


def precision(y_true: Sequence[Any], y_pred: Sequence[Any], positive: Any = 1) -> float:
    """TP / (TP + FP). Нет предсказанных положительных → 0.0."""
    _check_same_length(y_true, y_pred)
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if p == positive and t == positive)
    predicted_positive = sum(1 for p in y_pred if p == positive)
    return tp / predicted_positive if predicted_positive else 0.0


def recall(y_true: Sequence[Any], y_pred: Sequence[Any], positive: Any = 1) -> float:
    """TP / (TP + FN). Нет истинных положительных → 0.0."""
    _check_same_length(y_true, y_pred)
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if p == positive and t == positive)
    actual_positive = sum(1 for t in y_true if t == positive)
    return tp / actual_positive if actual_positive else 0.0


def f1_score(y_true: Sequence[Any], y_pred: Sequence[Any], positive: Any = 1) -> float:
    """Гармоническое среднее precision и recall: 2PR / (P + R)."""
    p = precision(y_true, y_pred, positive)
    r = recall(y_true, y_pred, positive)
    return 2 * p * r / (p + r) if (p + r) else 0.0
