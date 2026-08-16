"""Тесты образца hw00 — сквозной прогон каркаса."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.runner import AssertionGroup, TestRunner  # noqa: E402
from homework.hw00_intro.task import Hw00Intro, make_toy_dataset  # noqa: E402


class Hw00Tests(TestRunner):
    def setup(self) -> None:
        self.task = Hw00Intro()

    def test_toy_dataset_deterministic(self) -> AssertionGroup:
        g = AssertionGroup("hw00.dataset")
        a = make_toy_dataset(50, seed=42)
        b = make_toy_dataset(50, seed=42)
        c = make_toy_dataset(50, seed=1)
        g.add(a == b, "один сид -> одинаковый датасет")
        g.add(a != c, "разные сиды -> разные датасеты")
        g.add(len(a) == 50, "размер выборки соблюдён")
        g.add(sorted({label for _, label in a}) == [0, 1], "два класса: 0 и 1")
        return g

    def test_run_produces_metrics(self) -> AssertionGroup:
        g = AssertionGroup("hw00.run")
        report = self.task.run()
        m = report.metrics
        g.add(report.hw_id == "hw00", "id отчёта = hw00")
        g.add({"accuracy_baseline", "accuracy_model", "f1_model"} <= set(m), "ключевые метрики есть")
        g.add(0.0 <= m["accuracy_model"] <= 1.0, "accuracy в [0, 1]")
        g.add(m["accuracy_model"] > m["accuracy_baseline"], "модель бьёт baseline")
        g.add(m["accuracy_model"] > 0.75, f"разделимые облака -> accuracy > 0.75, факт {m['accuracy_model']:.3f}")
        g.add(0.5 < m["threshold"] < 1.5, f"порог около середины (0..2), факт {m['threshold']:.3f}")
        return g

    def test_artifacts_written(self) -> AssertionGroup:
        g = AssertionGroup("hw00.artifacts")
        ctx = self.task.build_context()
        self.task.run(ctx)
        g.add((ctx.out_dir / "metrics.json").exists(), "metrics.json записан в out/hw00/")
        g.add((ctx.out_dir / "predictions.json").exists(), "predictions.json записан в out/hw00/")
        return g

    def test_run_reproducible(self) -> AssertionGroup:
        g = AssertionGroup("hw00.reproducible")
        first = self.task.run().metrics
        second = Hw00Intro().run().metrics
        g.add(first == second, "повторный прогон с тем же сидом даёт те же метрики")
        return g


if __name__ == "__main__":
    Hw00Tests().run_all()
