"""Итоги прогона — то, что возвращает `Scanner.scan` и печатает консоль."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanSummary:
    """Value Object: счётчики, время и код возврата процесса.

    `counters` — плоский словарь чисел (`float`, чтобы влезали и доли секунд),
    одни и те же значения идут в лог, в отчёт и в метрики ДЗ: один источник истины.
    """

    counters: dict[str, float]
    duration_sec: float
    exit_code: int
