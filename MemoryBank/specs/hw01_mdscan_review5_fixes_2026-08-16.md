# Ревью 5 — таски T-01…T-16 + спека разработки/тестирования + скилл `hw01-build` (перед запуском)

> **Дата**: 2026-08-16 · **Автор**: Кодо · Задача Alex: «прочитай таски и dev/test-спеку, найди скилл, глубокое ревью,
> сразу исправь, запусти скилл, потом всё проверь».
> **Статус**: 🟡 внесено, Alex не читал. Пометка в файлах — `🔧 р5` / `🔧 ревью 5`.
> Проверено против реального репо: Python 3.14 в `.venv`, deps hw01 / `ruff` / `mypy` **не установлены**,
> `core.metrics.f1_score/accuracy` есть, `homework/hw01_mdlinks/` содержит только README, транскрипты JSONL —
> `requestId` повторяется в нескольких строках.

## Что исправлено

| # | Где | Было | Стало / почему |
|---|---|---|---|
| 1 | волны, T-09 | ребро T-08 → T-09 при обоих тасках в волне 1 (скрытая зависимость: `MarkdownFileFinder` звал `GitAdapter.listed_md`) | `GitFileLister` (Protocol, владеет T-09, `discovery/git_file_lister.py`); `GitAdapter` подходит структурно; ребро снято; конструктор `MarkdownFileFinder(lister, extensions, respect_gitignore, include_nested)` |
| 2 | T-04 | `LoggingSetup.start(config)` — `ScanConfig` из T-03 (та же волна 0) | `start(log_file: Path \| None, level, header)` — примитивы; `LogFormat.formatter()`; логгер `core.mdscan` |
| 3 | T-06 ↔ T-07 | `MarkdownItHeadingSource` «реализует checking.HeadingSource» → импорт файла соседа по волне | реализация **структурная**, `checking.*` не импортировать; правило записано в dev-спеку §2.5 |
| 4 | T-01 | исключения (`UnknownFieldError`, `MarkdownReadError`, `GitUnavailableError`) объявлялись «где-то» в T-03/T-06/T-08 → нарушение «класс = файл» или три разных иерархии | `core/mdscan/errors.py` (T-01): `MdScanError` → `ConfigError` → `UnknownFieldError`; `MarkdownReadError`, `GitUnavailableError`, `GitHubDiscoveryError`; исключение из правила «класс = файл» как enums (dev-спека §2.1) |
| 5 | T-01 | не было `cli/validation/__init__.py`, `parsing/rules/__init__.py`; тест 7 запускал `pip install` | добавлены; тест 7 — проверка `pyproject` через `tomllib`, без установки |
| 6 | T-02, T-14, dev-спека §2.6/§3.4/§4 | `FixtureTreeBuilder` в `tests/hw01/support/` — но `run_hw.py hw01` (T-14) должен строить наборы A/B; продуктивный код не может импортировать `tests/` | генератор + `Expectations` → `homework/hw01_mdlinks/support/`; `tests/` импортирует оттуда; `homework/hw01_mdlinks/__init__.py` пишет только T-14 |
| 7 | T-02 | тест 1 «дважды подряд побайтово одинаково» — при переиспользовании каталога второй вызов ничего не строит | два разных `tmp_path`, сравнение по файлам |
| 8 | T-03 | нет файла `config_draft.py` (в части 2 §4 есть); неясно, где живёт `source.targets_resolved` и вложенные секции | `config_draft.py` добавлен; секции — в `scan_config.py` (конфиг-модуль); `targets_resolved` — служебное поле: не в yaml, не через `-поле:`, `ConfigPrinter` показывает отдельно |
| 9 | T-05 | нет файлов для `ValidationContext` / `ValidationResult`; не сказано, что V5 пишет `source.target`, как работает `source.kind != auto`, что при коде 2 файлы не создаются | `validation_context.py`, `validation_result.py`; уточнения V5/V6/V7/V8 и про `mdscan.yaml` при холодном старте |
| 10 | T-07 | нет таблицы «какой `LinkKind` → какой чекер»; `AnchorChecker` не мог прочитать целевой файл, не импортируя `parsing` | таблица выдачи `CheckerFactory`; `AnchorChecker` читает файл сам (`read_text(utf-8-sig)`); `HttpChecker` — `urllib`, без `requests` |
| 11 | T-08, T-13 | `keep_clones: false → удалить после прогона` — некому: у `RepositorySource` только `repositories()` | `RepositorySource.cleanup()` (no-op у локального); T-13 зовёт в `finally`; тест 8 проверяет обе ветки; `gh`/REST — инжектируемые вызываемые (`run_gh`, `http_get`) |
| 12 | T-11, T-13 | «не TTY → отключается», «выключен → не создаётся» — решение размазано между reporter и оркестратором | `ProgressFactory.create(config, source, stream) -> ProgressReporter \| None`; тесты 3–4 — на фабрику |
| 13 | T-12 | отчёту нужны цель, заголовок, время старта — их нет ни в `results`, ни в `summary` | `MarkdownReportBuilder(config, started_at)`; `build(results, summary)` без изменений |
| 14 | T-13 | тест 9 «файлы не созданы» противоречит D19 (холодный старт создаёт `mdscan.yaml`) | «лог и отчёт не созданы», `monkeypatch.chdir(tmp_path)` |
| 15 | T-14 | не сказано, откуда брать наборы A/B и как собрать `ScanConfig` без CLI | через `homework.hw01_mdlinks.support.FixtureTreeBuilder` и `YamlConfigLoader` → `ScanConfig.from_draft` |
| 16 | T-15 | `TokenMeter` — только Protocol, реализации в файлах нет; `TokenUsage`/`TokenTotals` не описаны; дубли `requestId` не учтены | `TranscriptTokenMeter`, `TokenUsage`/`TokenTotals` (frozen VO); **один `requestId` считается один раз** (проверено на реальном транскрипте: 5 дублей из 22 строк); `__init__.py` пакета создаёт T-15; тест 7 |
| 17 | dev-спека §3.3 | `monkeypatch` глобалей как основной приём | предпочтительна инъекция вызываемых в конструктор; заглушки чужих `Protocol` — duck typing |
| 18 | скилл | не учтено: `ruff`/`mypy` нет в `.venv`; голый `pytest` может резолвиться не в тот интерпретатор; агентам не сообщалась среда | шаг 0 п.3–4, промпт агента п.7–8, приёмка — новые пункты; порядок приёмки волны 0: сначала T-01 |
| 19 | часть 2 §4 | структура папок без `errors.py`, `git_file_lister.py`, `progress_factory.py`, `transcript_token_meter.py`, `validation_context/result.py`; генератор в `tests/` | синхронизировано (пометки «ревью 5») |

## Не менял (осознанно)

- Контракты из C4, принятые Alex в ревью 3 (`check(link, md_file)`, `render(results, summary)`, `MarkdownWorker(BaseObserver)`) — без изменений.
- Бюджет кода: +≈40 строк (`errors.py`, `GitFileLister`, `ProgressFactory`, `TranscriptTokenMeter`) — ≈1980, отдельного согласования не прошу, отмечаю.
- Порядок правил классификации, закон CLI, порядок V1…V10 — без изменений.

## Открытые вопросы к Alex (не блокируют волну 0)

1. Зависимости hw01 + `ruff`/`mypy` в `.venv` не стоят — ставлю `pip install -e .[hw01,dev]` **после приёмки T-01** по твоему ОК на гейте волны 0.
2. Python дома **3.14** (спека говорила 3.12/3.11 минимум) — PyYAML/GitPython/markdown-it-py на 3.14 должны встать колёсами; если нет — доложу.

---

*Ревью 5 · 2026-08-16 · Кодо*
