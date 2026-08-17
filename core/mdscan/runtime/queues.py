"""Типы очередей конвейера: два псевдонима над `queue.Queue`.

Наследника от `Queue` намеренно нет: своей логики у очередей конвейера ноль,
потокобезопасность даёт сама `queue.Queue` (D2), а лишний класс пришлось бы
подменять в тестах. Псевдоним же даёт то единственное, чего не хватает, —
имя и проверяемый `mypy` состав элементов: в очереди либо данные, либо сентинел.
"""

from __future__ import annotations

import queue
from typing import TypeAlias

from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.md_task import MdTask
from core.mdscan.runtime.sentinels import _Sentinel

#: Стадия 1 → стадия 2: задачи разбора плюс `END_DISCOVERY` (по одному на worker).
TaskQueue: TypeAlias = queue.Queue[MdTask | _Sentinel]

#: Стадия 2 → вывод: готовые результаты плюс `END_RESULTS` (ровно один).
ResultQueue: TypeAlias = queue.Queue[MdFileResult | _Sentinel]
