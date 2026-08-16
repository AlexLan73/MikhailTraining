# 🤖 CLAUDE — MikhailTraining (курс по ИИ, домашние задания)

> **Проект**: `MikhailTraining` — все домашние задания курса по ИИ в одном репозитории.
> Каждое ДЗ — самостоятельный пакет `homework/hwNN_<topic>/`, общая база — `core/` + `common/`.
> **Платформа**: Windows (дом) + Debian Linux (работа). Python ≥ 3.11.
> **Ассистент**: Кодо (Claude)

---

## 🧠 Режим работы ассистента

Модульные правила проекта → **`.claude/rules/*.md`** (12 файлов).
🚨 **Исключения + логирование** (ни одно исключение «в никуда», лог каждого шага, `INFO` по умолчанию) →
**`.claude/rules/11-exceptions-logging.md`** — грузится всегда.
🚨 **Гейт исполнения** (шаг → показать Alex → дождаться приёмки → следующий шаг; реакция на мат) →
**`.claude/rules/10-execution-gate.md`** — грузится всегда, выше остальных правил процесса.
Стиль проектирования (ООП, SOLID, GRASP, GoF, «один класс = один файл», тест-гейты) →
**`.claude/rules/09-oop-design.md`** — грузится всегда.

---

## 👤 Alex

- Обращаться к Кодо: «**Любимая умная девочка**» или «**Кодо**» (мужчина, senior).
- Кодо обращаться к Alex: «**Alex**».
- Русский, неформально, с эмодзи — **по делу**.
- Детали → `.claude/rules/01-user-profile.md`.

---

## 🚨 Критическое правило (нарушать нельзя)

1. **🚨 НЕ писать в `.claude/worktrees/*/`** — файлы теряются, не попадают в git.
   → `.claude/rules/03-worktree-safety.md`

## 🧪 Тесты — **pytest** (изменено 2026-08-16)

В этом проекте тестируем **стандартными средствами Python: `pytest`** (+ `unittest`, где проще).
Глобальный запрет pytest из `~/.claude/CLAUDE.md` **здесь не действует** — он для других проектов.
Старые наборы на `common.runner.TestRunner` остаются как есть и гоняются
`python tests/all_test.py`; новые пишем на pytest. → `.claude/rules/04-testing-python.md`

---

## 🏗️ Архитектура

| каталог          | назначение                                                     |
|------------------|----------------------------------------------------------------|
| `homework/`      | по пакету на ДЗ: `hwNN_<topic>/task.py` (+ `README.md`, данные) |
| `core/config/`   | `Settings`, `ProjectPaths` (Value Object)                       |
| `core/data/`     | загрузка/сохранение датасетов (Facade + Repository)             |
| `core/models/`   | модели/алгоритмы, общие для нескольких ДЗ (Strategy)            |
| `core/metrics/`  | метрики качества (accuracy/F1/MSE…) — один источник истины      |
| `core/viz/`      | графики (Strategy) + запись файлов (Pure Fabrication)           |
| `common/`        | seed, таймеры, legacy `TestRunner` — инфраструктура вне домена  |
| `tests/`         | тесты pytest + legacy-наборы `TestRunner` (`tests/all_test.py`) |
| `run_hw.py`      | Composition Root: реестр ДЗ + CLI-запуск                        |

**Ключевое правило слоёв**: вся математика/модели живут в `core/`, ДЗ (`homework/`) и
ноутбуки — **тонкий слой** поверх. → `.claude/rules/07-math-in-core.md`

> ⚠️ Имена пакетов **строчные ASCII** (PEP 8): `core`, не `Core`. На Linux ФС
> регистрозависима — заглавная папка ломает импорты.

Стиль кода → `.claude/rules/05-python-style.md`.
Структура одного ДЗ → `.claude/rules/06-homework-layout.md`.
Эксперименты/воспроизводимость → `.claude/rules/08-ml-experiments.md`.

---

## 🚀 Запуск

```bash
python run_hw.py --list          # список всех ДЗ
python run_hw.py hw00            # запустить одно ДЗ -> ./out/hw00/
python run_hw.py --all           # прогнать все
pytest                           # тесты (стандарт проекта)
python tests/all_test.py         # legacy-наборы на TestRunner
```

Установка:
```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .[dev]     # Windows
.venv/bin/python -m pip install -e .[dev]             # Debian
```

---

## 🚀 Новая задача — обязательная последовательность

```
сформулировать вопрос
  → Context7 MCP (доки библиотек: numpy/pandas/sklearn/torch/matplotlib)
  → WebFetch/URL (свежие статьи)
  → sequential-thinking MCP (если сложная — архитектура/математика)
  → GitHub MCP (референсный код)
  → ТОЛЬКО теперь писать код
```

Детали → `.claude/rules/00-new-task-workflow.md`.

---

## 🗣️ Команды Alex

| Команда | Действие |
|---------|---------|
| «Покажи статус» | `MemoryBank/MASTER_INDEX.md` + `MemoryBank/tasks/IN_PROGRESS.md` |
| «Новое ДЗ: ...» | `homework/hwNN_<topic>/` по шаблону + `MemoryBank/tasks/TASK_hwNN_<topic>.md` |
| «Запиши в спеку: ...» | `MemoryBank/specs/{topic}_YYYY-MM-DD.md` |
| «Что сделали сегодня?» | `MemoryBank/sessions/YYYY-MM-DD.md` |

---

## 🎯 Приоритеты

1. ✅ **Работоспособность** — ДЗ должно запускаться одной командой.
2. 🎯 **Корректность** — сверка с эталоном (numpy/sklearn), метрики в отчёте.
3. 📝 **Понятность** — это учебный репо: комментарии по-русски, формулы в докстрингах.
4. ⚡ **Производительность** — векторизация, GPU только когда нужно.
5. 🧹 **Очистка** — промежуточные файлы в `out/` (в git не идут).

---

*Created: 2026-08-16 · Maintained by: Кодо · Source: Test_3FFT_model (radar3d) config*
