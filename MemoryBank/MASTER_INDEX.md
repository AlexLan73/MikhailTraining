# 🗂️ MASTER_INDEX — MikhailTraining (курс по ИИ)

> Читать **первым** в начале каждой сессии. Карта состояния проекта.

## 📊 Статус

- **Проект**: домашние задания курса по ИИ, Python ≥ 3.11.
- **Стадия**: каркас развёрнут (правила, MemoryBank, `core/` + `common/` + `homework/`,
  CLI `run_hw.py`, тесты). Образец каркаса — `hw00_intro`, ДЗ курса нумеруются с `hw01`.
  `hw01` закрыт вместе с этапом 2 (боевая приёмка на реальных данных, ускорение, устойчивость,
  два ревью). Открытые вопросы к Alex по итогам ревью — в `tasks/TASK_hw01_mdlinks.md`.
- **Тесты**: с 2026-08-16 стандарт — **pytest** (запрет снят по решению Alex).
  Legacy-наборы на `TestRunner` живут дальше: `python tests/all_test.py`.
- **Конфиг**: перенесён из `Test_3FFT_model` (radar3d), адаптирован под учебный репозиторий.

## 🧭 Навигация

| Что | Где |
|-----|-----|
| Правила Кодо | `.claude/rules/*.md` (12 файлов) |
| Архитектура / запуск | `CLAUDE.md`, `README.md` |
| Шаблоны (README ДЗ, TASK) | `Doc/templates/` |
| **Модуль `mdscan`** (архитектура · производительность · CLI и конфигурация) | `Doc/Modules/mdscan/README.md` · `Doc/Modules/mdscan/CLI.md` |
| **Окружение и инструменты** (gh, git, python, зависимости) | `Doc/ENVIRONMENT.md` |
| Активные задачи | `MemoryBank/tasks/IN_PROGRESS.md` |
| Конспекты / разборы / спеки | `MemoryBank/specs/` |
| Журнал сессий | `MemoryBank/sessions/YYYY-MM-DD.md` |
| Changelog | `MemoryBank/changelog/YYYY-MM.md` |

## 🎓 Домашние задания

| ID | тема | статус | таск |
|----|------|--------|------|
| `hw00` | Образец: сквозной прогон каркаса (не ДЗ курса) | ✅ готово | — |
| `hw01` | CLI: Markdown Link & Dead Code Checker | ✅ **DONE 2026-08-17** · `core/mdscan/` + `core/tokenstat/` · 444 теста · f1 = 1.0 | `TASK_hw01_mdlinks.md` |
| `hw01` | ↳ **этап 2**: боевая приёмка, ускорение, устойчивость, ревью | ✅ **DONE 2026-08-17** · H-01…H-13 · прогон по организации `dsp-gpu` (10 репо / 1230 файлов) · −36 % времени · `speedup` с HTTP ×9.59 · `Ctrl+C` → код 130 | `TASK_hw01_hardening_H01-H12.md` |

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
- `core/mdscan/` — сканер Markdown-ссылок в git-репозиториях (hw01): `Scanner` (Protocol),
  конфигурация `mdscan.yaml`, двухстадийный конвейер, чекеры, отчёты → `Doc/Modules/mdscan/`.
  Коды возврата `0/1/2/3` и `130` (`Ctrl+C`); умолчания параллельности `parse=10`, `http.workers=10`
- `tests/hw01/support/bench_*.py` — инструменты замера (слои, нагрузка, `speedup` с HTTP); не тесты
- `core/tokenstat/` — учёт токенов прогона по JSONL-транскрипту сессии и субагентов
- `run_hw.py` — Composition Root + CLI

## ⚙️ Среда

- Дома: Windows, `.venv` в корне. На работе: Debian.
- Базовый каркас — **без зависимостей** (чистая стандартная библиотека).
- `pip install -e .[ml]` — numpy/pandas/sklearn/matplotlib/scipy, `[nb]` — jupyter, `[dl]` — torch,
  `[hw01]` — markdown-it-py, linkify-it-py, mdit-py-plugins, GitPython, PyYAML, rich.

---

*Last updated: 2026-08-17 (после этапа 2 hw01) · Кодо*
