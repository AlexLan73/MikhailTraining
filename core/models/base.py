"""Единый контракт модели — все ДЗ говорят на одном языке (LSP, правило 05)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Model(Protocol):
    """Минимальный интерфейс обучаемой модели: `fit` → `predict`.

    Реализации не мутируют входные выборки и возвращают новый список предсказаний.
    """

    def fit(self, x: Sequence[Any], y: Sequence[Any]) -> Model:
        """Обучить на (x, y). Возвращает self — для цепочки `.fit(...).predict(...)`."""
        ...

    def predict(self, x: Sequence[Any]) -> list[Any]:
        """Предсказание для каждого объекта из x."""
        ...
