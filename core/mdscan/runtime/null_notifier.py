"""Null Object для `Notifier`: прогресс выключен — вызовы ничего не стоят."""

from __future__ import annotations


class NullNotifier:
    """Пустая реализация `Notifier`.

    Нужна, чтобы в коде не появилось `if notifier is not None` — вместо ветвления
    подставляется объект, который просто ничего не делает (правило 09, Null Object).
    """

    def show(self, text: str) -> None:
        """Ничего не делает и никогда не бросает."""
