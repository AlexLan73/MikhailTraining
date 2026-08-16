"""Тесты реестра ДЗ: уникальность id, заполненность полей, поиск."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.runner import AssertionGroup, TestRunner  # noqa: E402
from homework.registry import HomeworkTask, all_tasks, get_task  # noqa: E402


class HomeworkRegistryTests(TestRunner):
    def setup(self) -> None:
        self.tasks = all_tasks()

    def test_registry_not_empty(self) -> AssertionGroup:
        g = AssertionGroup("homework.registry.not_empty")
        g.add(bool(self.tasks), "в реестре есть хотя бы одно задание")
        return g

    def test_ids_unique_and_sorted(self) -> AssertionGroup:
        g = AssertionGroup("homework.registry.ids")
        ids = [t.hw_id for t in self.tasks]
        g.add(len(ids) == len(set(ids)), f"hw_id уникальны, получено {ids}")
        g.add(ids == sorted(ids), "задания отсортированы по hw_id")
        return g

    def test_fields_filled(self) -> AssertionGroup:
        g = AssertionGroup("homework.registry.fields")
        for task in self.tasks:
            g.add(isinstance(task, HomeworkTask), f"{type(task).__name__} наследует HomeworkTask")
            g.add(task.hw_id.startswith("hw"), f"{type(task).__name__}: hw_id вида hwNN")
            g.add(bool(task.title), f"{task.hw_id}: заголовок заполнен")
        return g

    def test_get_task(self) -> AssertionGroup:
        g = AssertionGroup("homework.registry.get")
        first = self.tasks[0]
        g.add(get_task(first.hw_id).hw_id == first.hw_id, "поиск по id возвращает то задание")
        try:
            get_task("hw999")
            g.add(False, "неизвестный id должен бросать KeyError")
        except KeyError as exc:
            g.add("hw999" in str(exc), "в сообщении есть запрошенный id")
        return g

    def test_package_exists_for_each_task(self) -> AssertionGroup:
        g = AssertionGroup("homework.registry.packages")
        root = Path(__file__).resolve().parents[1] / "homework"
        for task in self.tasks:
            packages = list(root.glob(f"{task.hw_id}_*"))
            g.add(bool(packages), f"{task.hw_id}: есть пакет homework/{task.hw_id}_*")
            for pkg in packages:
                g.add((pkg / "README.md").exists(), f"{pkg.name}: есть README.md с условием")
        return g


if __name__ == "__main__":
    HomeworkRegistryTests().run_all()
