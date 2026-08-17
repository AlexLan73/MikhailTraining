# H-10 · Ревью соответствия спеке (hw01 «Markdown / Git Scanner»)

> **Статус**: 🟡 ЧЕРНОВИК — не читан Alex
> **Дата**: 2026-08-17 · **Таск**: H-10 (этап 2, волна 4) · **Автор**: агент-исполнитель
> **Сверялось с**:
> - [`hw01_mdscan_architecture_2026-08-16.md`](hw01_mdscan_architecture_2026-08-16.md) — раздел 0 (T1…T12, A1…A12), §1 CLI, §2 конфиг, C4, §4 структура, §6 инварианты 1–25, §8 бюджет, §9.1 метрики
> - [`hw01_mdscan_dev_test_spec_2026-08-16.md`](hw01_mdscan_dev_test_spec_2026-08-16.md) — §2.5 таблица владения `Protocol`
> - [`TASK_hw01_modules_T01-T15.md`](../tasks/TASK_hw01_modules_T01-T15.md) — контракты по таскам T-01…T-16
> - код `core/mdscan/**` (107 файлов), `core/tokenstat/**`, `homework/hw01_mdlinks/**`, тесты `tests/hw01/**`
>
> **Код не менялся** — таск ревью-документа. Прогон тестов: `python -m pytest tests/hw01 -q` →
> **427 passed, 4 skipped** (skip — `tests/hw01/test_http_live.py`, нет `MDSCAN_NETWORK=1`).

---

## Итог (короткая сводка)

| Показатель | Значение |
|---|---|
| Требований раздела 0 закрыто | **23 из 24** (T1…T12 — 12/12, A1…A12 — 11/12; A11 «документация» — частично) |
| Инвариантов §6 с доказывающим тестом | **23 из 25** полностью, ещё **2** частично (№1, №3) — «нет теста» ни у одного |
| Расхождений спека ↔ код | **15**, из них **критичных 3** (Р-08, Р-09, Р-13) |
| Публичных контрактов `Protocol` сверено | **15 из 15** — файл, имя, сигнатура совпадают; отклонения только в **диаграмме C4**, не в коде |

Общий вывод: код соответствует спеке. Все найденные расхождения — это **спека отстала от кода**
(правки ревью 5/6 и этапа 2 внесены в код, но не во все диаграммы) плюс три содержательных пункта,
где решение нужно от Alex.

---

## 1. Публичные контракты `Protocol` — контракт → файл → сигнатура по спеке → в коде

Основание: dev/test-спека §2.5 (владение) + архитектура C4 (сигнатуры). «Реализует» —
структурно (`Protocol`, без наследования), как и предписано §2.5.

