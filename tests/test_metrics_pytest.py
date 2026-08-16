"""Образцовый набор тестов на **pytest** — метрики `core.metrics`.

Это эталон для новых тестов проекта (правило `.claude/rules/04-testing-python.md`).
Показаны все механики, которые нужны в учебном репо:

* `@pytest.fixture`          — подготовка данных вместо `setup()`;
* `@pytest.mark.parametrize` — таблица случаев вместо копипасты;
* `pytest.approx`            — сравнение float без ручных `abs(...) < 1e-12`;
* `pytest.raises`            — проверка исключений;
* `pytest.importorskip`      — нет библиотеки → **skip**, а не падение;
* `tmp_path`                 — временные файлы мимо репозитория.

Старый набор `tests/test_metrics.py` (на `common.runner.TestRunner`) оставлен как есть —
он гоняется через `python tests/all_test.py`. Здесь то же покрытие, но по-новому.

⚠️ Набор метрик курса будет меняться (появятся ROC-AUC, log-loss и прочее). Ценность файла —
в **механиках** pytest, а не в конкретных формулах: при новых метриках меняем импорты
и ожидаемые числа, структура остаётся.

Запуск:

    pytest                                  # всё
    pytest tests/test_metrics_pytest.py -v  # только этот файл
    pytest -k regression                    # по имени
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.metrics import (
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

# ─────────────────────────────── фикстуры ────────────────────────────────


@pytest.fixture
def binary_sample() -> tuple[list[int], list[int]]:
    """4 объекта, ровно одна ошибка: accuracy = 0.75, TP=2, FP=0, FN=1."""
    y_true = [1, 0, 1, 1]
    y_pred = [1, 0, 0, 1]
    return y_true, y_pred


@pytest.fixture
def regression_sample() -> tuple[list[float], list[float]]:
    """3 объекта, одна ошибка величиной 2.0: MAE = 2/3, MSE = 4/3."""
    y_true = [1.0, 2.0, 3.0]
    y_pred = [1.0, 2.0, 5.0]
    return y_true, y_pred


# ───────────────────────────── классификация ─────────────────────────────


def test_accuracy(binary_sample: tuple[list[int], list[int]]) -> None:
    y_true, y_pred = binary_sample
    assert accuracy(y_true, y_pred) == pytest.approx(0.75)


@pytest.mark.parametrize(
    ("y_true", "y_pred", "expected"),
    [
        pytest.param([1, 1], [1, 1], 1.0, id="всё-верно"),
        pytest.param([1, 0], [0, 1], 0.0, id="всё-мимо"),
        pytest.param([1, 0, 1, 1], [1, 0, 0, 1], 0.75, id="одна-ошибка"),
        pytest.param(["a", "b"], ["a", "a"], 0.5, id="строковые-метки"),
    ],
)
def test_accuracy_cases(y_true: list, y_pred: list, expected: float) -> None:
    """accuracy не зависит от типа меток — сравнение идёт через `==`."""
    assert accuracy(y_true, y_pred) == pytest.approx(expected)


def test_precision_recall_f1(binary_sample: tuple[list[int], list[int]]) -> None:
    """P = 2/2 = 1.0; R = 2/3; F1 = 2·P·R/(P+R) = 0.8."""
    y_true, y_pred = binary_sample
    assert precision(y_true, y_pred) == pytest.approx(1.0)
    assert recall(y_true, y_pred) == pytest.approx(2 / 3)
    assert f1_score(y_true, y_pred) == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("metric", "y_true", "y_pred"),
    [
        pytest.param(precision, [0, 0], [0, 0], id="precision-нет-предсказанных-положительных"),
        pytest.param(recall, [0, 0], [1, 1], id="recall-нет-истинных-положительных"),
        pytest.param(f1_score, [0, 0], [0, 0], id="f1-обе-компоненты-нулевые"),
    ],
)
def test_degenerate_returns_zero(metric, y_true: list[int], y_pred: list[int]) -> None:
    """Вырожденный случай = 0.0, а не ZeroDivisionError (контракт `core.metrics`)."""
    assert metric(y_true, y_pred) == 0.0


def test_confusion_matrix(binary_sample: tuple[list[int], list[int]]) -> None:
    y_true, y_pred = binary_sample
    labels, matrix = confusion_matrix(y_true, y_pred)

    assert labels == [0, 1]
    assert matrix[0][0] == 1, "истина 0 / предсказано 0 (TN)"
    assert matrix[1][0] == 1, "истина 1 / предсказано 0 (FN)"
    assert matrix[1][1] == 2, "истина 1 / предсказано 1 (TP)"
    # Инвариант: сумма всей матрицы = размер выборки.
    assert sum(sum(row) for row in matrix) == len(y_true)


# ─────────────────────────────── регрессия ───────────────────────────────


def test_regression_basic(regression_sample: tuple[list[float], list[float]]) -> None:
    y_true, y_pred = regression_sample
    assert mae(y_true, y_pred) == pytest.approx(2 / 3)
    assert mse(y_true, y_pred) == pytest.approx(4 / 3)


def test_rmse_is_sqrt_of_mse(regression_sample: tuple[list[float], list[float]]) -> None:
    """Проверяем **свойство** (rmse² = mse), а не подогнанное число."""
    y_true, y_pred = regression_sample
    assert rmse(y_true, y_pred) ** 2 == pytest.approx(mse(y_true, y_pred))


@pytest.mark.parametrize(
    ("y_true", "y_pred", "expected"),
    [
        pytest.param([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 1.0, id="идеальное-предсказание"),
        pytest.param([5.0, 5.0], [5.0, 5.0], 0.0, id="нет-дисперсии-по-контракту-0"),
    ],
)
def test_r2_score(y_true: list[float], y_pred: list[float], expected: float) -> None:
    assert r2_score(y_true, y_pred) == pytest.approx(expected)


# ───────────────────────────── валидация входа ───────────────────────────


@pytest.mark.parametrize("metric", [accuracy, precision, recall, mae, mse])
def test_length_mismatch_raises(metric) -> None:
    with pytest.raises(ValueError, match="длины не совпадают"):
        metric([1, 0], [1])


@pytest.mark.parametrize("metric", [accuracy, mae, mse])
def test_empty_sample_raises(metric) -> None:
    with pytest.raises(ValueError, match="пустая выборка"):
        metric([], [])


def test_input_is_not_mutated(binary_sample: tuple[list[int], list[int]]) -> None:
    """Метрики — чистые функции: входные списки после вызова не изменились."""
    y_true, y_pred = binary_sample
    before_true, before_pred = list(y_true), list(y_pred)

    accuracy(y_true, y_pred)
    f1_score(y_true, y_pred)
    confusion_matrix(y_true, y_pred)

    assert y_true == before_true
    assert y_pred == before_pred


# ───────── сверка с эталоном: нет sklearn → skip, а не падение ───────────


def test_matches_sklearn(binary_sample: tuple[list[int], list[int]]) -> None:
    """Правило 08: новая метрика сверяется с эталоном (sklearn/numpy).

    Дома sklearn может быть не установлен (`pip install -e .[ml]`) — тогда тест
    уходит в skip. Именно так оформляются все ветки «нет библиотеки / нет датасета».
    """
    sk = pytest.importorskip("sklearn.metrics", reason="sklearn не установлен — ставится через .[ml]")
    y_true, y_pred = binary_sample

    assert accuracy(y_true, y_pred) == pytest.approx(sk.accuracy_score(y_true, y_pred))
    assert precision(y_true, y_pred) == pytest.approx(sk.precision_score(y_true, y_pred))
    assert recall(y_true, y_pred) == pytest.approx(sk.recall_score(y_true, y_pred))
    assert f1_score(y_true, y_pred) == pytest.approx(sk.f1_score(y_true, y_pred))


# ──────────────── временные файлы: tmp_path, не корень репо ──────────────


def test_report_written_to_tmp_path(
    tmp_path: Path,
    binary_sample: tuple[list[int], list[int]],
) -> None:
    """Артефакты теста пишем в `tmp_path` — репозиторий и `out/` остаются чистыми."""
    y_true, y_pred = binary_sample
    report = tmp_path / "metrics.csv"
    report.write_text(f"accuracy,{accuracy(y_true, y_pred)}\n", encoding="utf-8")

    assert report.exists()
    assert report.read_text(encoding="utf-8").startswith("accuracy,0.75")
