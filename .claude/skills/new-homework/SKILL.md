---
name: new-homework
description: Создать каркас нового домашнего задания курса по ИИ в MikhailTraining — пакет homework/hwNN_<topic>/ (task.py + README.md + __init__.py), регистрация в реестре, таск-файл в MemoryBank, набор тестов. Запускается когда Alex говорит «новое ДЗ», «добавь домашку», `/new-homework`.
disable-model-invocation: false
---

# new-homework — каркас нового ДЗ

## 🔹 Шаг 0 — спросить (один раз, если не сказано)

Номер `NN`, тема (строчными ASCII, напр. `linreg`), краткое условие. Всё остальное — по канону.

## 🔹 Шаг 1 — создать пакет `homework/hwNN_<topic>/`

```
homework/hwNN_<topic>/
  __init__.py     # from .task import HwNN<Topic>;  __all__ = ["HwNN<Topic>"]
  README.md       # Условие / Что сделано / Как запустить / Метрики / Выводы
  task.py         # class HwNN<Topic>(HomeworkTask): hw_id="hwNN"; title="..."; solve(ctx)->dict
  solution.py     # (опц.) логика ТОЛЬКО этого ДЗ
```

`task.py` — тонкая оркестровка: загрузил (`core.data`) → посчитал (`core.models`) →
метрики (`core.metrics`) → артефакты в `ctx.out_dir`. Математика — в `core/` (правило 07).

## 🔹 Шаг 2 — зарегистрировать

`homework/registry.py` → добавить импорт и класс в `_TASK_CLASSES`.
Проверить: `python run_hw.py --list` показывает новое ДЗ.

## 🔹 Шаг 3 — тесты (pytest)

`tests/test_hwNN.py` — функции `test_*` с `assert`: минимум
(а) задание регистрируется и `hw_id` уникален, (б) `solve` на игрушечных данных даёт
метрику в разумном диапазоне. Нет датасета/библиотеки → `pytest.skip(...)` /
`pytest.importorskip(...)`, не падение. Регистрировать нигде не надо — pytest сам соберёт.

## 🔹 Шаг 4 — MemoryBank

- `MemoryBank/tasks/TASK_hwNN_<topic>.md` — условие, план, статус, метрики.
- `MemoryBank/tasks/IN_PROGRESS.md` — указатель на активный таск (1–5 строк).
- `MemoryBank/MASTER_INDEX.md` — строка в таблице ДЗ.

## 🔹 Шаг 5 — проверка (обязательно прогнать самой)

```bash
python run_hw.py hwNN
pytest
```

В README ДЗ вписать **реальные числа**, а не «работает».

## 🚫 Чего не делать

- ❌ Скрипт в корне репо вместо пакета.
- ❌ Копипаста прошлого ДЗ — общее выносим в `core/`.
- ❌ Датасеты/веса/PNG в git — только `out/` и `data/` (игнорятся).