| Контракт | Файл (есть?) | Сигнатура по спеке (§2.5 / C4) | В коде | Кто реализует | Кто использует | Вердикт |
|---|---|---|---|---|---|---|
| `Scanner` | `core/mdscan/scanner.py` ✅ | `scan(config) -> ScanSummary` | `scan(self, config: ScanConfig) -> ScanSummary` | `runtime/scan_orchestrator.ScanOrchestrator` | `__main__.main`, `homework/hw01_mdlinks/solution.Hw01Metrics` | ✅ совпадает |
| `Notifier` | `runtime/notifier.py` ✅ | `show(text) -> None` | `show(self, text: str) -> None` | `ProgressReporter`, `NullNotifier` | `MarkdownWorker`, `HttpChecker`, `CheckerFactory` | ✅ |
| `NullNotifier` (Null Object) | `runtime/null_notifier.py` ✅ | `show(text) -> None` | идентично | — | `ScanOrchestrator.scan` | ✅ |
| `ProgressSnapshot` (VO) | `models/progress_snapshot.py` ✅ | frozen VO, срез счётчиков | `@dataclass(frozen=True, slots=True)`, 8 полей: `repos_total/repos_done/md_found/parsed/task_qsize/result_qsize/links/broken` | — | `ProgressSource`, `ProgressView`, `StatisticsCollector.snapshot` | ✅ |
| исключения пакета | `core/mdscan/errors.py` ✅ | `MdScanError`, `ConfigError`, `UnknownFieldError`, `MarkdownReadError`, `GitUnavailableError`, `GitHubDiscoveryError` | все 6, иерархия `UnknownFieldError < ConfigError < MdScanError` | — | config, cli, parsing, source, runtime | ✅ |
| `GitFileLister` | `discovery/git_file_lister.py` ✅ | `listed_md(root, extensions) -> list[Path]` | `listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]` | `source/git_adapter.GitAdapter` (структурно) | `MarkdownFileFinder`, `PipelineRunner` | ✅ имена и типы совпадают |
| `LinkExtractor` | `parsing/link_extractor.py` ✅ | `extract(text) -> tuple[MdLink, ...]` | идентично | `MarkdownItLinkExtractor` | `MarkdownWorker` | ✅ |
| `LinkRule` | `parsing/rules/link_rule.py` ✅ | `matches(link) -> bool`, `kind -> LinkKind` | `matches(self, link: MdLink) -> bool`, `@property kind` | 10 правил `rules/rule_*.py` | `LinkClassifier` | ✅ код прав (C4 рисует `kind()` методом — см. Р-07) |
| `HeadingSource` | `checking/heading_source.py` ✅ | `headings(text) -> tuple[str, ...]` | идентично | `parsing/markdown_it_heading_source.MarkdownItHeadingSource` (структурно) | `AnchorChecker` | ✅ |
| `LinkChecker` | `checking/link_checker.py` ✅ | `check(link, md_file) -> None` | идентично | `LocalFileChecker`, `AnchorChecker`, `HttpChecker`, `NullChecker` | `CheckerFactory` → `MarkdownWorker` | ✅ |
| `RepositorySource` | `source/repository_source.py` ✅ | `repositories() -> Iterable[RepoInfo]` **+ `cleanup() -> None`** (р5) | оба метода | `LocalPathSource`, `RemoteRepoSource`, `GitHubOrgSource` | `SourceFactory`, `PipelineRunner`, `ScanOrchestrator._shutdown` | ✅ код прав (C4 без `cleanup` — Р-04) |
| `ValidationRule` | `cli/validation/rule.py` ✅ | `validate(ctx) -> ValidationResult` | идентично | 10 классов `rule_*.py` | `ValidationChain` | ✅ |
| `ProgressSource` | `runtime/progress_source.py` ✅ | `snapshot() -> ProgressSnapshot` | идентично | `ScanOrchestrator.snapshot` (поверх `PipelineRunner`/`StatisticsCollector`) | `ProgressReporter` | ✅ |
| `ProgressView` | `runtime/progress_view.py` ✅ | `draw(snapshot, messages)`, `clear()` | идентично + свободная `format_status()` (один источник формата) | `PlainProgressView`, `RichProgressView` | `ProgressReporter`, `ProgressFactory` | ✅ |
| `ConsoleRenderer` | `reporting/console_renderer.py` ✅ | `render(results, summary) -> None` | идентично + общие `summary_rows()` / `broken_rows()` | `PlainConsoleRenderer`, `RichConsoleRenderer` | `RendererFactory` → `ScanOrchestrator._publish` | ✅ |
| `TokenMeter` | `core/tokenstat/token_meter.py` ✅ | `start(label)`, `stop()`, `total` (property) | + `mark(agent, task)`, `by_agent()`, `report()` — расширение, не изменение | `TranscriptTokenMeter` | скил-оркестрант, `core/tokenstat/__main__.py` | ✅ (§2.5 перечисляет минимум; расширение не ломает потребителей) |

**Фабрики и модели C4 (не `Protocol`, но публичные)** — сверено отдельно:

| Класс | C4 | Код | Вердикт |
|---|---|---|---|
| `SourceFactory` | `for_config(config) -> list[RepositorySource]` | идентично | ✅ |
| `RendererFactory` | `create() -> ConsoleRenderer` | идентично | ✅ |
| `CheckerFactory` | `for_kind(kind) -> LinkChecker`, один на прогон | идентично, таблица `dict[LinkKind, LinkChecker]`, экземпляры общие | ✅ |
| `ProcessedRegistry` | `add_if_absent(key) -> bool`, потокобезопасный | идентично, `key: tuple[Path, Path]`, `threading.Lock` | ✅ |
| `BaseObserver` | `run()`, `on_item()*`, `on_error()`, `on_finish()`, поля queue/sentinel | идентично | ✅ |
| `MarkdownReportBuilder` | `build(results, summary) -> str` | идентично (конструктор берёт `config`, `started_at`) | ✅ |
| `StatisticsCollector` | `add(result)`, `summary()` | `summary(duration_sec, fail_on_broken)` | ⚠ Р-05 |
| `MarkdownWorker` | `on_item()`, `read()`, `extract()`, `check_links(links, md_file)`, `publish()` | `on_item()`, `_check_links(result)`; чтение/извлечение/публикация встроены | ⚠ Р-06 (приватная деталь) |
| `MdLink` | `target, origin, kind, line, status, detail, http_code` | все 7, `@dataclass(slots=True)` изменяемый | ✅ |
| `MdFileResult` | `repo, md_file, rel_path, links, error, seconds, thread_name`, `ok`, `broken_count` | все 7 + 2 property | ✅ |
| `RepoInfo` | `root, remote_url, web_url, is_nested` | + `scope: Path \| None` (р5) | ⚠ Р-03 |
| `MdTask` | `repo, md_file`, frozen | идентично | ✅ |
| `ScanSummary` | `counters, duration_sec, exit_code`, frozen | идентично | ✅ |
| `ScanConfig` | frozen VO, 10 секций | frozen + 10 вложенных frozen-секций, `from_draft()` — единственная сборка | ✅ |
| `HttpChecker` | `Semaphore slots`, `dict cache`, `str user_agent` | `_slots`, `_cache` под `Lock`, `_user_agent`, `_head_first`, `_cache_enabled` | ✅ |
| `AnchorChecker` | `dict headings_cache` | `_cache: dict[Path, tuple[str,...]]` под `Lock` | ✅ |

