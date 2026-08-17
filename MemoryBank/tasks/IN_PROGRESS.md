# 🔄 IN_PROGRESS

> Короткий указатель на активную задачу (1–5 строк). Детали — в `TASK_hwNN_<topic>.md`.

## Сейчас в работе

- 🎯 **hw01 этап 2 — боевая приёмка и ускорение** (2026-08-17) — 🟡 спека и таски написаны,
  Alex не читал. Спека: `specs/hw01_mdscan_hardening_spec_2026-08-17.md`,
  таски H-01…H-12: `tasks/TASK_hw01_hardening_H01-H12.md`, скил `/hw01-build`.
  🔧 **Ревью 6** (Кодо): картина «63 % — `Path.resolve()`» была артефактом cProfile; прямые замеры —
  второй разбор `markdown-it` ради заголовков (~17 %) + обход (~20 %) + накладные (~22 %); спека §2, H-04/H-05
  переписаны, скилл поправлен, `python -m core.tokenstat` добавлен — `specs/hw01_mdscan_review6_fixes_2026-08-17.md`.
  Боевой прогон `dsp-gpu` уже сделан (04:18, 10 репо, 1230 файлов, дефект linkify исправлен).
  **Дальше:** Alex читает ревью 6 → по команде — волна 1 этапа 2 (H-01…H-04).

## Сделано ранее

- ✅ **hw01 — CLI: Markdown Link & Dead Code Checker** (2026-08-17): модуль `core/mdscan/`
  (16 тасков T-01…T-16, 6 волн, агенты Opus), `core/tokenstat/`, ДЗ `homework/hw01_mdlinks/`.
  `pytest tests/hw01 -q` → 396 passed, mypy 0 ошибок, ruff чисто; `python run_hw.py hw01`
  даёт `extract_f1 = 1.0`, `classify_accuracy = 1.0`, 28 файлов / 82 ссылки / 7 битых.
  Документация — `Doc/Modules/mdscan/`. Детали → `TASK_hw01_mdlinks.md`.
- ✅ **Спека hw01** (2026-08-16): части 1/2 и 2/2 приняты Alex, ревью 2–5 закрыты,
  ТЗ по таскам — `TASK_hw01_modules_T01-T15.md`.
- ✅ **Каркас репозитория** (2026-08-16): правила `.claude/rules/`, хуки, MCP, MemoryBank,
  `core/` + `common/` + `homework/`, CLI `run_hw.py`, тесты. Образец переименован `hw01_intro`
  → **`hw00_intro`** (номера `hwNN` совпадают с нумерацией курса).
- ✅ **Смена стандарта тестов** (2026-08-16): pytest разрешён и стал стандартом.

## Следующее

- 📚 Новое ДЗ курса (`hw02`) — по команде Alex: скилл `/new-homework`.
