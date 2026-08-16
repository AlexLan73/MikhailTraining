# 05 — Python Style (MikhailTraining)

> **paths:** `core/**`, `common/**`, `homework/**`, `tests/**`, `run_hw.py`, `*.py`

## Базовое

- Python ≥ 3.11.
- **Pathlib** для путей (`from pathlib import Path`). Минимум `os.path.join`.
  Абсолютные Windows-пути (`E:\...`) в коде и документации **запрещены** — репо ездит на Debian.
- **Type hints** везде (`def f(x: int) -> str:`). `from __future__ import annotations` для forward-refs.
- Имена пакетов/каталогов — **строчные ASCII** (`core`, не `Core`): Linux ФС регистрозависима.
- Докстринги — по-русски, с формулой, если это математика.

## SOLID + GoF (как в проекте)

| Принцип | Применение здесь |
|---------|------------------|
| **S**ingle responsibility | загрузка данных ≠ модель ≠ метрика ≠ график |
| **O**pen-closed | новое ДЗ = новый `HomeworkTask`, реестр и CLI не трогаем |
| **L**iskov | все модели ДЗ — один интерфейс `fit/predict`, взаимозаменяемы |
| **I**nterface segregation | маленькие `Protocol` под роль |
| **D**ependency injection | связывание в `run_hw.py` (Composition Root), без global'ов |

Паттерны: Strategy (модель / метрика / визуализатор), Template Method (`HomeworkTask.run`),
Registry (реестр ДЗ), Facade (`DataContext`), Value Object (`Settings`, `ProjectPaths`).

## Naming

- `snake_case` — функции/переменные.
- `PascalCase` — классы.
- `UPPER_CASE` — константы (`DEFAULT_SEED = 42`).
- Префикс `_` — приватное.
- Префикс `I` НЕ используем (не Java) — пишем `Model(Protocol)`.

## Структура пакета

```python
# core/metrics/__init__.py — реэкспорт публичного API подпакета
from .classification import accuracy, confusion_matrix, f1_score
from .regression import mae, mse, rmse

__all__ = ["accuracy", "confusion_matrix", "f1_score", "mae", "mse", "rmse"]
```

## NumPy / pandas

- Векторизация вместо python-циклов где возможно.
- Явный `dtype` (`np.float32`) — экономия памяти под GPU-перенос.
- Не мутировать входные массивы/датафреймы — возвращать новые (чистота).
- Никаких `SettingWithCopyWarning`-конструкций: `df = df.copy()` перед правкой.

## torch / GPU

- Импорт torch — **опциональный** (`try/except ImportError`), базовые ДЗ работают без него.
- `device = "cuda" if torch.cuda.is_available() else "cpu"` — одной строкой в конфиге ДЗ, не по коду.
- Дома (Windows) GPU-стека может не быть → тест уходит в `skip` (`pytest.importorskip`), не «чинить».
- На Debian: torch **2.11.0+rocm7.2**, venv Python **3.12** (колёса cp312), AMD RX 9070 (gfx1201).
- Тяжёлые скачивания (>600 МБ) — не качать без спроса.

## Запреты

- `from xxx import *`
- bare `except:` (нужен `except Exception as e`)
- `print()` в библиотечном коде (`core/`, `common/`) — только в `run_hw.py`/ДЗ-выводе
- mutable default args (`def f(x=[])`)
- `lambda` для нетривиальной логики (>30 символов)
- магические числа в коде модели — в `Settings`/константы с именем

## Линт

```bash
ruff check core/ common/ homework/ tests/
mypy core/
```

`pyproject.toml` настроен: line-length=110, ruff rules E/F/W/I/N/UP/B/SIM/RET.