---

## 2. Требования T1…T12 и A1…A12 — код и тест

Формат: `файл:класс` (код) → `файл::тест` (доказательство).

### 2.1 Из условия курса (T1…T12)

| # | Требование | Код | Тест | Статус |
|---|---|---|---|---|
| T1 | Сканирует указанную папку | `source/local_path_source.py:LocalPathSource`; `discovery/markdown_file_finder.py:MarkdownFileFinder` | `test_source.py::test_directory_outside_git_gives_single_repo`, `::test_local_repository_root_detected`; `test_discovery.py::test_both_extensions_found_and_git_directory_skipped`, `::test_scope_limits_files_to_target_subdirectory` | ✅ закрыто |
| T2 | Находит **все** `.md` | `MarkdownFileFinder` (`_normalized`, `.md`/`.markdown`) | `test_fixture_tree.py::test_files_and_links_match_expectations`; `test_discovery.py::test_both_extensions_found_and_git_directory_skipped`, `::test_extensions_normalized`; `test_hw01_task.py::test_reference_run_matches_expectations` (28 файлов эталона) | ✅ |
| T3 | Извлекает `[text](url)` | `parsing/markdown_it_link_extractor.py:MarkdownItLinkExtractor` | `test_parsing.py::test_extract_returns_single_link_with_origin`, `::test_line_numbers_match_source`, `::test_extraction_f1_on_reference_tree` (f1 = 1.0) | ✅ |
| T4 | Извлекает `file:///…` | `parsing/rules/rule_file_url.py:FileUrlRule` → `LinkKind.LOCAL`; экстрактор отключает `validateLink` | `test_parsing.py::test_classification_table` (параметризован); `test_checking.py::test_file_uri_is_skipped` | ✅ |
| T5 | Проверяет локальные ссылки на существование | `checking/local_file_checker.py:LocalFileChecker`; `checking/anchor_checker.py:AnchorChecker` | `test_checking.py::test_local_target_existence_defines_status`, `::test_broken_local_link_explains_reason`, `::test_anchor_matches_github_slug`, `::test_local_link_with_anchor_checks_target_file` | ✅ |
| T6 | Проверяет внешние HTTP (HEAD или GET) | `checking/http_checker.py:HttpChecker`, `method: head_then_get` | `test_checking.py::test_http_codes_map_to_statuses` (200/301/404/500 на `support/http_server.py`), `::test_head_not_allowed_falls_back_to_get`, `::test_user_agent_is_sent` | ✅ |
| T7 | Статус-коды в отчёте | `MdLink.http_code`; `reporting/markdown_report_builder.py:_broken_http_section` / `_access_denied_section`; `reporting/console_renderer.py:broken_rows` | `test_reporting.py::test_broken_http_link_reported_with_status_code`, `::test_access_denied_codes_go_to_separate_section` | ✅ |
| T8 | Красивый отчёт в консоли | `reporting/rich_console_renderer.py`, `plain_console_renderer.py`, `renderer_factory.py` | `test_reporting.py::test_rich_renderer_used_when_available`, `::test_factory_falls_back_to_plain_without_rich`, `::test_plain_renderer_colors_only_for_tty`, `::test_tables_have_consistent_column_count` | ✅ |
| T9 | Список сломанных ссылок | секции «Битые локальные» / «Битые HTTP» / «Таймауты» / «401-403-429» + `broken_rows` | `test_reporting.py::test_report_contains_all_required_sections`, `::test_broken_local_links_listed_with_line_and_detail`, `::test_timeout_has_its_own_section` | ✅ |
| T10 | Относительные пути — от файла-владельца | `LocalFileChecker._base_of(md_file.parent)` + `_resolve` (`os.path.normpath`) | `test_checking.py::test_parent_relative_path_resolved_from_owner_file`, `::test_same_target_from_other_file_is_broken` | ✅ |
| T11 | Таймауты HTTP | `HttpChecker._timeout_sec` из `http.timeout_ms`, статус `TIMEOUT` | `test_checking.py::test_hanging_endpoint_gives_timeout`; `test_http_live.py::test_tiny_timeout_gives_timeout_not_broken` (network) | ✅ (ограничение по DNS/редиректам — Д-9, документирует H-12) |
| T12 | Обработка ошибок сети: 404/500/timeout различимы | `HttpChecker._probe`; `CheckStatus.OK/BROKEN/TIMEOUT` | `test_checking.py::test_http_codes_map_to_statuses` + `::test_hanging_endpoint_gives_timeout` + `::test_closed_port_does_not_raise`, `::test_malformed_url_is_broken` | ✅ |

