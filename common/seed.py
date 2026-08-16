"""Единая фиксация случайности — воспроизводимость экспериментов (правило 08).

Вызывать ОДИН раз в начале прогона (`HomeworkTask.run`), сид приходит снаружи (DI),
внутри `core/` собственного `random`-состояния быть не должно.
"""

from __future__ import annotations

import os
import random


def set_seed(seed: int, *, deterministic_torch: bool = True) -> int:
    """Зафиксировать `random`, `numpy` и `torch` (если установлены). Вернуть сид.

    numpy/torch — опциональные: базовые ДЗ работают и без них.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np
    except ImportError:
        pass
    else:
        np.random.seed(seed)

    try:
        import torch
    except ImportError:
        return seed

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic_torch:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    return seed
