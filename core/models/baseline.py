"""Тривиальные baseline-модели — «пол», ниже которого решение не имеет смысла.

Любое ДЗ по обучению должно бить свой baseline; иначе результат не про модель,
а про перекос выборки.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any


class MajorityClassifier:
    """Всегда предсказывает самый частый класс обучающей выборки."""

    def __init__(self) -> None:
        self.majority: Any = None

    def fit(self, x: Sequence[Any], y: Sequence[Any]) -> MajorityClassifier:
        if not y:
            raise ValueError("пустая обучающая выборка")
        self.majority = Counter(y).most_common(1)[0][0]
        return self

    def predict(self, x: Sequence[Any]) -> list[Any]:
        if self.majority is None:
            raise RuntimeError("модель не обучена: вызови fit()")
        return [self.majority] * len(x)


class MeanRegressor:
    """Всегда предсказывает среднее целевой переменной."""

    def __init__(self) -> None:
        self.mean: float | None = None

    def fit(self, x: Sequence[Any], y: Sequence[float]) -> MeanRegressor:
        if not y:
            raise ValueError("пустая обучающая выборка")
        self.mean = sum(float(v) for v in y) / len(y)
        return self

    def predict(self, x: Sequence[Any]) -> list[float]:
        if self.mean is None:
            raise RuntimeError("модель не обучена: вызови fit()")
        return [self.mean] * len(x)


class ThresholdClassifier:
    """Одномерный порог: x >= threshold → `positive`, иначе `negative`.

    Порог подбирается перебором середин между соседними значениями обучающей выборки
    по максимуму accuracy (детерминированно, без случайности).
    """

    def __init__(self, positive: Any = 1, negative: Any = 0) -> None:
        self.positive = positive
        self.negative = negative
        self.threshold: float | None = None

    def fit(self, x: Sequence[float], y: Sequence[Any]) -> ThresholdClassifier:
        if len(x) != len(y):
            raise ValueError(f"длины не совпадают: {len(x)} != {len(y)}")
        if not x:
            raise ValueError("пустая обучающая выборка")

        values = sorted({float(v) for v in x})
        candidates = [values[0] - 1.0] + [
            (a + b) / 2 for a, b in zip(values, values[1:], strict=False)
        ]

        best_threshold, best_hits = candidates[0], -1
        for threshold in candidates:
            hits = sum(
                1
                for xi, yi in zip(x, y, strict=True)
                if (self.positive if float(xi) >= threshold else self.negative) == yi
            )
            if hits > best_hits:
                best_threshold, best_hits = threshold, hits

        self.threshold = best_threshold
        return self

    def predict(self, x: Sequence[float]) -> list[Any]:
        if self.threshold is None:
            raise RuntimeError("модель не обучена: вызови fit()")
        return [self.positive if float(v) >= self.threshold else self.negative for v in x]
