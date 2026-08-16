"""Визуализация (Strategy + Pure Fabrication для записи файлов).

matplotlib — **опциональная** зависимость: без неё ДЗ считает метрики, но не рисует.
"""

from .writer import FigureWriter, matplotlib_available

__all__ = ["FigureWriter", "matplotlib_available"]
