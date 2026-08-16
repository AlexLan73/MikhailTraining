"""Тесты baseline-моделей (🚫 pytest, правило 04)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.runner import AssertionGroup, TestRunner  # noqa: E402
from core.models import MajorityClassifier, MeanRegressor, Model, ThresholdClassifier  # noqa: E402


class ModelsTests(TestRunner):
    def test_majority(self) -> AssertionGroup:
        g = AssertionGroup("models.majority")
        model = MajorityClassifier().fit([0, 1, 2, 3], [1, 1, 1, 0])
        g.add(model.majority == 1, "самый частый класс = 1")
        g.add(model.predict([9, 9]) == [1, 1], "предсказание = константа большинства")
        return g

    def test_mean_regressor(self) -> AssertionGroup:
        g = AssertionGroup("models.mean")
        model = MeanRegressor().fit([0, 1], [2.0, 4.0])
        g.add(abs((model.mean or 0.0) - 3.0) < 1e-12, "среднее = 3.0")
        g.add(model.predict([0]) == [3.0], "предсказание = среднее")
        return g

    def test_threshold_separable(self) -> AssertionGroup:
        g = AssertionGroup("models.threshold")
        x = [0.0, 0.1, 0.2, 5.0, 5.1, 5.2]
        y = [0, 0, 0, 1, 1, 1]
        model = ThresholdClassifier().fit(x, y)
        g.add(model.predict(x) == y, "разделимая выборка -> 100% на train")
        g.add(0.2 < (model.threshold or 0.0) <= 5.0, f"порог между облаками, получено {model.threshold}")
        return g

    def test_not_fitted_raises(self) -> AssertionGroup:
        g = AssertionGroup("models.not_fitted")
        for model in (MajorityClassifier(), MeanRegressor(), ThresholdClassifier()):
            try:
                model.predict([1.0])
                g.add(False, f"{type(model).__name__}: predict без fit должен падать")
            except RuntimeError:
                g.add(True, f"{type(model).__name__}: predict без fit -> RuntimeError")
        return g

    def test_protocol_conformance(self) -> AssertionGroup:
        g = AssertionGroup("models.protocol")
        for model in (MajorityClassifier(), MeanRegressor(), ThresholdClassifier()):
            g.add(isinstance(model, Model), f"{type(model).__name__} соответствует Model (LSP)")
        return g

    def test_inputs_not_mutated(self) -> AssertionGroup:
        g = AssertionGroup("models.purity")
        x = [1.0, 2.0, 3.0, 4.0]
        y = [0, 0, 1, 1]
        x_copy, y_copy = list(x), list(y)
        ThresholdClassifier().fit(x, y).predict(x)
        g.add(x == x_copy and y == y_copy, "fit/predict не мутируют входы")
        return g


if __name__ == "__main__":
    ModelsTests().run_all()
