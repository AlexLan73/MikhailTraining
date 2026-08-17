"""Срез счётчиков для зоны 1 прогресса."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    """Мгновенный снимок состояния прогона: читает поток прогресса, отдаёт оркестратор.

    Неизменяем намеренно: снимок пересекает границу потоков, а рисующий поток
    не должен увидеть «полуобновлённые» счётчики.
    """

    repos_total: int
    repos_done: int
    md_found: int
    parsed: int
    task_qsize: int
    result_qsize: int
    links: int
    broken: int
