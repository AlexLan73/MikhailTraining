"""Отрисовка прогресса без внешних зависимостей: ANSI поверх обычного текстового потока."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, TextIO

from ..models.progress_snapshot import ProgressSnapshot
from .progress_view import format_status

#: Очистить строку от курсора до конца строки.
CLEAR_LINE: Final = "\x1b[K"
#: Очистить экран от курсора вниз — убирает «хвост», если строк стало меньше.
CLEAR_BELOW: Final = "\x1b[J"
#: Вернуть курсор в начало строки.
LINE_START: Final = "\r"


class PlainProgressView:
    """Реализация `ProgressView` на голом stdlib: `\r` + ANSI-очистка.

    Блок из строки статуса (зона 1) и строк-сообщений (зона 2) перерисовывается
    на месте: курсор поднимается к началу блока, старое стирается, новое пишется.
    Последняя строка выводится **без** перевода строки — иначе блок «уползал» бы вниз.
    """

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._drawn = 0

    def draw(self, snapshot: ProgressSnapshot, messages: Sequence[str]) -> None:
        """Перерисовать блок: строка статуса плюс строки-сообщения."""
        lines = [format_status(snapshot), *messages]
        body = "\n".join(f"{line}{CLEAR_LINE}" for line in lines)
        self._stream.write(f"{self._rewind()}{body}")
        self._stream.flush()
        self._drawn = len(lines)

    def clear(self) -> None:
        """Стереть блок целиком; повторный вызов безопасен (стирать уже нечего)."""
        if self._drawn == 0:
            return
        self._stream.write(self._rewind())
        self._stream.flush()
        self._drawn = 0

    def _rewind(self) -> str:
        """Последовательность «вернуть курсор к началу блока и стереть его»."""
        if self._drawn == 0:
            return ""
        up = f"\x1b[{self._drawn - 1}A" if self._drawn > 1 else ""
        return f"{LINE_START}{up}{CLEAR_BELOW}"
