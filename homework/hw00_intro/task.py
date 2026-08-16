"""ДЗ 00 — вводный образец: сквозной прогон каркаса (не задание курса).

Показывает канон (правило 06): загрузка → сплит → baseline → модель → метрики.
Данных снаружи не требует: игрушечная выборка генерится детерминированно по сиду.
Служит и образцом для новых ДЗ, и смоук-тестом инфраструктуры.
"""

from __future__ import annotations

import random

from core.data import train_test_split
from core.metrics import accuracy, f1_score
from core.models import MajorityClassifier, ThresholdClassifier

# базу импортируем лениво внутри модуля-реестра, здесь — только типы
from homework.registry import HomeworkContext, HomeworkTask


def make_toy_dataset(n: int, seed: int) -> list[tuple[float, int]]:
    """Два гауссовых облака на прямой: класс 0 около 0.0, класс 1 около 2.0.

    Возвращает список пар (признак, метка). Детерминирован по сиду.
    """
    rng = random.Random(seed)
    negatives = [(rng.gauss(0.0, 1.0), 0) for _ in range(n // 2)]
    positives = [(rng.gauss(2.0, 1.0), 1) for _ in range(n - n // 2)]
    return negatives + positives


class Hw00Intro(HomeworkTask):
    """Сквозной прогон: baseline vs пороговый классификатор."""

    hw_id = "hw00"
    title = "Образец: сквозной прогон каркаса (baseline vs порог)"

    n_samples = 400
    test_size = 0.25

    def solve(self, ctx: HomeworkContext) -> dict[str, float]:
        dataset = make_toy_dataset(self.n_samples, ctx.seed)
        train, test = train_test_split(dataset, test_size=self.test_size, seed=ctx.seed)

        x_train = [x for x, _ in train]
        y_train = [y for _, y in train]
        x_test = [x for x, _ in test]
        y_test = [y for _, y in test]

        baseline = MajorityClassifier().fit(x_train, y_train)
        model = ThresholdClassifier().fit(x_train, y_train)

        y_baseline = baseline.predict(x_test)
        y_model = model.predict(x_test)

        ctx.data.write_json(
            "predictions.json",
            {"x": x_test, "y_true": y_test, "y_pred": y_model, "threshold": model.threshold},
        )

        return {
            "accuracy_baseline": accuracy(y_test, y_baseline),
            "accuracy_model": accuracy(y_test, y_model),
            "f1_model": f1_score(y_test, y_model),
            "threshold": float(model.threshold or 0.0),
            "n_train": float(len(train)),
            "n_test": float(len(test)),
        }
