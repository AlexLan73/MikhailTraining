"""Модели/алгоритмы, общие для нескольких ДЗ (Strategy)."""

from .base import Model
from .baseline import MajorityClassifier, MeanRegressor, ThresholdClassifier

__all__ = ["MajorityClassifier", "MeanRegressor", "Model", "ThresholdClassifier"]
