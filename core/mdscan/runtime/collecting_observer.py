"""Сбор результатов: единственный поток, который видит все `MdFileResult` прогона."""

from __future__ import annotations

import logging

from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.runtime.base_observer import BaseObserver
from core.mdscan.runtime.queues import ResultQueue
from core.mdscan.runtime.sentinels import END_RESULTS
from core.mdscan.runtime.statistics_collector import StatisticsCollector

logger = logging.getLogger("core.mdscan.runtime")

#: Имя потока-сборщика: попадает в лог и в проверку «наших потоков не осталось».
COLLECTOR_THREAD_NAME = "collector"


class CollectingObserver(BaseObserver):
    """Потребитель `ResultQueue`: копит результаты и кормит статистику.

    Отчёт и консоль **не строит** (инвариант 25) — это делает главный поток после
    `join()`, читая `results` и `summary()`. Иначе вывод мог бы начаться раньше,
    чем придёт последний результат.
    """

    def __init__(self, results_q: ResultQueue, stats: StatisticsCollector) -> None:
        super().__init__(results_q, END_RESULTS, COLLECTOR_THREAD_NAME)
        self.results: list[MdFileResult] = []
        self._stats = stats

    def on_item(self, result: MdFileResult) -> None:
        """Принять результат: сохранить и учесть. Сам объект не изменяется (D15.2)."""
        self.results.append(result)
        self._stats.add(result)

    def on_finish(self) -> None:
        """Итог потока в лог — теми же числами, что уйдут в отчёт (D2.1)."""
        failed = sum(1 for result in self.results if not result.ok)
        logger.info("collector завершён: файлов=%d с ошибкой=%d", len(self.results), failed)
