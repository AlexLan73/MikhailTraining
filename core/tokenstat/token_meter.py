"""Публичный контракт модуля: счётчик токенов за окно прогона."""

from __future__ import annotations

from typing import Protocol

from .models.token_totals import TokenTotals


class TokenMeter(Protocol):
    """Считает токены, потраченные между :meth:`start` и :meth:`stop`."""

    def start(self, label: str) -> None:
        """Открыть окно: запомнить смещение главного транскрипта и уже существующих агентов."""
        ...

    def mark(self, agent: str, task: str) -> None:
        """Привязать агента к таску вручную (запасной путь, если ярлыка ``TASK=`` в файле нет)."""
        ...

    def stop(self) -> None:
        """Закрыть окно и зафиксировать итоги."""
        ...

    @property
    def total(self) -> TokenTotals:
        """Суммарные токены окна (агенты + оркестрант)."""
        ...

    def by_agent(self) -> dict[str, TokenTotals]:
        """Итоги по каждому агенту; главный транскрипт — под именем оркестранта."""
        ...

    def report(self) -> str:
        """Markdown-отчёт: общий итог, таблица по агентам, свод «агенты» / «оркестрант»."""
        ...
