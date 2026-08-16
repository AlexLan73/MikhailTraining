"""Метрики качества — ОДИН источник истины для всех ДЗ (правило 06)."""

from .classification import accuracy, confusion_matrix, f1_score, precision, recall
from .regression import mae, mse, r2_score, rmse

__all__ = [
    "accuracy",
    "confusion_matrix",
    "f1_score",
    "mae",
    "mse",
    "precision",
    "r2_score",
    "recall",
    "rmse",
]
