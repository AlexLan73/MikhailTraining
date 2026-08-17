"""Публичное API пакета `core.mdscan`: один вызов — один прогон (D18.5).

Наружу из пакета торчит ровно один контракт: «дай конфигурацию — получи итоги».
Всё остальное (очереди, потоки, чекеры, отчёт) — детали реализации, и потребитель
(`__main__`, `homework/hw01_mdlinks/task.py`) о них не знает: он зависит от
`Scanner`, а не от `ScanOrchestrator` (DIP, правило 09 п. 5).

Реализация — `core.mdscan.runtime.scan_orchestrator.ScanOrchestrator`.
"""

from __future__ import annotations

from typing import Protocol

from .config.scan_config import ScanConfig
from .models.scan_summary import ScanSummary


class Scanner(Protocol):
    """Сканер Markdown-ссылок: прогон целиком, от конфигурации до итогов."""

    def scan(self, config: ScanConfig) -> ScanSummary:
        """Выполнить прогон и вернуть итоги.

        Исключений наружу не выпускает: внутренняя ошибка становится
        `ScanSummary.exit_code == 3` с записью `CRITICAL` в лог (часть 2 §1.4).
        """
        ...
