"""Отрисовка прогресса через `rich` — используется, если библиотека установлена (D10)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TextIO

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from ..models.progress_snapshot import ProgressSnapshot
from .progress_view import format_status

# `rich` импортируется на уровне модуля намеренно: наличие библиотеки решает
# `ProgressFactory` (через `importlib.util.find_spec`), поэтому глушить здесь ImportError
# нечем и незачем — до импорта этого модуля дело дойдёт только при установленном `rich`.


class RichProgressView:
    """Реализация `ProgressView` поверх `rich.live.Live`.

    Блок «статус + сообщения» отдаётся `Live` как единая группа: библиотека сама
    перерисовывает его на месте, а `transient=True` стирает блок при остановке.
    """

    def __init__(self, stream: TextIO) -> None:
        self._console = Console(file=stream)
        self._live: Live | None = None

    def draw(self, snapshot: ProgressSnapshot, messages: Sequence[str]) -> None:
        """Перерисовать блок; при первом вызове поднимает `Live`."""
        group = Group(Text(format_status(snapshot)), *(Text(message) for message in messages))
        live = self._live
        if live is None:
            live = Live(group, console=self._console, transient=True)
            live.start()
            self._live = live
            return
        live.update(group, refresh=True)

    def clear(self) -> None:
        """Остановить `Live` — блок стирается; повторный вызов безопасен."""
        live = self._live
        if live is None:
            return
        self._live = None
        live.stop()
