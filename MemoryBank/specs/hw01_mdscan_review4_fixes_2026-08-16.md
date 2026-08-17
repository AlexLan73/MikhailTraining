# Ревью 4 — таски T-01…T-16 + спека разработки/тестирования + скилл `hw01-build` ↔ спека (после ревью 3)

> **Дата**: 2026-08-16 · **Автор**: Кодо · Задача Alex: «глубокое ревью тасков на модули и тесты + скилл + спеку, сразу исправь».
> **Статус**: 🟡 внесено, Alex не читал (по команде Alex сразу переходим к запуску скилла).
> Пометка в файлах — `🔧 ревью 4`.

## Что исправлено

| # | Где | Было | Стало / почему |
|---|---|---|---|
| 1 | T-07 | `check(link, base_dir)` | `check(link, md_file)` — ✅ решение Alex (ревью 3); якорному чекеру нужен файл |
| 2 | T-12 | `render(summary, results)` | `render(results, summary)` — как в C4 и у `build()` |
| 3 | T-10 | `MarkdownWorker.process(task)` (свой цикл) | `MarkdownWorker(BaseObserver).on_item(task)`; контракты `CollectingObserver.results`, `StatisticsCollector.add/summary/snapshot`, `TaskQueue/ResultQueue` |
| 4 | T-01 | `SourceKind.YAML` | убран: `yaml` — ветка CLI (T-05), не вид источника |
| 5 | T-06 | 8 правил, порядок без `footnote` | 9 правил, порядок как в D8.3: wikilink → footnote → anchor → … ; `MarkdownReader.read` в контракте |
| 6 | T-05 | `usage_printer.py`; `validate(args)` | usage печатает `ConfigPrinter`; `ValidationContext(args, draft)`, V3 применяет overrides, **V5 классифицирует все цели** и пишет `targets_resolved` |
| 7 | T-08 | `SourceFactory` сам определял вид цели; `tracked_md` | читает `targets_resolved` (инвариант 23), по источнику на цель; `listed_md` с `--cached --others --exclude-standard`; тест пагинации REST |
| 8 | T-03 | `load()->dict`, нет точки сборки `ScanConfig` | `ConfigDraft(data, sources)`, `ScanConfig.from_draft`, `http.user_agent`, `keep_clones` |
| 9 | T-07/T-06 (скрытая зависимость в одной волне) | якорям нужны заголовки из парсера | `HeadingSource` (Protocol, владеет T-07) ← `MarkdownItHeadingSource` (T-06); тесты T-07 на заглушке |
| 10 | T-11/T-10 (скрытая зависимость) | прогресс читает `StatisticsCollector` | `ProgressSource` (Protocol, владеет T-11) + `ProgressSnapshot` (VO, T-01); реализует T-13 |
| 11 | T-07/T-10/T-11 (`Notifier`) | Protocol жил в T-11 (волна 2), нужен в волне 1 | `Notifier` + `NullNotifier` → T-01 (волна 0) |
| 12 | T-11 | `notifier.py` в файлах, нет rich/plain-отрисовки | `progress_view.py` + `rich_/plain_progress_view.py` (Strategy, D10), `clock` в конструкторе |
| 13 | T-13 | «пул parse», `run()`, фасад-функция | `Scanner` (Protocol, `scanner.py`), `ScanOrchestrator.scan()`, порядок фаз 0–3 по D1/D6, реализует `ProgressSource` |
| 14 | T-14 | README заполняет сам; метрики «функциями» с несуществующими именами | ключи метрик остаются, считаются `core.metrics.f1_score/accuracy`; README — T-16 |
| 15 | T-15 | читал только главный JSONL | + `subagents/agent-*.jsonl`, привязка по `TASK=` (D18, ревью 2) |
| 16 | нет таска | документация (часть 1 раздел 0 — обязательный шаг) | **T-16 · Документация** (README ДЗ, `Doc/Modules/mdscan/`, MemoryBank), волна 5 |
| 17 | нет таска | extra `hw01` в `pyproject`, пустые `__init__.py`, `tests/hw01/conftest.py` — кто? | T-01: extra + скелет пакетов; T-02: `conftest.py` (`reference_tree`, `--rebuild-fixtures`); остальные `conftest` не правят |
| 18 | волны | T-13 и T-14 в одной волне при зависимости T-13 → T-14 | волны 3 (T-13), 4 (T-14), 5 (T-16); ребро T-03 → T-08 |
| 19 | dev-спека §3.2 | «Singleton сбрасывается фикстурой» | глобального состояния нет (D2) — появилось = дефект |
| 20 | dev-спека | нет карты «чей контракт» | **§2.5** таблица владения `Protocol` (DIP), §2.6 общие файлы тестов; HTTP-сервер: режим 403 без UA, счётчик одновременных |
| 21 | скилл | `run_in_background: true` — нет такого параметра Agent; смещение только главного JSONL | агенты в фоне по умолчанию, волна одним сообщением; фиксировать список `subagents/*.jsonl` до старта; `git status`; возвраты через `SendMessage`; приёмка: контракт ↔ C4/§2.5, 5 прогонов для T-10/11/13, ruff/mypy; финал: `python -m core.mdscan Doc/Modules/mdscan` |
| 22 | часть 2 §4/§7/§8, C4 | нет новых файлов; SP-макеты как отдельная фаза | добавлены `config_draft.py`, `progress_snapshot.py`, `heading_source.py`, `markdown_it_heading_source.py`, `progress_source.py`; SP → вошли в таски; бюджет ≈ 1940 (+4 %) |
| 23 | часть 1 шапка/D16 | ТЗ = замороженный файл; макет→агент A1–A6 | ТЗ = `TASK_hw01_modules_T01-T15.md`; A1–A6 заменены T-01…T-16 |
