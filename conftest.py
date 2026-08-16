"""Корневой conftest — общий для всех тестов pytest.

Пакет `mikhail-training` может быть не установлен (`pip install -e .`), а базовый каркас
работает на голом Python. Поэтому кладём корень репозитория в `sys.path` — тогда
`from core.metrics import ...` работает при запуске `pytest` из любого каталога.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
