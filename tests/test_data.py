"""Тесты слоя данных: детерминизм сплита + понятная ошибка при отсутствии датасета."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.runner import AssertionGroup, TestRunner  # noqa: E402
from core.config import ProjectPaths, default_settings  # noqa: E402
from core.data import DataContext, DatasetMissingError, train_test_split  # noqa: E402


class DataTests(TestRunner):
    def setup(self) -> None:
        self.items = list(range(100))

    def test_split_sizes(self) -> AssertionGroup:
        g = AssertionGroup("data.split.sizes")
        train, test = train_test_split(self.items, test_size=0.25, seed=42)
        g.add(len(test) == 25, f"test = 25, получено {len(test)}")
        g.add(len(train) == 75, f"train = 75, получено {len(train)}")
        g.add(sorted(train + test) == self.items, "объединение = исходная выборка без потерь")
        g.add(not set(train) & set(test), "train и test не пересекаются")
        return g

    def test_split_deterministic(self) -> AssertionGroup:
        g = AssertionGroup("data.split.determinism")
        a = train_test_split(self.items, seed=7)
        b = train_test_split(self.items, seed=7)
        c = train_test_split(self.items, seed=8)
        g.add(a == b, "один сид -> один результат")
        g.add(a != c, "разные сиды -> разные разбиения")
        return g

    def test_split_does_not_mutate(self) -> AssertionGroup:
        g = AssertionGroup("data.split.purity")
        original = list(self.items)
        train_test_split(self.items, seed=1)
        g.add(self.items == original, "вход не мутируется")
        return g

    def test_split_validation(self) -> AssertionGroup:
        g = AssertionGroup("data.split.validation")
        for bad in (0.0, 1.0, -0.3, 1.5):
            try:
                train_test_split(self.items, test_size=bad)
                g.add(False, f"test_size={bad} должен бросать ValueError")
            except ValueError:
                g.add(True, f"test_size={bad} -> ValueError")
        return g

    def test_missing_dataset_message(self) -> AssertionGroup:
        g = AssertionGroup("data.context.missing")
        paths = ProjectPaths()
        ctx = DataContext(paths, "hw_probe")
        try:
            ctx.require("нет_такого_файла.csv", source="https://example.org/dataset")
            g.add(False, "отсутствующий датасет должен бросать DatasetMissingError")
        except DatasetMissingError as exc:
            g.add("нет_такого_файла.csv" in str(exc), "в сообщении есть имя файла")
            g.add("example.org" in str(exc), "в сообщении есть источник для скачивания")
        return g

    def test_paths_are_relative_to_repo(self) -> AssertionGroup:
        g = AssertionGroup("data.paths")
        paths = default_settings().paths
        g.add(paths.root.exists(), "корень репозитория существует")
        g.add(paths.data.parent == paths.root, "data/ лежит в корне")
        g.add(paths.out.parent == paths.root, "out/ лежит в корне")
        g.add((paths.root / "run_hw.py").exists(), "корень определён верно (есть run_hw.py)")
        return g


if __name__ == "__main__":
    DataTests().run_all()