### 2.2 Добавленные нами (A1…A12)

| # | Требование | Код | Тест | Статус |
|---|---|---|---|---|
| A1 | Обход git-репо; вложенные по флагу | `discovery/nested_repo_finder.py:NestedRepoFinder`; `MarkdownFileFinder._excluded_roots`; `runtime/pipeline_runner.py:PipelineRunner._queue_files` | `test_discovery.py::test_nested_file_queued_once_when_included`, `::test_nested_file_absent_for_main_repo_when_excluded`, `::test_sibling_of_nested_repo_not_lost`, `::test_nested_finder_accepts_git_file_submodule`; `test_source.py::test_submodule_file_and_nested_clone_are_recognised` | ✅ |
| A2 | Удалённый репозиторий и организация (SSH/HTTPS) | `source/remote_repo_source.py`, `source/github_org_source.py` (+ `clone_workers`, H-13), `source_factory.py` | `test_source.py::test_clone_uses_configured_depth`, `::test_gh_discovery_applies_filters`, `::test_api_discovery_reads_all_pages`, `::test_org_clones_repositories_in_parallel`, `::test_org_cleanup_removes_all_children`; боевой прогон — `hw01_h01_org_run_2026-08-17.md` | ✅ |
| A3 | Двухстадийный конвейер, два сентинела, порядок завершения | `runtime/pipeline_runner.py:PipelineRunner._drain`, `runtime/sentinels.py`, `base_observer.py` | весь `test_pipeline.py` (11 тестов) | ✅ |
| A4 | `workers.discover` / `workers.parse` / `http.workers` | `config/scan_config.py:WorkersConfig`, `HttpConfig.workers`; `PipelineRunner.__init__`/`_discover`; `HttpChecker._slots` | `test_pipeline.py::test_one_sentinel_per_worker_stops_all`; `test_checking.py::test_semaphore_limits_concurrent_requests`; `test_hw01_task.py::test_all_parse_workers_took_part`; замеры — `hw01_h04_baseline_2026-08-17.md`, `hw01_h07_after_2026-08-17.md`, инструмент `tests/hw01/support/bench_scan.py` | ✅ |
| A5 | Перехват исключений + лог каждого шага, лог по умолчанию включён | `log_setup/logging_setup.py` (`QueueHandler`/`QueueListener`), `log_format.py`; `MarkdownWorker.on_item`, `PipelineRunner._scan_repo`, `ScanOrchestrator.scan/_publish/_shutdown`, `__main__.main` | `test_logging.py` (11 тестов: 5 потоков → ровно 1000 записей, формат, шапка, идемпотентный `stop`); `test_orchestrator.py::test_info_level_writes_no_debug_records`, `::test_debug_level_writes_a_record_for_every_link`, `::test_missing_target_gives_exactly_one_warning` | ✅ |
| A6 | Markdown-отчёт файлом, имя `<цель>_<дата>_<время>` | `log_setup/log_naming.py:LogNaming`; `ScanOrchestrator._scope/_log_file` | `test_logging.py::test_log_naming_build`, `::test_log_naming_shares_stamp_between_log_and_report`; `test_orchestrator.py::test_end_to_end_writes_log_and_report` | ✅ |
| A7 | `mdscan.yaml` + `-поле:значение` | `config/yaml_config_loader.py`, `cli_override_applier.py`, `config_draft.py`, `defaults.py`, `config_printer.py` | `test_config.py` (18 тестов: холодный старт с комментариями, приоритет defaults<yaml<CLI, неизвестное поле → похожие, значение с двоеточием, frozen) | ✅ |
| A8 | Закон CLI: 4 ветки, первый аргумент — цель, коды 0/1/2 | `cli/argument_parser.py`, `cli/validation/chain.py` (V1…V10 в порядке §1.3), `__main__.py` | `test_cli.py` (29 тестов, включая матрицу аргументов и каждое правило V1…V10) | ✅ |
| A9 | Прогресс: статус по таймеру + строка модуля TTL 5 с | `runtime/progress_reporter.py`, `progress_factory.py`, `progress_view.py` + 2 вида | `test_progress.py` (17 тестов: TTL, две строки, потокобезопасность `show`, `stop` без `start`, битый view не убивает поток); `test_orchestrator.py::test_progress_flag_does_not_change_report` | ✅ (`style: panel` не реализован — Р-08) |
| A10 | Подсчёт токенов, отчёт отдельным файлом | `core/tokenstat/**` (`TranscriptTokenMeter`, `TranscriptReader`, `TokenAggregator`, `TokenReportBuilder`) | `test_tokenstat.py` (15 тестов: окно `start/stop`, группировка по агентам, дубль `requestId` один раз, битая строка → WARNING и продолжаем) | ✅ |
| A11 | Документация: README ДЗ с реальными числами + `Doc/Modules/mdscan/` | `homework/hw01_mdlinks/README.md`, `Doc/Modules/mdscan/README.md`, `Doc/Modules/mdscan/CLI.md` | автотеста нет по природе требования | ⚠ **частично**: все разделы заполнены, числа не «работает», но числа **устарели** (README ДЗ: `workers.parse = 5`, `speedup 0.918`, `workers_used 5`; `CLI.md` §7.3 пример шапки `parse=5 http=5`) при умолчаниях 10/10 и `Hw01MdLinks.parse_workers = 10`. Раздел «Производительность» и токены — по плану H-12 |
| A12 | Метрики качества извлечения на golden-наборе | `homework/hw01_mdlinks/solution.py:Hw01Metrics.quality` на `core.metrics.f1_score`/`accuracy`; ожидания — `support/expectations.py` | `test_parsing.py::test_extraction_f1_on_reference_tree` (f1 ≥ 0.95), `::test_classification_accuracy_on_reference_tree` (acc ≥ 0.98); `test_hw01_task.py::test_quality_metrics_pass_thresholds` | ✅ |

