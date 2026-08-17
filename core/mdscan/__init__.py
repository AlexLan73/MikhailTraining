"""Пакет `core.mdscan` — сканер Markdown-ссылок в git-репозиториях (ДЗ hw01).

Фасад пакета: наружу торчит контракт `Scanner`, его реализация `ScanOrchestrator`
и два value object'а — вход `ScanConfig` и выход `ScanSummary` (часть 2, §4).
Всё остальное — детали реализации, импортировать их извне не нужно.

```python
from core.mdscan import ScanConfig, ScanOrchestrator, Scanner

scanner: Scanner = ScanOrchestrator()
summary = scanner.scan(config)      # ScanSummary: счётчики, время, код возврата
```

Запуск из командной строки — `python -m core.mdscan <цель> [-поле:значение ...]`.
"""

from __future__ import annotations

from .config.scan_config import ScanConfig
from .models.scan_summary import ScanSummary
from .runtime.scan_orchestrator import ScanOrchestrator
from .scanner import Scanner

__all__ = ["ScanConfig", "ScanOrchestrator", "ScanSummary", "Scanner"]
