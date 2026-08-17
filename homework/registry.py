"""Контракт домашнего задания (Template Method) + реестр (Registry).

Новое ДЗ:
  1. пакет `homework/hwNN_<topic>/` с классом-наследником `HomeworkTask`;
  2. класс добавить в `_TASK_CLASSES` ниже;
  3. `python run_hw.py --list` покажет его.

См. `.claude/rules/06-homework-layout.md`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from common.seed import set_seed
from common.timer import Stopwatch
from core.config import Settings, default_settings
from core.data import DataContext


@dataclass(frozen=True)
class HomeworkContext:
    """Всё, что нужно заданию для работы (Value Object, инъекция снаружи)."""

    hw_id: str
    settings: Settings
    data: DataContext

    @property
    def seed(self) -> int:
        return self.settings.seed

    @property
    def out_dir(self) -> Path:
        return self.data.out_dir

    @property
    def data_dir(self) -> Path:
        return self.data.data_dir


@dataclass
class HomeworkReport:
    """Результат прогона одного ДЗ: метрики + время + произвольные заметки."""

    hw_id: str
    title: str
    metrics: dict[str, float] = field(default_factory=dict)
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "hw_id": self.hw_id,
            "title": self.title,
            "metrics": self.metrics,
            "seconds": round(self.seconds, 3),
            "notes": self.notes,
        }


class HomeworkTask(ABC):
    """Базовый класс задания. Наследник реализует только `solve`.

    `run` — шаблонный метод: фиксирует сид → замеряет время → зовёт `solve`
    → складывает метрики в отчёт и пишет `metrics.json` в `out/<hw_id>/`.
    """

    hw_id: str = ""
    title: str = ""

    def build_context(self, settings: Settings | None = None) -> HomeworkContext:
        cfg = settings or default_settings()
        return HomeworkContext(hw_id=self.hw_id, settings=cfg, data=DataContext(cfg.paths, self.hw_id))

    def run(self, ctx: HomeworkContext | None = None) -> HomeworkReport:
        context = ctx or self.build_context()
        set_seed(context.seed)

        report = HomeworkReport(hw_id=self.hw_id, title=self.title)
        with Stopwatch() as sw:
            report.metrics = self.solve(context)
        report.seconds = sw.seconds

        context.data.write_json("metrics.json", report.as_dict())
        return report

    @abstractmethod
    def solve(self, ctx: HomeworkContext) -> dict[str, float]:
        """Решение задания. Возвращает метрики: `{"accuracy": 0.93, ...}`."""


# ── Реестр ────────────────────────────────────────────────────────────────────
# Новое ДЗ добавляем сюда одной строкой.

from homework.hw00_intro import Hw00Intro  # noqa: E402 — импорт после определения базы
from homework.hw01_mdlinks import Hw01MdLinks  # noqa: E402 — импорт после определения базы

_TASK_CLASSES: list[type[HomeworkTask]] = [
    Hw00Intro,
    Hw01MdLinks,
]


def all_tasks() -> list[HomeworkTask]:
    """Все зарегистрированные задания, отсортированные по `hw_id`."""
    tasks = [cls() for cls in _TASK_CLASSES]
    ids = [t.hw_id for t in tasks]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"дублирующиеся hw_id в реестре: {sorted(duplicates)}")
    return sorted(tasks, key=lambda t: t.hw_id)


def get_task(hw_id: str) -> HomeworkTask:
    """Найти задание по идентификатору (`hw01`). Нет такого → понятная ошибка."""
    for task in all_tasks():
        if task.hw_id == hw_id:
            return task
    known = ", ".join(t.hw_id for t in all_tasks())
    raise KeyError(f"нет задания '{hw_id}'. Известные: {known}")
