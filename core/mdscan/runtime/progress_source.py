"""Контракт зоны 1 прогресса: откуда рисующий поток берёт срез счётчиков."""

from __future__ import annotations

from typing import Protocol

from ..models.progress_snapshot import ProgressSnapshot


class ProgressSource(Protocol):
    """Источник среза счётчиков для строки статуса (D3.5, зона 1).

    Контрактом владеет T-11 (потребитель, правило DIP), реализует оркестратор (T-13)
    поверх `StatisticsCollector` и размеров очередей. Благодаря этому поток прогресса
    ничего не знает ни про конвейер, ни про статистику — только про один метод.
    """

    def snapshot(self) -> ProgressSnapshot:
        """Мгновенный срез счётчиков; вызывается из потока прогресса по таймеру."""
        ...