---

## 3. Инварианты §6 (1–25) — чем доказан

| # | Инвариант (коротко) | Тест | Статус |
|---|---|---|---|
| 1 | `workers.parse` / `workers.discover` / `http.workers` — верхние границы | `test_checking.py::test_semaphore_limits_concurrent_requests` (http.workers=2 → в пике 2); `test_source.py::test_org_clones_repositories_in_parallel` (пиковая одновременность клонов); `test_pipeline.py::test_one_sentinel_per_worker_stops_all` (число воркеров) | ⚠ **частично**: прямого теста «одновременных разборов ≤ `workers.parse`» нет (число воркеров задано конструктивно, пик не замеряется) |
| 2 | Результат публикует сам worker | `test_pipeline.py::test_result_not_modified_after_put` (наблюдатель получает **тот же** объект от воркера), `::test_all_tasks_produce_results`; `MdFileResult.thread_name` = `parse-N` | ✅ |
| 3 | `END_DISCOVERY` — после всех discover-futures, ровно один раз | `test_pipeline.py::test_one_sentinel_per_worker_stops_all` (`gets == задачи + воркеры`); `test_orchestrator.py::test_end_to_end_counters_match_expectations` (сквозной прогон) | ⚠ **частично**: «ровно один раз на воркер» доказано; «строго после `future.result()` каждого источника» — только сквозным прогоном, отдельного теста нет |
| 4 | `END_RESULTS` — после `TaskQueue.join()` и выхода воркеров, ровно один раз | `test_pipeline.py::_shutdown_tail` (утверждает «воркер не жив» **до** `put(END_RESULTS)`), используется в 9 тестах; `test_orchestrator.py::test_report_built_after_collector_join` | ✅ |
| 5 | На каждый `get()` — `task_done()` в `finally`; `join()` не виснет | `test_pipeline.py::test_task_done_matches_get` (`_CountingQueue`), `::test_task_done_called_for_sentinel`, хелпер `_join_queue` с таймаутом | ✅ |
| 6 | MD-файл попадает в задачи ровно один раз | `test_discovery.py::test_nested_file_queued_once_when_included`, `::test_repeated_repository_gives_no_second_tasks`, `::test_symlink_to_scanned_directory_gives_no_duplicates`, `::test_same_named_directory_kept` | ✅ |
| 7 | Ошибка одного файла публикуется и не роняет прогон | `test_pipeline.py::test_read_error_published_and_others_processed`, `::test_checker_error_published`; `test_parsing.py::test_reference_tree_broken_byte_file_is_reported` | ✅ |
| 8 | Отчёт строится только после `reporter.join()` | `test_orchestrator.py::test_report_built_after_collector_join` | ✅ |
| 9 | Два прогона на одном дереве → одинаковый отчёт | `test_orchestrator.py::test_two_runs_produce_same_report`; `test_reporting.py::test_report_is_deterministic`, `::test_report_order_independent_of_input_order`; `test_hw01_task.py::test_repeated_run_gives_same_metrics` | ✅ |
| 10 | Ссылки внутри code-блоков не извлекаются | `test_parsing.py::test_links_inside_code_are_not_extracted`, `::test_indented_code_block_is_not_extracted`; `test_parsing.py::test_bare_filenames_are_not_linkified` (fuzzy-linkify выключен) | ✅ |
| 11 | После завершения `threading.enumerate()` без наших потоков | `test_pipeline.py::test_no_threads_left_after_shutdown`; `test_orchestrator.py::test_no_threads_left_after_scan` | ✅ |
| 12 | `ScanConfig` неизменяем | `test_config.py::test_6_scan_config_is_frozen`, `::test_6_lists_become_tuples`; `test_models.py::test_value_objects_are_frozen` | ✅ |
| 13 | Приоритет defaults < yaml < cmdline | `test_config.py::test_2_yaml_overrides_defaults_and_cli_overrides_yaml`, `::test_8_defaults_are_declared_once`, `::test_7_printer_shows_usage_examples_and_every_field` (колонка источника) | ✅ |
| 14 | После `put()` владелец объект не изменяет | `test_pipeline.py::test_result_not_modified_after_put` (полный снимок состояния на момент приёма) | ✅ |
| 15 | Первый аргумент — всегда цель, иначе код 2 | `test_cli.py::test_4_first_argument_override_is_error`, `::test_v2_first_arg_must_be_target`, `::test_5_second_positional_is_error`, `::test_v5_unknown_target_rejected` | ✅ |
| 16 | Строка зоны 2 гаснет через `message_ttl_sec` и не ломает таблицу | `test_progress.py::test_message_disappears_after_ttl`, `::test_message_ttl_counted_from_show_time`, `::test_new_message_replaces_old_when_one_line`, `::test_stop_clears_view_and_joins_thread` | ✅ |
| 17 | `respect_gitignore: true` → игнорируемые не попадают, untracked попадают | `test_source.py::test_listed_md_keeps_untracked_and_skips_ignored`; `test_discovery.py::test_git_lister_used_when_gitignore_respected`, `::test_tree_walk_used_when_repository_outside_git`, `::test_tree_walk_used_when_git_lister_fails` | ✅ |
| 18 | `task_done()` только после `ResultQueue.put(result)` | `test_pipeline.py::test_slow_worker_result_not_lost` (сентинелы уже в очереди, результатов нет), `::test_task_done_matches_get` | ✅ |
| 19 | Каждый parse-worker получает свой `END_DISCOVERY` и делает `task_done()` | `test_pipeline.py::test_one_sentinel_per_worker_stops_all`, `::test_task_done_called_for_sentinel` | ✅ |
| 20 | К моменту `put()` все ссылки проверены | `test_pipeline.py::test_slow_worker_result_not_lost` (шлюз в чекере), `::test_checker_error_published` | ✅ |
| 21 | Организация > `page_size` → полный список (пагинация) | `test_source.py::test_api_discovery_reads_all_pages` | ✅ |
| 22 | `HttpChecker` один на прогон: одновременных запросов ≤ `http.workers` | `test_checking.py::test_semaphore_limits_concurrent_requests`, `::test_for_kind_returns_shared_instances` | ✅ |
| 23 | `SourceKind` определяется один раз (V5) и пишется в конфиг | `test_cli.py::test_v5_explicit_kind_skips_detection`, `::test_10_yaml_mixed_list_resolves_every_kind`; `test_source.py::test_factory_creates_source_per_resolved_target` (фабрика берёт готовый `targets_resolved`) | ✅ |
| 24 | Якорь по GitHub-slug; `a.md#x` — файл + заголовок в нём | `test_checking.py::test_anchor_matches_github_slug`, `::test_local_link_with_anchor_checks_target_file`, `::test_anchor_slug_ignores_inline_markup_in_heading`, `::test_headings_read_once_per_file` | ✅ |
| 25 | Отчёт/консоль — главный поток после `join()`, collector сам не пишет | `test_orchestrator.py::test_report_built_after_collector_join`; `StatisticsCollector` не имеет ни `print`, ни записи файлов (проверено чтением) | ✅ |

