# 🗂️ MASTER_INDEX — MikhailTraining (курс по ИИ)

> Читать **первым** в начале каждой сессии. Карта состояния проекта.

## 📊 Статус

- **Проект**: домашние задания курса по ИИ, Python ≥ 3.11.
- **Стадия**: каркас развёрнут (правила, MemoryBank, `core/` + `common/` + `homework/`,
  CLI `run_hw.py`, тесты). Образец каркаса — `hw00_intro`, ДЗ курса нумеруются с `hw01`.
- **Тесты**: с 2026-08-16 стандарт — **pytest** (запрет снят по решению Alex).
  Legacy-наборы на `TestRunner` живут дальше: `python tests/all_test.py`.
- **Конфиг**: перенесён из `Test_3FFT_model` (radar3d), адаптирован под учебный репозиторий.

## 🧭 Навигация

| Что | Где |
|-----|-----|
| Правила Кодо | `.claude/rules/*.md` (9 файлов) |
| Архитектура / запуск | `CLAUDE.md`, `README.md` |
| Шаблоны (README ДЗ, TASK) | `Doc/templates/` |
| **Окружение и инструменты** (gh, git, python, зависимости) | `Doc/ENVIRONMENT.md` |
| Активные задачи | `MemoryBank/tasks/IN_PROGRESS.md` |
| Конспекты / разборы / спеки | `MemoryBank/specs/` |
| Журнал сессий | `MemoryBank/sessions/YYYY-MM-DD.md` |
| Changelog | `MemoryBank/changelog/YYYY-MM.md` |

## 🎓 Домашние задания

| ID | тема | статус | таск |
|----|------|--------|------|
| `hw00` | Образец: сквозной прогон каркаса (не ДЗ курса) | ✅ готово | — |
| `hw01` | CLI: Markdown Link & Dead Code Checker | ✅ спека (2 части) принята 2026-08-16 · кода нет · дальше макеты M1–M5 | `TASK_hw01_mdlinks.md` |

> Новое ДЗ: скилл `/new-homework` или `.claude/rules/06-homework-layout.md`.

## 🗂️ Код

- `homework/registry.py` — контракт `HomeworkTask` (Template Method) + реестр заданий
- `homework/hwNN_<topic>/` — по пакету на задание
- `core/config/` — `Settings`, `ProjectPaths` (Value Object)
- `core/data/` — `DataContext` (Facade) + детерминированный `train_test_split`
- `core/metrics/` — классификация + регрессия (один источник истины)
- `core/models/` — `Model` (Protocol) + baseline-модели
- `core/viz/` — `FigureWriter` (matplotlib опционально)
- `common/runner.py` — legacy `TestRunner`, `common/seed.py`, `common/timer.py`
- `run_hw.py` — Composition Root + CLI

## ⚙️ Среда

- Дома: Windows, `.venv` в корне. На работе: Debian.
- Базовый каркас — **без зависимостей** (чистая стандартная библиотека).
- `pip install -e .[ml]` — numpy/pandas/sklearn/matplotlib/scipy, `[nb]` — jupyter, `[dl]` — torch.

---

*Last updated: 2026-08-16 · Кодо*
