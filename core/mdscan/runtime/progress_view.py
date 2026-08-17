"""Контракт отрисовки прогресса (Strategy, D10) и общий формат строки зоны 1."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Protocol

from ..models.progress_snapshot import ProgressSnapshot

#: Шаблон строки статуса (зона 1, D3.5). Единственный источник формата: обе реализации
#: `ProgressView` зовут `format_status`, а не собирают строку сами (правило 07).
STATUS_TEMPLATE: Final = (
    "repos {repos_done}/{repos_total} · md {md_found} · parsed {parsed}"
    " · queue task={task_qsize} result={result_qsize} · links {links} · broken {broken}"
)


def format_status(snapshot: ProgressSnapshot) -> str:
    """Собрать строку зоны 1 из среза счётчиков.

    Свободная функция намеренно: формат общий для `PlainProgressView` и `RichProgressView`,
    а дублировать его в двух классах запрещает правило 07 («один источник истины»).
    """
    return STATUS_TEMPLATE.format(
        repos_done=snapshot.repos_done,
        repos_total=snapshot.repos_total,
        md_found=snapshot.md_found,
        parsed=snapshot.parsed,
        task_qsize=snapshot.task_qsize,
        result_qsize=snapshot.result_qsize,
        links=snapshot.links,
        broken=snapshot.broken,
    )


class ProgressView(Protocol):
    """Куда и как рисуется прогресс: `rich` или ANSI-строка — за одним интерфейсом.

    Обе реализации пишут **только** в переданный поток (по умолчанию `stderr`),
    в `stdout` не пишет никто: там финальные таблицы и отчёт (D3.5).
    """

    def draw(self, snapshot: ProgressSnapshot, messages: Sequence[str]) -> None:
        """Перерисовать зону 1 (статус) и зону 2 (строки-сообщения) на месте."""
        ...

    def clear(self) -> None:
        """Стереть всё нарисованное: экран возвращается в исходное состояние."""
        ...