**Итого**: 23 инварианта закрыты полностью, 2 (№1 и №3) — частично; «нет теста» — ни у одного.

---

## 4. Расхождения спека ↔ код

| # | Спека говорит | Код делает | Кто прав | Предложение |
|---|---|---|---|---|
| Р-01 | C4 и §4 (комментарий `rules/`) и §8 («9 правил») перечисляют **9** `LinkRule` | **10** правил: добавлен `parsing/rules/rule_other_scheme.py:OtherSchemeRule` (`data:`, `javascript:`, `ftp:` → `UNKNOWN`), стоит между `FileUrlRule` и `LocalPathRule` (Д-1 ревью 6) | **код** | Обновить C4 (`LinkRule <\|.. OtherSchemeRule`), §4, §8 и докстринг `LinkClassifier.default` («канонический порядок 9 правил» → 10) |
| Р-02 | §4 «Структура папок» | В коде есть, в §4 нет: `runtime/pipeline_runner.py` (упомянут только в §10 как митигация), `discovery/resolved_path_cache.py` (H-05), `parsing/rules/rule_other_scheme.py`, `homework/hw01_mdlinks/solution.py`, `core/tokenstat/__main__.py`, `tests/hw01/support/bench_*.py` (4 файла) | **код** | Дописать §4; `PipelineRunner` перевести из §10 «риск» в §4 и C3/C4 как штатный компонент |
| Р-03 | C4 `RepoInfo`: `root`, `remote_url`, `web_url`, `is_nested` | + `scope: Path \| None` — цель-подкаталог репозитория (р5); устанавливается в `LocalPathSource`, читается `MarkdownFileFinder.find` | **код** | Добавить поле в C4 и абзац в §2.0 (поведение «цель — подкаталог») |
| Р-04 | C4 `RepositorySource`: только `repositories()` | `repositories()` **+ `cleanup()`** (ревью 5 — есть в §4 и dev-спеке §2.5, но не в C4) | **код** | Дополнить C4 |
| Р-05 | C4 `StatisticsCollector.summary() ScanSummary` | `summary(duration_sec: float, fail_on_broken: bool)` + `add_repo`, `repo_done`, `md_found`, `snapshot(task_qsize, result_qsize)` | **код** (иначе статистика знала бы про часы и конфиг — SRP) | Поправить сигнатуру в C4 |
| Р-06 | C4 `MarkdownWorker`: `read()`, `extract()`, `check_links(links, md_file)`, `publish(result)` | `on_item()` + `_check_links(result)`; чтение/извлечение/публикация встроены в `on_item` | **код** (это приватные детали; класс 135 строк) | Убрать из C4 приватные методы либо привести к факту |
| Р-07 | C4 `LinkRule`: `+kind() LinkKind` (метод) | `@property kind` | **код** (правило 09: геттер = property) | Пометить в C4 как property |
| Р-08 🔴 | §2: `progress.style: line — одна строка \| panel — рамка \| off` | Различается **только** `off` (`progress_factory.STYLE_OFF`); `line` и `panel` дают одно и то же — вид выбирается по наличию `rich` (`RichProgressView`/`PlainProgressView`) | **спека** (заявленное значение не работает) | Решение Alex: (A) убрать `panel` из конфига и §2/CLI.md, (B) реализовать `panel` как отдельный `ProgressView`. Тест на выбор вида по `style` тоже отсутствует |
| Р-09 🔴 | §2.0: `source.auth` — «как подключаемся к репозиториям» (общая таблица `auto/ssh/https/token`) | `auth` читается **только** в `GitHubOrgSource._clone_url`. Ветка `remote_repo` (`RemoteRepoSource` через `SourceFactory._remote`) клонирует адрес **как дан**, `auth` игнорирует | **спека неточна** (поведение осмысленно: адрес задан явно) | Уточнить в §2.0 и `CLI.md`: «`auth` влияет только на раскрытие организации; для одиночного репозитория протокол задаётся самим адресом». Иначе `-source.auth:ssh` на `https://…/repo.git` молча ничего не меняет |
| Р-10 | Раздел 0.3: `report.console` — публичный ключ конфигурации (р5) | Реализован (`ScanOrchestrator._publish`), но **ни одного теста** нет: `grep "report.console\|console=" tests/hw01` пусто | **код** (поведение верное), **пробел в тестах** | Добавить тест «`report.console: false` → в stdout ничего, файл отчёта на месте» (решение Alex — этого нет ни в одном таске) |
| Р-11 | §8 бюджет: `core/mdscan` ≈ 1750 строк, всего ≈ 1940 | Факт (все строки, с докстрингами): `core/mdscan` **6288**, `core/tokenstat` **613**. По пакетам против цели: `config` 1055/200, `cli` 727/180, `runtime` 1187/360, `source` 726/190, `parsing` 692/160, `reporting` 542/160, `checking` 480/130, `discovery` 344/120 | **спека** (бюджет нереалистичен для принятого стиля: докстринги-обоснования по правилам 05/09 занимают ~половину) | Пересогласовать бюджет с Alex, считая **только** исполняемые строки, либо признать §8 справочным. Кандидаты на дробление ведёт H-11 |
| Р-12 | Правило 11 (`.claude/rules/11-exceptions-logging.md`): имена потоков по стадиям `discover-1`, `parse-2` | `parse-N` верно; пул обхода — `thread_name_prefix="discover"` → `discover_0`, `discover_1` (нумерация с 0, подчёркивание) | **спека** формально не соблюдена | Косметика, уже зафиксировано как Д-11 (H-11). Правка на 1 строку: `thread_name_prefix="discover-"` + смещение не задаётся API `ThreadPoolExecutor` |
| Р-13 🔴 | A11: «README ДЗ с реальными числами», `Doc/Modules/mdscan/` | Числа устарели: `homework/hw01_mdlinks/README.md` — `duration_parallel_sec` при `workers.parse = 5`, `speedup 0.918`, `workers_used 5`, `duration_sec 0.115`; `Doc/Modules/mdscan/CLI.md` §7.3 пример шапки лога `workers : discover=5 parse=5 http=5`. Умолчания — `parse=10`, `http.workers=10`; `Hw01MdLinks.parse_workers = 10`; после H-05/H-06 время другое | **код/умолчания** | Это ровно объём H-12 (п. 1, 3, 6, 7). До его выполнения A11 считать **не закрытым**. `CLI.md` в остальном уже актуален (есть `report.console`, `workers.parse=10`, секция 401/403/429, примечание про `linkify`) |
| Р-14 | §9.1: `broken_total` (р5: «все BROKEN+TIMEOUT») | Так и есть, но формулировка не объясняет: `broken_local + broken_anchor + broken_http + timeout_http` **не равно** `broken_total`, если битой оказалась ссылка категории без своей корзины (`WIKILINK`, `FOOTNOTE_URL`, `UNKNOWN` — они `SKIPPED`, но `MAILTO`/`TEL` тоже без корзины). Плюс `MdFileResult.broken_count` = BROKEN+TIMEOUT, а консоль разводит «битых» и «таймаутов» (Д-4) | **код**, спека неполна | Дописать в §9.1 одну строку про соотношение счётчиков; H-12 уже обязан задокументировать Д-4 |
| Р-15 | Д-7 (список дефектов волны 1): «`std::string`/`af::array` из автодоков → битые локальные, ограничение классификатора» | **Уже закрылось** побочным эффектом `OtherSchemeRule`: схема из ≥2 букв + `:` → `UNKNOWN` → `SKIPPED`. Проверено: `std::string` → `unknown`, `af::array` → `unknown`, `C:/tmp/x.md` → `local` (односимвольная схема исключена регулярно) | **код** | Снять Д-7 из открытых находок H-11 / отметить закрытым; желателен тест-закрепитель (`test_parsing.py::test_other_schemes_are_unknown_not_local` покрывает `data:`/`javascript:`, но не `std::`) |

