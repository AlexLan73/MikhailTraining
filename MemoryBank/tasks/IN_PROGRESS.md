# 🔄 IN_PROGRESS

> Короткий указатель на активную задачу (1–5 строк). Детали — в `TASK_hwNN_<topic>.md`.

## Сейчас в работе

- 🎯 **hw01 — CLI: Markdown Link & Dead Code Checker** (2026-08-16) — ✅ **спека принята Alex**
  (часть 1/2 `specs/hw01_mdscan_reasoning_2026-08-16.md`, часть 2/2 `specs/hw01_mdscan_architecture_2026-08-16.md`;
  ревью 2 — `specs/hw01_mdscan_review2_fixes_2026-08-16.md`). Бюджет ≈1870 утверждён (после ревью 3 ≈1910).
  ✅ **Ревью 3** (диаграммы C1–C4 + 3.5 ↔ решения части 1) принято Alex: `MarkdownWorker(BaseObserver)`,
  отчёт из главного потока с законченным циклом (D6), `check(link, md_file)`; список — `specs/hw01_mdscan_review3_fixes_2026-08-16.md`.
  ТЗ под таски (`hw01_mdscan_spec_…`) ⛔ заморожено до гейта SP. Кода нет.
  **Дальше (по команде Alex):** S0 → S1 → **SP: макеты M1–M5** (часть 2 §7); каждый шаг — показать,
  дождаться приёмки — `.claude/rules/10-execution-gate.md`.

## Сделано ранее

- ✅ **Каркас репозитория** (2026-08-16): правила `.claude/rules/` (9), хуки, MCP, MemoryBank,
  `core/` + `common/` + `homework/`, CLI `run_hw.py`, тесты. Образец переименован `hw01_intro`
  → **`hw00_intro`** (номера `hwNN` теперь совпадают с нумерацией курса).
- ✅ **Смена стандарта тестов** (2026-08-16): pytest разрешён и стал стандартом.

## Следующее

- 📦 Каркас `homework/hw01_mdlinks/task.py` + регистрация в реестре (скилл `/new-homework`).
