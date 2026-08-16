"""Простой таймер прогона (без внешних зависимостей)."""

from __future__ import annotations

import time
from types import TracebackType


class Stopwatch:
    """Контекстный менеджер: измеряет время блока в секундах.

        with Stopwatch() as sw:
            train(...)
        print(sw.seconds)
    """

    def __init__(self) -> None:
        self._start = 0.0
        self.seconds = 0.0

    def __enter__(self) -> Stopwatch:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.seconds = time.perf_counter() - self._start