Критичные (🔴): **Р-08**, **Р-09**, **Р-13**.

---

## 5. Что проверено дополнительно и совпало (без расхождений)

- **§2 конфигурация**: все 10 секций и 39 полей `config/defaults.py` совпадают со спекой **значение в значение**
  (`workers.parse: 10`, `http.workers: 10`, `progress.message_ttl_sec: 5.0` float, `report.console: true`,
  `clone_dir: out/hw01/_clones`, `page_size: 100`) — сверено выводом `Defaults().tree`.
- **§1.3 цепочка V1…V10**: порядок в `ValidationChain.default()` дословно как в спеке
  (`ArgCount → FirstArgIsTarget → OverrideSyntax → PathNormalization → TargetKind → PathIsDirectory →
  PathReadable → GitRepository → OutputDir → WritePermission`); справка выполняет первые 3 (`HELP_RULES = 3`) —
  соответствует §1.1 «`-h` = как без аргументов» + требованию «ошибка в `-поле:значение` видна и при `-h`».
- **§1.4 коды возврата**: `0/1` — `StatisticsCollector.summary` через `fail_on_broken`; `2` — `ValidationResult.exit_code`;
  `3` — `INTERNAL_ERROR_CODE` в `ScanOrchestrator` (прогон и запись отчёта) и в `__main__` (последний рубеж).
