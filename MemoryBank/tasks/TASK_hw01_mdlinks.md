# TASK hw01_mdlinks — CLI: Markdown Link & Dead Code Checker

- **Статус**: ✅ **DONE 2026-08-17** — модуль написан, отлажен, покрыт тестами, задокументирован
- **Пакет ДЗ**: `homework/hw01_mdlinks/` (`task.py`, `solution.py`, `support/`, `README.md`)
- **Модуль**: `core/mdscan/` (сканер) + `core/tokenstat/` (учёт токенов)
- **Документация модуля**: `Doc/Modules/mdscan/README.md` (архитектура) ·
  `Doc/Modules/mdscan/CLI.md` (командная строка, все параметры, отчёт)
- **Создан**: 2026-08-16 · **Закрыт**: 2026-08-17

## Условие (кратко)

Консольная утилита: сканирует папку → находит `.md` → извлекает ссылки `[text](url)` и
`file:///...` → проверяет локальные (существование файла) и внешние (HTTP HEAD/GET) →
печатает отчёт с цветами/таблицей и статус-кодами.

Подводные камни, названные в задании:
- относительные пути разрешаются **относительно файла**, где встретилась ссылка;
- таймауты HTTP и обработка сетевых ошибок (404 / 500 / timeout).

Полный текст — `homework/hw01_mdlinks/README.md`.

## Что сделано

Разработка шла по ТЗ `MemoryBank/tasks/TASK_hw01_modules_T01-T15.md` (таски **T-01…T-16**),
шестью волнами; таски внутри волны выполняли независимые агенты Opus, приёмку делал
оркестрант (скилл `.claude/skills/hw01-build/`).

| Волна | Таски | Что закрыто |
|---|---|---|
| 0 | T-01 · T-02 · T-03 · T-04 · T-15 | модели и enum, фикстуры-дерево, конфигурация, логирование, tokenstat |
| 1 | T-05 · T-06 · T-07 · T-08 · T-09 | CLI и валидация, парсинг, чекеры, источники репозиториев, обход |
| 2 | T-10 · T-11 · T-12 | конвейер, прогресс, отчёты |
| 3 | T-13 | `Scanner` / `ScanOrchestrator` / `PipelineRunner`, точка входа `python -m core.mdscan` |
| 4 | T-14 | `Hw01MdLinks(HomeworkTask)`, метрики ДЗ, `python run_hw.py hw01` |
| 5 | T-16 | документация: README ДЗ, `Doc/Modules/mdscan/`, MemoryBank |

Один агент (T-13) упал на лимите сессии и был перезапущен — работа принята со второго прохода.

### Итог по коду и тестам

- `pytest tests/hw01 -q` → **396 passed** (15 тестовых файлов).
- `mypy` — 0 ошибок (138 файлов), `ruff` — чисто.
- Сеть в тестах только `127.0.0.1` (локальный `http.server`), `sleep` и `TestRunner` не использованы.

### Метрики прогона `python run_hw.py hw01` (набор A, `out/hw01/metrics.json`)

| метрика | значение |
|---|---:|
| `md_files_total` / `files_ok` / `files_failed` | 28 / 27 / 1 |
| `links_total` | 82 |
| по категориям | local 54 · anchor 7 · url 9 · github 6 · mailto 3 · tel 1 · wikilink 1 · footnote 1 · unknown 0 |
| `broken_total` (local / anchor) | 7 (5 / 2) |
| `error_rate` | 0.036 |
| `extract_f1` (порог 0.95) | **1.000** |
| `classify_accuracy` (порог 0.98) | **1.000** |
| `duration_sec` / `throughput_files_per_sec` | 0.115 / 242.8 |
| `speedup` / `parallel_efficiency` / `workers_used` | 0.918 / 0.184 / 5 |

`speedup < 1` — честный результат: без HTTP разбор упирается в GIL, потоки не помогают.
Ожидание спеки 1.5–3× относится к прогону с сетевыми проверками.

### Токены разработки (`out/hw01/tokens_2026-08-17_03-51-18.md`)

| группа | requests | out | cache_create | cache_read | thinking |
|---|---:|---:|---:|---:|---:|
| агенты (16 запусков) | 468 | 615 393 | 2 142 180 | 55 287 872 | 260 761 |
| оркестрант | 104 | 82 523 | 398 515 | 26 394 202 | 5 882 |
| **всего** | **572** | **697 916** | **2 540 695** | **81 682 074** | **266 643** |

Итого по всем полям — 84 921 867 токенов.

## Документы

| Что | Где |
|---|---|
| ТЗ по таскам T-01…T-16 | `MemoryBank/tasks/TASK_hw01_modules_T01-T15.md` |
| Часть 1/2 — решения D1–D19 | `MemoryBank/specs/hw01_mdscan_reasoning_2026-08-16.md` |
| Часть 2/2 — архитектура | `MemoryBank/specs/hw01_mdscan_architecture_2026-08-16.md` |
| Правила разработки и тестирования | `MemoryBank/specs/hw01_mdscan_dev_test_spec_2026-08-16.md` |
| Ревью 2–5 (списки правок) | `MemoryBank/specs/hw01_mdscan_review{2,3,4,5}_fixes_2026-08-16.md` |
| Архитектура модуля | `Doc/Modules/mdscan/README.md` |
| CLI, конфигурация, отчёт | `Doc/Modules/mdscan/CLI.md` |
| Условие, метрики, выводы | `homework/hw01_mdlinks/README.md` |

⛔ `MemoryBank/specs/hw01_mdscan_spec_2026-08-16.md` — ранний вариант ТЗ, не использовать.

## Решения по ходу

- **2026-08-16**: HTTP-проверка в v1 (отключаемо ключом), «Dead Code» = мёртвые ссылки,
  код в `core/mdscan/`, консоль Strategy `rich` + ANSI-fallback, CLI только позиционный,
  golden-набор (эталонное дерево) делаем.
- **2026-08-16 (ревью 3–5)**: `MarkdownWorker(BaseObserver)`, отчёт строит главный поток после
  `join()`, `check(link, md_file)`, `HttpChecker` — один на прогон, вид цели определяется один раз
  правилом V5.
- **2026-08-17**: `file:///…` → `SKIPPED` (иначе ложная битая ссылка); `RepoInfo.scope` для цели-
  подкаталога; `linkify-it-py` в extra `hw01` (без него `gfm-like` гасит `linkify`); `wikilinks` —
  встроенное правило экстрактора, такого плагина в `mdit-py-plugins` нет; на Python 3.14
  `threading.Thread._context` конфликтует с одноимённым полем наследника.

## Открытые вопросы

- Нет. Возможное развитие (не в объёме ДЗ): прогон по организации `dsp-gpu` целиком с включённым
  HTTP — там конвейер и должен дать заявленный `speedup` 1.5–3×.
