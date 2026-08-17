"""Базовый потребитель очереди: цикл, перехват ошибок и `task_done()` — один раз на все.

Template Method (D15.1): наследник пишет только `on_item` — что делать с элементом.
Всё, из-за чего конвейеры виснут и теряют данные, живёт здесь и потому написано
однажды: выход **только** по сентинелу (а не по «пустой очереди»), `task_done()`
в `finally` и на сентинел тоже (инварианты 5, 18–19), исключение элемента не
убивает поток (D2.1).
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("core.mdscan.runtime")


class BaseObserver(threading.Thread, ABC):
    """Поток-потребитель одной очереди с одним сентинелом.

    Очередь и сентинел приходят через конструктор (DI, D2): глобальной шины нет,
    один и тот же класс обслуживает и `TaskQueue`, и `ResultQueue`.
    `daemon=False` намеренно: поток обязан завершиться сам, по сентинелу, —
    демон был бы убит на выходе интерпретатора вместе с недоделанной работой.
    """

    def __init__(self, q: queue.Queue[Any], sentinel: object, name: str) -> None:
        super().__init__(name=name, daemon=False)
        self._queue = q
        self._sentinel = sentinel

    def run(self) -> None:
        """Цикл потребителя: `get` → `on_item` → `task_done`; выход по сентинелу."""
        logger.debug("поток %s запущен", self.name)
        while True:
            item = self._queue.get()
            if item is self._sentinel:
                self._queue.task_done()
                self._finish()
                return
            try:
                self.on_item(item)
            except Exception as exc:  # noqa: BLE001 — ошибка элемента не роняет поток (D2.1)
                self.on_error(exc)
            finally:
                self._queue.task_done()

    @abstractmethod
    def on_item(self, item: Any, /) -> None:
        """Обработать один элемент. Единственное, что пишет наследник.

        Аргумент позиционный: наследник называет его по существу (`task`, `result`).
        """

    def on_error(self, exc: Exception) -> None:
        """Ошибка элемента: лог `ERROR` с трейсом, поток продолжает работу (D2.1)."""
        logger.exception("поток %s: необработанная ошибка элемента: %s", self.name, exc)

    def on_finish(self) -> None:
        """Хук завершения: вызывается один раз, после сентинела. По умолчанию — ничего."""

    def _finish(self) -> None:
        """`on_finish` под защитой: его падение не должно оставить поток «живым трупом»."""
        logger.debug("поток %s получил сентинел, завершается", self.name)
        try:
            self.on_finish()
        except Exception as exc:  # noqa: BLE001 — гасим, поток всё равно выходит
            self.on_error(exc)