- **§9.1 метрики**: все 24 имени присутствуют в `_ADDITIVE_COUNTERS` + вычисляемые
  (`broken_ratio`, `error_rate`, `duration_sec`, `throughput_files_per_sec`); служебный `repos_done` наружу не выдаётся.
- **§5 паттерны**: Template Method (`BaseObserver.run`), Observer (`MarkdownWorker`, `CollectingObserver`),
  Strategy (5 контрактов), CoR (`ValidationChain`, `LinkClassifier`), Facade+Controller (`ScanOrchestrator`),
  Adapter (`GitAdapter`, `TranscriptReader`), Factory Method (`CheckerFactory`, `RendererFactory`, `SourceFactory`,
  `ProgressFactory`), Builder (`MarkdownReportBuilder`, `TokenReportBuilder`), Null Object (`NullChecker`, `NullNotifier`),
  Command (`MdTask`), VO, Registry (`ProcessedRegistry`) — **все на месте**.
- **Правки этапа 2 присутствуют и согласованы**: `OtherSchemeRule` (Д-1), `ResolvedPathCache` + абсолютные пути из
  `MarkdownFileFinder` (H-05/G-D), блочный `MarkdownItHeadingSource` (H-05/G-H), ленивое логирование под
  `logger.isEnabledFor` и единственный `WARNING` на битую ссылку у воркера (H-06/Д-3), `GitHubOrgSource(clone_workers)`
  + `as_completed` (H-13/Д-2), `report.console` (р5), `RepoInfo.scope` (р5), секция «HTTP 401/403/429» в отчёте и
  «(доступ закрыт?)» в консоли (ревью 6), `broken_total` (р5), `workers.parse = 10` (р6).

---

*H-10, 2026-08-17. Правки не вносились; их утверждает Alex.*
