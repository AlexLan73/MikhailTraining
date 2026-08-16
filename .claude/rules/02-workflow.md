# 02 — Workflow (сессия: начало → работа → конец)

## 📖 В начале сессии

1. Прочитать `MemoryBank/MASTER_INDEX.md` — статус проекта и карта ДЗ.
2. Прочитать `MemoryBank/tasks/IN_PROGRESS.md` — что сейчас в работе.
3. Посмотреть последнюю `MemoryBank/sessions/YYYY-MM-DD.md`.
4. Новая тема → применить `00-new-task-workflow.md` (Context7 → URL → seq → GitHub).

## 💻 Во время работы

- **Одно ДЗ = один пакет** `homework/hwNN_<topic>/` + **один таск-файл**
  `MemoryBank/tasks/TASK_hwNN_<topic>.md`.
- `MemoryBank/tasks/IN_PROGRESS.md` — короткий указатель на активный TASK-файл (1–5 строк).
- Исследования / конспекты / разборы теории → `MemoryBank/specs/{topic}_YYYY-MM-DD.md`.
- Изменение публичного API `core/` → обновить `README.md`.
- Новое ДЗ регистрируется в `run_hw.py` (реестр) — иначе `--list` его не увидит.

## 📝 В конце сессии

1. Короткое резюме → `MemoryBank/sessions/YYYY-MM-DD.md`.
2. Обновить `MemoryBank/changelog/YYYY-MM.md` (одна строчка).
3. Сданные ДЗ — пометить ✅ DONE внутри TASK-файла и в `MASTER_INDEX.md`.
4. Временные черновики — **удалить** (принцип чистоты).

## 🎯 Приоритеты (в порядке убывания)

1. ✅ **Работоспособность** — `python run_hw.py hwNN` отрабатывает от начала до конца.
2. 🎯 **Корректность** — метрики сверены с эталоном (numpy/sklearn).
3. 📝 **Понятность** — учебный репо: формулы и «почему» в докстрингах.
4. ⚡ **Производительность** — векторизация, потом GPU.
5. 🧹 **Очистка** — временное в `out/` (git не трекает).

## 🚫 Запреты процесса

- Не делать git push/tag без явного OK от Alex.
- Не менять условие ДЗ / архитектуру слоёв без согласования.
- Не писать в `.claude/worktrees/*/` (см. `03-worktree-safety.md`).
- Тесты — `pytest` (см. `04-testing-python.md`); legacy-наборы на `TestRunner` не ломать.
- Не коммитить датасеты и веса моделей (см. `.gitignore`, `08-ml-experiments.md`).

## 🗣️ Команды Alex

| Команда | Действие |
|---------|---------|
| «Покажи статус» | `MASTER_INDEX.md` + `tasks/IN_PROGRESS.md` |
| «Новое ДЗ: ...» | пакет по шаблону + `tasks/TASK_hwNN_<topic>.md` + запись в реестр |
| «Запиши в спеку: ...» | `specs/{topic}_YYYY-MM-DD.md` |
| «Что сделали сегодня?» | создать `sessions/YYYY-MM-DD.md` |
