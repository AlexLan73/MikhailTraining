# MikhailTraining — домашние задания курса по ИИ

Один репозиторий на весь курс: **каждое ДЗ — отдельный пакет**, запускается одной командой,
общий код (данные, метрики, модели, графика) живёт в `core/` и переиспользуется.

## Быстрый старт

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .[dev]     # Windows
.venv/bin/python -m pip install -e .[dev]             # Debian
# численный стек для ДЗ, когда понадобится:
#   pip install -e .[ml]      numpy/pandas/sklearn/matplotlib/scipy
#   pip install -e .[nb]      jupyterlab
#   pip install -e .[dl]      torch

python run_hw.py --list      # список заданий
python run_hw.py hw00        # запустить одно -> out/hw00/
python run_hw.py --all       # все подряд
pytest                       # тесты (стандарт проекта)
python tests/all_test.py     # legacy-наборы на TestRunner
```

Базовый каркас работает **без внешних зависимостей** — `python run_hw.py hw00` заводится
на голом Python 3.11+.

## Структура

```
MikhailTraining/
├── homework/            # ДЗ: пакет на задание (hw00_intro — образец, hw01_..., ...)
│   ├── registry.py      #   контракт HomeworkTask + реестр заданий
│   └── hw00_intro/      #   task.py · README.md (условие/метрики/выводы)
├── core/                # общая база — ВСЯ математика здесь
│   ├── config/          #   Settings, ProjectPaths (Value Object)
│   ├── data/            #   DataContext (Facade) + детерминированный сплит
│   ├── metrics/         #   accuracy/precision/recall/F1 · MAE/MSE/RMSE/R²
│   ├── models/          #   контракт Model (Protocol) + baseline-модели
│   └── viz/             #   FigureWriter (matplotlib — опционально)
├── common/              # инфраструктура: set_seed, Stopwatch, legacy TestRunner
├── tests/               # тесты pytest + legacy-наборы TestRunner (all_test.py)
├── MemoryBank/          # память проекта: статус, таски, спеки, сессии
├── Doc/                 # документация и шаблоны
├── data/                # датасеты (в git НЕ идут)
├── out/                 # артефакты прогонов (в git НЕ идут)
└── run_hw.py            # Composition Root + CLI
```

## Как добавить новое ДЗ

1. `homework/hwNN_<topic>/` — `task.py` (класс-наследник `HomeworkTask`), `README.md`, `__init__.py`.
2. Зарегистрировать класс в `homework/registry.py` → `_TASK_CLASSES`.
3. Тесты `tests/test_hwNN.py` — на **pytest** (функции `test_*`, `assert`).
4. Прогнать `python run_hw.py hwNN` и `pytest`, вписать реальные числа в README ДЗ.

Подробно — `.claude/rules/06-homework-layout.md` (или скилл `/new-homework`).

## Правила проекта

Модульные правила ассистента — `.claude/rules/*.md`:

| файл | о чём |
|------|-------|
| `00-new-task-workflow.md` | порядок при новой задаче (доки → анализ → код) |
| `01-user-profile.md` | профиль Alex и Кодо, стиль общения |
| `02-workflow.md` | сессия: начало → работа → конец |
| `03-worktree-safety.md` | 🚨 не писать в `.claude/worktrees/` |
| `04-testing-python.md` | тесты на `pytest` (стандарт), legacy `TestRunner` |
| `05-python-style.md` | стиль Python, SOLID/GoF, numpy/torch |
| `06-homework-layout.md` | канон структуры одного ДЗ |
| `07-math-in-core.md` | математика только в `core/`, ноутбук — тонкий слой |
| `08-ml-experiments.md` | сид, данные, веса, метрики, утечки |
| `09-oop-design.md` | ООП, SOLID, GRASP, GoF, один класс = один файл, тест-гейты |

## Список заданий

| ID | тема | статус |
|----|------|--------|
| `hw00` | Образец: сквозной прогон каркаса (не ДЗ курса) | ✅ готово |
| `hw01` | CLI: Markdown Link & Dead Code Checker | 🟡 условие |

Актуальный статус — `MemoryBank/MASTER_INDEX.md`.
