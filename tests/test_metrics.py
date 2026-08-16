"""Тесты метрик — сверка с ручным счётом (🚫 pytest, правило 04)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.runner import AssertionGroup, TestRunner  # noqa: E402
from core.metrics import (  # noqa: E402
    accuracy,
    confusion_matrix,
    f1_score,
    mae,
    mse,
    precision,
    r2_score,
    recall,
    rmse,
)


class MetricsTests(TestRunner):
    def setup(self) -> None:
        # 4 объекта: 1 ошибка -> accuracy 0.75; TP=2, FP=0, FN=1
        self.y_true = [1, 0, 1, 1]
        self.y_pred = [1, 0, 0, 1]

    def test_accuracy(self) -> AssertionGroup:
        g = AssertionGroup("metrics.accuracy")
        g.add(abs(accuracy(self.y_true, self.y_pred) - 0.75) < 1e-12, "accuracy = 0.75")
        g.add(abs(accuracy([1, 1], [1, 1]) - 1.0) < 1e-12, "идеальное предсказание = 1.0")
        return g

    def test_precision_recall_f1(self) -> AssertionGroup:
        g = AssertionGroup("metrics.prf")
        g.add(abs(precision(self.y_true, self.y_pred) - 1.0) < 1e-12, "precision = 2/2 = 1.0")
        g.add(abs(recall(self.y_true, self.y_pred) - 2 / 3) < 1e-12, "recall = 2/3")
        g.add(abs(f1_score(self.y_true, self.y_pred) - 0.8) < 1e-12, "f1 = 2·1·(2/3)/(1+2/3) = 0.8")
        g.add(precision([0, 0], [0, 0]) == 0.0, "нет предсказанных положительных -> 0.0")
        return g

    def test_confusion_matrix(self) -> AssertionGroup:
        g = AssertionGroup("metrics.confusion")
        labels, matrix = confusion_matrix(self.y_true, self.y_pred)
        g.add(labels == [0, 1], f"метки [0, 1], получено {labels}")
        g.add(matrix[0][0] == 1, "истина 0 / предсказано 0 = 1")
        g.add(matrix[1][0] == 1, "истина 1 / предсказано 0 = 1 (FN)")
        g.add(matrix[1][1] == 2, "истина 1 / предсказано 1 = 2 (TP)")
        g.add(sum(sum(row) for row in matrix) == len(self.y_true), "сумма матрицы = N")
        return g

    def test_regression(self) -> AssertionGroup:
        g = AssertionGroup("metrics.regression")
        y_true = [1.0, 2.0, 3.0]
        y_pred = [1.0, 2.0, 5.0]  # одна ошибка 2.0
        g.add(abs(mae(y_true, y_pred) - 2 / 3) < 1e-12, "mae = 2/3")
        g.add(abs(mse(y_true, y_pred) - 4 / 3) < 1e-12, "mse = 4/3")
        g.add(abs(rmse(y_true, y_pred) ** 2 - mse(y_true, y_pred)) < 1e-12, "rmse² = mse")
        g.add(abs(r2_score(y_true, y_true) - 1.0) < 1e-12, "идеальное предсказание -> R² = 1")
        g.add(r2_score([5.0, 5.0], [5.0, 5.0]) == 0.0, "постоянный y_true -> 0.0 (нет дисперсии)")
        return g

    def test_input_validation(self) -> AssertionGroup:
        g = AssertionGroup("metrics.validation")
        try:
            accuracy([1, 0], [1])
            g.add(False, "разные длины должны бросать ValueError")
        except ValueError:
            g.add(True, "разные длины -> ValueError")
        try:
            mae([], [])
            g.add(False, "пустая выборка должна бросать ValueError")
        except ValueError:
            g.add(True, "пустая выборка -> ValueError")
        return g


if __name__ == "__main__":
    MetricsTests().run_all()
