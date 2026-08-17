"""Поток прогресса: статус по таймеру (зона 1) и строки-сообщения с TTL (зона 2), D3.5."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Final

from .progress_source import ProgressSource
from .progress_view import ProgressView

LOGGER: Final = logging.getLogger("core.mdscan.runtime.progress")

#: Сколько ждать завершения потока в `stop()`, секунды.
STOP_TIMEOUT_SEC: Final = 2.0
#: Нижняя граница периода перерисовки: защита от `wait(0)` и холостого прокручивания цикла.
MIN_INTERVAL_SEC: Final = 0.01


class ProgressReporter(threading.Thread):
    """Демон-поток вывода хода работы; одновременно реализует `Notifier` (T-01).

    Зона 1 — строка статуса, перерисовывается каждые `interval_sec` по срезу от
    `ProgressSource`. Зона 2 — до `message_lines` строк от любого модуля, каждая
    гаснет через `message_ttl_sec` (инвариант 16 части 2). Время берётся из `clock`
    (по умолчанию `time.monotonic`) — в тестах подставляется управляемое.

    На завершение прогона поток не влияет: он только читает счётчики, поэтому `daemon=True`.
    """

    def __init__(
        self,
        source: ProgressSource,
        view: ProgressView,
        interval_sec: float,
        message_lines: int,
        message_ttl_sec: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(name="progress", daemon=True)
        self._source = source
        self._view = view
        self._interval_sec = max(float(interval_sec), MIN_INTERVAL_SEC)
        self._message_ttl_sec = float(message_ttl_sec)
        self._clock = clock
        # maxlen делает вытеснение: новое сообщение выдавливает самое старое.
        self._messages: deque[tuple[str, float]] = deque(maxlen=max(0, message_lines))
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def show(self, text: str) -> None:
        """Зона 2: показать строку до истечения TTL. Потокобезопасно и никогда не бросает."""
        try:
            expires_at = self._clock() + self._message_ttl_sec
            with self._lock:
                self._messages.append((text, expires_at))
            LOGGER.debug("прогресс, зона 2: %s", text)
        except Exception:
            LOGGER.exception("сообщение прогресса не принято: %s", text)

    def tick(self) -> None:
        """Один такт отрисовки: срез счётчиков + живые сообщения → `view.draw`.

        Метод публичный намеренно: тест вызывает такт напрямую и не зависит от таймера.
        """
        snapshot = self._source.snapshot()
        self._view.draw(snapshot, self._live_messages())

    def run(self) -> None:
        """Цикл потока: такт сразу, дальше — каждые `interval_sec` до `stop()`."""
        LOGGER.debug("поток прогресса запущен, период %.3f с", self._interval_sec)
        self._safe_tick()
        while not self._stopped.wait(self._interval_sec):
            self._safe_tick()
        LOGGER.debug("поток прогресса завершён")

    def stop(self) -> None:
        """Погасить прогресс: остановить цикл, дождаться потока, стереть нарисованное."""
        self._stopped.set()
        if self.is_alive():
            self.join(timeout=STOP_TIMEOUT_SEC)
            if self.is_alive():
                LOGGER.error("поток прогресса не завершился за %.1f с", STOP_TIMEOUT_SEC)
        try:
            self._view.clear()
        except Exception:
            LOGGER.exception("не удалось стереть блок прогресса")

    def _safe_tick(self) -> None:
        """Такт под защитой: сбой отрисовки логируется, поток продолжает работу (правило 11)."""
        try:
            self.tick()
        except Exception:
            LOGGER.exception("сбой отрисовки прогресса — поток продолжает работу")

    def _live_messages(self) -> tuple[str, ...]:
        """Сообщения, у которых не истёк TTL; просроченные удаляются на месте."""
        now = self._clock()
        with self._lock:
            while self._messages and self._messages[0][1] <= now:
                self._messages.popleft()
            return tuple(text for text, _ in self._messages)
