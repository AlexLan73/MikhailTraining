"""Группировка расхода токенов: по агенту, по задаче, по модели."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from .models.token_totals import TokenTotals
from .models.token_usage import TokenUsage

_LOG = logging.getLogger("core.tokenstat")


class TokenAggregator:
    """Копит итоги в трёх разрезах и общий итог.

    Порядок ключей — порядок первого появления: отчёт получается детерминированным.
    """

    def __init__(self) -> None:
        self._by_agent: dict[str, TokenTotals] = {}
        self._by_task: dict[str, TokenTotals] = {}
        self._by_model: dict[str, TokenTotals] = {}
        self._task_of: dict[str, str] = {}
        self._models_of: dict[str, list[str]] = {}
        self._total = TokenTotals()

    def add(self, agent: str, task: str, usages: Iterable[TokenUsage]) -> None:
        """Учесть записи агента ``agent``, работавшего над таском ``task``."""
        self._task_of.setdefault(agent, task)
        self._models_of.setdefault(agent, [])
        self._by_agent.setdefault(agent, TokenTotals())
        self._by_task.setdefault(task, TokenTotals())
        for usage in usages:
            one = TokenTotals(
                requests=1,
                input=usage.input,
                output=usage.output,
                cache_creation=usage.cache_creation,
                cache_read=usage.cache_read,
                thinking=usage.thinking,
            )
            self._by_agent[agent] = self._by_agent[agent] + one
            self._by_task[task] = self._by_task[task] + one
            self._by_model[usage.model] = self._by_model.get(usage.model, TokenTotals()) + one
            self._total = self._total + one
            if usage.model and usage.model not in self._models_of[agent]:
                self._models_of[agent].append(usage.model)
        _LOG.debug("учтён агент %s (таск %s): %s", agent, task, self._by_agent[agent])

    @property
    def total(self) -> TokenTotals:
        """Общий итог по всем добавленным записям."""
        return self._total

    def by_agent(self) -> dict[str, TokenTotals]:
        """Итоги по агентам."""
        return dict(self._by_agent)

    def by_task(self) -> dict[str, TokenTotals]:
        """Итоги по таскам."""
        return dict(self._by_task)

    def by_model(self) -> dict[str, TokenTotals]:
        """Итоги по моделям."""
        return dict(self._by_model)

    def task_of(self, agent: str) -> str:
        """Таск агента; неизвестен → пустая строка."""
        return self._task_of.get(agent, "")

    def models_of(self, agent: str) -> tuple[str, ...]:
        """Модели, которыми работал агент, в порядке появления."""
        return tuple(self._models_of.get(agent, ()))
