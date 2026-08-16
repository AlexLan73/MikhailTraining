# 04 — Testing Python (pytest — стандарт проекта)

> **paths:** `tests/**`, `homework/**/tests/**`, `core/**/tests/**`
> **Изменено 2026-08-16 по решению Alex.** Раньше здесь был запрет pytest — **запрет снят**.

## ⚖️ Приоритет над глобальным правилом

В `~/.claude/CLAUDE.md` (глобальный профиль) pytest значится запрещённым — это правило
для **других** проектов (DSP-GPU и т.п.). **В `MikhailTraining` оно не действует**:
здесь тестирование ведётся стандартными средствами Python.

## ✅ Стандарт — `pytest`

Пишем обычные тесты pytest: функции `test_*`, голый `assert`, фикстуры, параметризация.

📌 **Образец для копирования: `tests/test_metrics_pytest.py`** — там показаны все механики
(fixture, parametrize с `id`, `approx`, `raises(match=...)`, `importorskip`, `tmp_path`).
Корневой `conftest.py` кладёт корень репо в `sys.path` — импорты `core.*` работают без установки пакета.

```python
# tests/test_metrics_pt.py
from __future__ import annotations

import pytest

from core.metrics import accuracy, f1_score, mae


@pytest.fixture
def binary_sample() -> tuple[list[int], list[int]]:
    # 4 объекта, 1 ошибка -> accuracy 0.75
    return [1, 0, 1, 1], [1, 0, 0, 1]


def test_accuracy(binary_sample: tuple[list[int], list[int]]) -> None:
    y_true, y_pred = binary_sample
    assert accuracy(y_true, y_pred) == pytest.approx(0.75)


@pytest.mark.parametrize(
    ("y_true", "y_pred", "expected"),
    [
        ([1.0, 2.0, 3.0], [1.0, 2.0, 5.0], 2 / 3),
        ([1.0, 1.0], [1.0, 1.0], 0.0),
    ],
)
def test_mae(y_true: list[float], y_pred: list[float], expected: float) -> None:
    assert mae(y_true, y_pred) == pytest.approx(expected)


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        accuracy([1, 0], [1])


def test_torch_branch() -> None:
    torch = pytest.importorskip("torch", reason="torch не установлен — GPU-ветка пропущена")
    assert torch.tensor([1.0]).sum().item() == pytest.approx(1.0)
```

### Что используем

| Инструмент | Зачем |
|-----------|-------|
| `assert` + `pytest.approx` | сравнение float — без ручных `abs(...) < 1e-12` |
| `@pytest.fixture` | подготовка данных вместо `setup()` |
| `@pytest.mark.parametrize` | таблица случаев вместо копипасты |
| `pytest.raises` | проверка исключений |
| `pytest.importorskip` / `@pytest.mark.skipif` | нет torch / нет датасета → **skip**, не падение |
| `tmp_path` | временные файлы (не писать в репо) |
| `conftest.py` | общие фикстуры на каталог `tests/` |

`unittest` (stdlib) тоже допустим, если для конкретного случая он проще — pytest его запускает.

## Запуск

```bash
pytest                      # всё (testpaths = tests, см. pyproject.toml)
pytest tests/test_metrics_pt.py
pytest -k accuracy          # по имени
pytest -q                   # коротко
pytest --cov=core           # покрытие (нужен pytest-cov)
```

## 🧟 Наследие: `common.runner.TestRunner`

Старые наборы (`tests/test_metrics.py`, `test_models.py`, `test_data.py`, `test_homework.py`,
`test_hw00.py`) написаны на самодельном `TestRunner` и **остаются как есть** —
переписывать их не требуется.

- Гоняются по-прежнему: `python tests/all_test.py`.
- pytest их не собирает (классы называются `*Tests`, а не `Test*`) — конфликта нет.
- **Новые** тесты пишем на pytest. Трогаем старый файл по делу — можно заодно перевести.
- `common/runner.py` не удаляем.

## Правила для учебного репо (не изменились)

- Тест **не должен** зависеть от скачанного датасета: нет данных → `skip`, не падение.
- Тяжёлое обучение (эпохи) в тестах не гоняем — 1 шаг / форма выхода / метрика на игрушке.
- Тест доказывает **свойство** (инвариант, диапазон, сходимость), а не «печатает».
- Новая метрика в `core/metrics/` → хотя бы один тест со сверкой с эталоном (numpy/sklearn).

## ✅ Dev-инструменты

`pytest`, `pytest-cov`, `ruff` (lint), `mypy` (type check). Ставятся через `pip install -e .[dev]`.
