# H-11 · Ревью кода hw01 (mdscan / tokenstat / ДЗ / тесты)

> **Статус: 🟡 ЧЕРНОВИК — не читан Alex.** Правки **не внесены**: их утверждает Alex.
> Дата: 2026-08-17 · Таск: [`TASK_hw01_hardening_H01-H12.md`](../tasks/TASK_hw01_hardening_H01-H12.md) H-11
> Состояние кода на момент ревью: `pytest tests/hw01 -q` → **427 passed, 4 skipped**;
> `ruff check core tests/hw01 homework` → чисто; `mypy core homework` → 141 файл, ошибок нет.

---

## 0. Что смотрел и чем

| Инструмент | Результат |
|---|---|
| `python -m ruff check core tests/hw01 homework` | All checks passed |
| `python -m mypy core homework` | Success: no issues found in 141 source files |
| `python -m pytest tests/hw01 -q` | 427 passed, 4 skipped (живые HTTP без `MDSCAN_NETWORK=1`) |
| глазами | все ~120 файлов `core/mdscan/**`, `core/tokenstat/**`, `homework/hw01_mdlinks/**`, `tests/hw01/**` |
| AST-скрипты | ненужные публичные методы (счёт обращений `.имя`), классы >120 строк, файлы с >1 классом, тесты без `assert` |

**Объём продуктивного кода** (без тестов): `core/mdscan` 6371 · `core/tokenstat` 613 ·
`homework/hw01_mdlinks` 881 = **7865 строк**. Тесты `tests/hw01` — 6828 строк (в бюджет не входят).
По пакетам: `runtime` 1270 · `config` 1055 · `cli` **727** · `source` 726 · `parsing` 692 ·
`reporting` 542 · `checking` 480 · `discovery` 344 · `log_setup` 161 · `models` 149 · `enums` 70.

> Известный кандидат из таска «`cli/` 417 строк против бюджета 180» — **число устарело**:
> сейчас `cli/` = 727 строк на 17 файлов (10 правил V1…V10 + цепочка + контекст + разбор argv).
> Это не разбухание одного класса, а 10 маленьких Strategy-классов по 20–120 строк; предлагаю
> переформулировать бюджет, а не резать правила.

---

## 1. Находки — 🔴 высокий приоритет

### 🔴-1 · Консоль считает «битых» сама, а не берёт числа у `StatisticsCollector` — числа на экране и в отчёте расходятся

**Где**: `core/mdscan/reporting/console_renderer.py:40-54` (`summary_rows`) против
`core/mdscan/runtime/statistics_collector.py:93-106` (`summary`) и `:122-134` (`_add_link`).

**Что**: `summary_rows` заново обходит `results` и считает `links`, `broken`, `timeouts`, `failed`,
хотя те же числа уже лежат в `summary.counters`. Определения при этом **разные**:
консоль печатает `битых` = только `CheckStatus.BROKEN`, а `counters["broken_total"]` = `BROKEN + TIMEOUT`.

Проверено прямым вызовом (файл с одной 404-ссылкой и одним таймаутом):

```text
counters: broken_total = 2 · timeout_http = 1 · broken_http = 1
консоль:  битых | 1        таймаутов | 1
MdFileResult.broken_count = 2
```

**Почему это проблема**: это ровно тот случай, который запрещают правило 07 и **докстринг самого
`StatisticsCollector`**: «считаем здесь, а не в отчёте и не в консоли — иначе „битых 7“ на экране и
„битых 6“ в файле разъедутся и никто не поймёт, кто прав». Сейчас источников истины два, и они уже
расходятся. Это же объясняет расхождение, зафиксированное в H-01 (Д-4) и H-02 (Д-4) как «косметика»:
причина не в определении `broken_total`, а в дубле вычислений.

**Предложение**: `summary_rows(summary)` берёт числа **только** из `summary.counters`
(`md_files_total`, `links_total`, `broken_total`, `timeout_http`, `files_failed`); `results`
остаются нужны лишь `broken_rows` для списка строк. Решение по семантике `broken_total`
(Д-4) принимает Alex, но считаться она обязана в одном месте.

---

## 2. Находки — 🟠 средний приоритет

### 🟠-1 · Коды «доступ закрыт» заданы в двух местах

**Где**: `core/mdscan/reporting/markdown_report_builder.py:41`
(`_ACCESS_DENIED_CODES = frozenset({401, 403, 429})`) и
`core/mdscan/reporting/plain_console_renderer.py`-путь → `console_renderer.py:66`
(`if link.http_code in (401, 403, 429)`).

**Почему**: решение Alex (ревью 6) записано двумя литералами в двух файлах одного пакета.
Добавили `451` в отчёт — консоль об этом не узнает. Правило 07 прямо про это.

**Предложение**: один `ACCESS_DENIED_CODES` (публичный, в `console_renderer.py` или отдельном
`reporting/http_codes.py`), оба потребителя импортируют его.

### 🟠-2 · Набор «ссылка не работает» определён трижды

**Где**: `core/mdscan/models/md_file_result.py:236` `_BROKEN_STATUSES = {BROKEN, TIMEOUT}` ·
`core/mdscan/runtime/markdown_worker.py:206` `_LOUD_STATUSES = {BROKEN, TIMEOUT}` ·
`core/mdscan/reporting/console_renderer.py:62` `not in (BROKEN, TIMEOUT)`.

**Почему**: один и тот же смысл, три определения. Если Alex решит по Д-4 вынести `TIMEOUT` из
«битых», придётся править три файла и легко забыть третий.

**Предложение**: одна константа рядом с `CheckStatus` (`enums/check_status.py` или
`models/md_file_result.py` как публичная `BROKEN_STATUSES`), три потребителя её импортируют.

### 🟠-3 · `_scope()` — имя прогона считается двумя разными реализациями

**Где**: `core/mdscan/runtime/scan_orchestrator.py:154-159` и
`core/mdscan/reporting/markdown_report_builder.py:196-201`.

**Что**: одинаковый алгоритм («последний сегмент пути/URL»), но у оркестратора есть
`removesuffix(".git")` и fallback `"yaml"`, у отчёта — нет и fallback `"mdscan"`. Для цели
`git@github.com:org/radar.git` лог получит `radar`, а заголовок отчёта — `radar.git`.

**Предложение**: один Value Object / статический метод (напр. `models.ScanScope.of(config)`),
оба потребителя зовут его; fallback задаётся аргументом.

### 🟠-4 · Секции «Битые HTTP» и «HTTP 401/403/429» — копия друг друга

**Где**: `core/mdscan/reporting/markdown_report_builder.py:146-180`.

**Что**: два метода по 15 строк отличаются одним `in` / `not in _ACCESS_DENIED_CODES` и текстом
заголовка; строки, шапка и порядок колонок совпадают дословно.

**Почему**: это же и причина **Д-5** (секция «Битые HTTP» показывает `_нет_` при `broken_http=7`,
потому что все семь ушли во вторую секцию, а перекрёстной подписи нет).

**Предложение**: один приватный `_http_rows(ordered, *, denied: bool)` + два вызова `_block`;
в пустую секцию добавлять строку «см. секцию HTTP 401/403/429 — N ссылок».

### 🟠-5 · `ScanSummary` — `frozen=True`, но внутри изменяемый `dict`

**Где**: `core/mdscan/models/scan_summary.py:213-223` (`counters: dict[str, float]`).

**Почему**: правило 09 п.4 требует immutable для данных, пересекающих границы слоёв/потоков.
`frozen=True` защищает только ссылку: `summary.counters["broken_total"] = 0` пройдёт молча.
`ScanSummary` уходит наружу пакета (`Scanner.scan`) и в ДЗ, то есть в чужие руки.
Плюс `slots=True` + `dict` ломает хешируемость (её и нет, но VO обычно её ждут).

**Предложение**: `counters: Mapping[str, float]` и `MappingProxyType(...)` в
`StatisticsCollector.summary`; потребители уже делают `dict(summary.counters)`
(`homework/hw01_mdlinks/task.py:43`), так что ломать нечего.

### 🟠-6 · `github_org_source.py` — 318 строк, 1 класс + 10 свободных функций

**Где**: `core/mdscan/source/github_org_source.py` (класс `GitHubOrgSource` 163 строки,
модуль 318). Известный кандидат: в таске указано 271 — после H-13 стало 318.

**Почему**: правило 09 п.3 (файл >150, класс >120). В одном файле уживаются три ответственности:
(а) нормализация записей GitHub (`_from_gh`, `_from_api`, `_lower_headers`), (б) два способа
раскрытия организации (`_discover_gh`, `_discover_api`, `_check_status`, `_has_next`, `_payload`,
`_reset_hint`), (в) клонирование пулом и выбор URL по `auth`.

**Предложение**: `OrgRepoRecord` (frozen VO вместо `Mapping[str, Any]`, заодно уйдут
`record["ssh_url"]`-строки), `GhRepoLister` / `ApiRepoLister` (Strategy за общим `Protocol`),
`GitHubOrgSource` остаётся фильтры + клонирование + `cleanup`.

### 🟠-7 · `markdown_report_builder.py` — 267 строк, 1 класс + 9 свободных функций

**Где**: `core/mdscan/reporting/markdown_report_builder.py`.

**Почему**: правило 09 п.3. Внутри перемешаны «какие секции в отчёте» и «как рисуется
Markdown-таблица» (`_block`, `_escape`, `_code`, `_number`, `_yes_no`, `_MAX_CELL`).

**Предложение**: вынести отрисовку в `reporting/markdown_table.py` (Pure Fabrication:
`MarkdownTable.block(heading, header, rows)` + `Cell.code/escape/number`), builder оставить
списком секций. Заодно `_MAX_CELL` станет параметром, а не константой в середине модуля.

### 🟠-8 · `ResolvedPathCache` создаётся дважды — кэш H-05 работает вполсилы

**Где**: `core/mdscan/discovery/markdown_file_finder.py:59` (`self._paths = ResolvedPathCache()`)
и `core/mdscan/discovery/processed_registry.py:186` (свой второй экземпляр);
собираются оба в `core/mdscan/runtime/pipeline_runner.py:68-75`.

**Почему**: обход резолвит каталог, затем реестр резолвит **тот же** каталог заново — своим кэшем.
Цель H-05 («один вызов ОС на каталог») достигнута наполовину: на дереве из 96 каталогов это
192 обращения к ОС вместо 96. Плюс это нарушение правила 09 п.5 — зависимость создаётся внутри
класса, а не приходит из Composition Root.

**Предложение**: `PipelineRunner` создаёт один `ResolvedPathCache` и передаёт его и обходу,
и реестру (аргумент со значением по умолчанию — тесты не ломаются).

### 🟠-9 · `MarkdownFileFinder` сам создаёт `NestedRepoFinder`, и при `include_nested_repos: false` обходит всё дерево ради исключений

**Где**: `core/mdscan/discovery/markdown_file_finder.py:58` (`self._nested_finder = NestedRepoFinder()`),
`:135-141` (`_excluded_roots` → `self._nested_finder.find(root)`); второй экземпляр —
`core/mdscan/runtime/pipeline_runner.py:69`.

**Почему**: (а) конкретный класс внутри бизнес-логики вместо `Protocol` + DI (правило 09 п.5) —
подменить в тесте можно только monkeypatch'ем; (б) при `include_nested_repos: false` (умолчание)
на **каждый** репозиторий делается полный `os.scandir`-обход всего дерева только чтобы узнать,
какие поддеревья исключить. Это входит в «обход 0.12 с» замера H-04 и не разбиралось отдельно.

**Предложение**: принимать `NestedRepoSource(Protocol)` в конструкторе (значение по умолчанию —
текущий класс); результат обхода вложенных кэшировать на корень, чтобы `PipelineRunner` и
`MarkdownFileFinder` не искали их дважды.

### 🟠-10 · `mdscan.yaml` пишется в текущий каталог независимо от `-report.dir`

**Где**: `core/mdscan/__main__.py:43` (`YamlConfigLoader().load(Path.cwd() / CONFIG_FILE)`) →
`core/mdscan/config/yaml_config_loader.py:287-311` (`_create` при отсутствии файла).

**Почему**: любой прогон из корня репозитория оставляет там 11 КБ `mdscan.yaml` (зафиксировано
H-01 как D-7). Для боевого инструмента запись в рабочее дерево «за компанию» — неожиданность.

**Предложение**: создавать файл только по явному ключу (`-config.create:true`) либо в `report.dir`;
чтение — по-прежнему из `cwd`. Требует решения Alex: меняет поведение D19.1.

---

## 3. Находки — 🟡 низкий приоритет

### Дублирование

| # | Где | Что | Предложение |
|---|---|---|---|
| 🟡-1 | `parsing/markdown_it_link_extractor.py:72` · `parsing/markdown_it_heading_source.py:218` · `config/defaults.py:235` | `"gfm-like"` задан **трижды** (два `_DEFAULT_PRESET` + значение по умолчанию конфига) | убрать значения по умолчанию у классов (пресет всегда приходит из конфига) либо брать из `Defaults.value_at("parser.preset")` |
| 🟡-2 | `parsing/markdown_it_link_extractor.py:107-109` · `parsing/markdown_it_heading_source.py:244-247` | одинаковая заглушка «`linkify-it-py` нет → выключить опцию» в двух классах | приватный хелпер `_make_parser(preset)` в модуле `parsing` |
| 🟡-3 | `source/git_adapter.py:133` (`_CREDENTIALS`) · `source/local_path_source.py:342` (`_CREDENTIALS`) | одна и та же regex маскировки учётных данных в двух файлах, но функции разные (`_masked` → `//***@`, `_web_url` → `//`) | один `source/url_masking.py`; иначе однажды поправят одну и токен утечёт в отчёт |
| 🟡-4 | `discovery/nested_repo_finder.py:214` (`GIT_ENTRY`) · `cli/validation/rule_path_is_directory.py:21` (`_GIT_DIR`) · `cli/validation/rule_git_repository.py:112` (`_GIT_ENTRY`) | константа `".git"` объявлена трижды | одна константа (`enums`/`models` или `discovery.GIT_ENTRY`, который уже публичный) |
| 🟡-5 | `reporting/plain_console_renderer.py:157` (`_is_tty`) · `runtime/progress_factory.py:64` (`ProgressFactory._is_tty`) | две реализации «терминал ли поток», ловят разные исключения (`(AttributeError, ValueError)` vs `Exception`) | один хелпер; поведение при закрытом потоке должно быть одинаковым |
| 🟡-6 | `reporting/plain_console_renderer.py:100-101` · `reporting/rich_console_renderer.py:184-185` | `_SUMMARY_HEADER` / `_BROKEN_HEADER` скопированы в оба рендерера | перенести в `console_renderer.py` рядом с `summary_rows`/`broken_rows` (там же, где общий источник чисел) |
| 🟡-7 | `config/config_printer.py:246-252` (`_format`) · `config/yaml_config_loader.py:359-371` (`_scalar`) | обе превращают значение в текст: `bool → true/false`, список → строка | общий `ValueFormatter`; сейчас можно поправить печать и забыть про yaml |
| 🟡-8 | `cli/validation/rule_output_dir.py:174` · `cli/validation/rule_write_permission.py:223` | `FIELDS = ("logging.dir", "report.dir")` продублирован | одна константа в `validation_context.py` (там уже живут `TARGETS_RESOLVED`, `URL_MARKERS`) |
| 🟡-9 | `homework/hw01_mdlinks/solution.py:168-184` (`_found_links`) | ДЗ обходит дерево своим `root.rglob("*")` + `MD_SUFFIXES`, дублируя `MarkdownFileFinder` и `scan.md_extensions` | звать `MarkdownFileFinder`; либо оставить осознанно (это отдельный проход для метрик качества) и написать в докстринге, почему обход свой |
| 🟡-10 | `core/tokenstat/token_report_builder.py:142,182,193` | шапки Markdown-таблиц заданы тремя разными литералами с одним набором колонок | один список колонок → шапка и разделитель строятся из него |
| 🟡-11 | `tests/hw01/*` — 8 файлов | `ConfigDraft.from_defaults()` + `assign` + `from_draft` копируется в `_config` / `make_config` / `_source_config` (`test_checking.py:69`, `test_cli.py:41`, `test_config.py:48`, `test_orchestrator.py:60`, `test_progress.py:107`, `test_reporting.py:56`, `test_source.py:71`, `test_http_live.py:53`) | `tests/hw01/support/config_factory.py` с `config(**overrides)`; по спеке разработки §2.6 файлы принадлежали разным таскам — теперь таски закрыты, дубль можно снять |

### Мёртвый код

| # | Где | Что | Предложение |
|---|---|---|---|
| 🟡-12 | `core/mdscan/source/git_adapter.py:160-169` | `GitAdapter.submodules()` — **не вызывается ниоткуда** в продуктивном коде (единственное упоминание — заглушка `tests/hw01/test_source.py:88`). Подтверждён известный кандидат | удалить метод и заглушку либо задокументировать как задел (submodule'ы сейчас ловит `NestedRepoFinder` по файлу `.git`) |
| 🟡-13 | `core/tokenstat/token_aggregator.py:60,64` | `by_task()` и `by_model()` не вызываются в продуктиве (только в `test_tokenstat.py:277-279`); `TokenReportBuilder` их не использует | **не удалять**: H-12 обязан дать таблицу «по таскам H-XX». Правильная правка — добавить секцию «По таскам» в `TokenReportBuilder.build`, тогда `by_task()` перестанет быть мёртвым |
| 🟡-14 | `core/tokenstat/transcript_token_meter.py:117-130` (`start`), `:147-149` (`mark`), `:162-164` (`by_agent`) + `core/tokenstat/token_meter.py:210,214,227` | `start()` не зовётся (CLI использует `start_from`), `mark()` не зовётся никем → словарь `self._marks` всегда пуст и запасной путь в `_collect():190` недостижим; `TranscriptTokenMeter.by_agent()` — обёртка без потребителей | либо снять `mark`/`start` из `Protocol` и класса, либо задокументировать как API для будущего скила; сейчас `Protocol TokenMeter` вообще ни в одной аннотации не используется — контракт есть, зависимости от него нет |

### Нарушения правила 09

| # | Где | Что | Предложение |
|---|---|---|---|
| 🟡-15 | `core/mdscan/runtime/statistics_collector.py:126-133` | `if status is TIMEOUT / elif status is BROKEN / else: return` — ветвление по категории (правило 09 п.7), да ещё с `return` в `else` и «провалом» к `broken_total` ниже | таблица `{TIMEOUT: "timeout_http"}` + `_BROKEN_BY_KIND`; читается труднее, чем остальной файл, который как раз построен на таблицах |
| 🟡-16 | `core/mdscan/parsing/markdown_it_link_extractor.py:115-123` | `if name == "footnote" / elif "attrs" / elif "wikilinks" / else warning` — ветвление по имени плагина | таблица `{"footnote": md.use(footnote_plugin), ...}` из `Callable[[MarkdownIt], None]` — новый плагин добавляется строкой |
| 🟡-17 | `core/mdscan/config/cli_override_applier.py:344-354` | `_coerce` — цепочка `isinstance` по типу значения по умолчанию (буквально «`if/elif` по типу») | таблица `{bool: self._as_bool, int: ..., float: ..., list: ...}` по `type(default)` |
| 🟡-18 | `core/mdscan/errors.py` | 6 классов в одном файле — исключение п.2 разрешено только для `config/` и `enums/` | оставить (докстринг мотивирует: 43 строки, плоская иерархия, иначе циклические импорты) — но это **решение Alex**, а не автоматическое исключение |
| 🟡-19 | `homework/hw01_mdlinks/solution.py` | 151 строка при пороге ~150 | не трогать; иметь в виду при следующем добавлении метрики |

### Магические числа

| # | Где | Что | Предложение |
|---|---|---|---|
| 🟡-20 | 10 файлов `cli/validation/rule_*.py` | `exit_code=2` литералом в 12 местах, тогда как код 3 назван (`scan_orchestrator.INTERNAL_ERROR_CODE`) | `ARGUMENT_ERROR_CODE = 2` рядом с `ValidationResult` |
| 🟡-21 | `runtime/pipeline_runner.py:50` `JOIN_TIMEOUT_SEC=60.0` · `runtime/progress_reporter.py:18,20` `STOP_TIMEOUT_SEC=2.0`, `MIN_INTERVAL_SEC=0.01` · `source/source_factory.py:27` `_API_TIMEOUT_SEC=10.0` | таймауты названы, но зашиты в код, хотя рядом `http.timeout_ms` — поле конфига | либо в конфиг (`workers.join_timeout_sec`, `source.api_timeout_sec`), либо строкой в `Doc/Modules/mdscan/CLI.md`: «эти таймауты не настраиваются» |
| 🟡-22 | `reporting/markdown_report_builder.py:249` `_MAX_CELL = 200` | обрезка ячейки — поведение, видимое человеку в отчёте, но не настраиваемое | `report.max_cell` в конфиге либо аргумент конструктора builder'а |
| 🟡-23 | `source/github_org_source.py:37` `_MAX_PAGES = 1000` · `:91` `status == 200` | «страховка от бесконечного листания» и «200» литералом | `_MAX_PAGES` — оставить (комментарий есть); `200` → `http.HTTPStatus.OK` |

### Прочее

| # | Где | Что | Предложение |
|---|---|---|---|
| 🟡-24 | `runtime/pipeline_runner.py:53,126` | `DISCOVER_PREFIX = "discover"` + `ThreadPoolExecutor` → имена потоков `discover_0`, а правило 11 требует `discover-1`. **Подтверждён Д-11** | `DISCOVER_PREFIX = "discover-"` (даст `discover-0`) либо своими потоками; правило-формулировку «с 1» соблюсти `ThreadPoolExecutor` не даёт — тогда поправить правило |
| 🟡-25 | `runtime/markdown_worker.py:250` · `checking/http_checker.py:255` | `self._notifier.show(f"[parse] …")` / `f"[http] {code} {url}"` — f-строка собирается **на каждый файл и каждую ссылку**, даже когда `notifier` = `NullNotifier` (`progress.enabled: false`) | тот же приём, что H-06 применил к логам: `Notifier` получает шаблон и аргументы, либо `NullNotifier` определяется по `is`-проверке в конструкторе. Выигрыш того же порядка, что у H-06 (единицы процентов), правка бесплатная |
| 🟡-26 | `runtime/markdown_worker.py:256-263` | `logger.info("parsed …", extra=self._log_context(result))` — словарь `extra` строится всегда, даже при `logging.enabled: false` (`NullHandler`) | обернуть в `if logger.isEnabledFor(logging.INFO)` — единственное место конвейера «на файл», которое H-06 не закрыл |
| 🟡-27 | `discovery/markdown_file_finder.py:120-133` | `_scan_tree` делает `root.rglob(f"*{ext}")` **по расширению**: при умолчании `(".md", ".markdown")` дерево обходится **дважды** | один `rglob("*")` + проверка `_has_extension` (уже есть) |
| 🟡-28 | `config/defaults.py:470-476` | `Defaults._by_path` — `@property`, пересобирающая индекс всех полей при **каждом** `has()` / `value_at()`; `CliOverrideApplier` зовёт их по разу на каждый `-поле:значение`, `YamlConfigLoader._merge` — на каждое поле файла | `functools.cached_property` или построить один раз в `__init__` (класс и так неизменяем) |
| 🟡-29 | `runtime/pipeline_runner.py:164` | вложенный репозиторий создаётся как `RepoInfo(root=Path(root), is_nested=True)` — теряются `remote_url`, `web_url` и `scope` родителя | в отчёте у вложенных репозиториев колонка `web_url` всегда `—`; если это осознанно — строкой в докстринг, если нет — пробрасывать `web_url` родителя |
| 🟡-30 | `homework/hw01_mdlinks/solution.py:186-198` | `_workers_used` считает потоки, **разбирая текстовый лог** по индексу поля 2 — жёсткая связка с `LogFormat.PATTERN`. Поменяли формат лога → метрика ДЗ тихо станет 0 | отдавать имена потоков из `StatisticsCollector`/`ScanSummary` (у `MdFileResult` уже есть `thread_name`), лог не парсить |
| 🟡-31 | `homework/hw01_mdlinks/solution.py:163` + `task.py:44` | `run.fail_on_broken=False` → `exit_code` в `metrics.json` **всегда 0**. Подтверждён известный кандидат | либо считать `exit_code` «как было бы» (`broken_total > 0`), либо убрать поле из метрик — оно не несёт информации. Решение Alex |
| 🟡-32 | `checking/local_file_checker.py:409` | единственный оставшийся `WARNING` в чекере (ошибка разбора пути), хотя H-06 постановил «одна громкая строка на ссылку — у воркера» | оставить (случай редкий и это не «битая ссылка», а сбой разбора) — но зафиксировать, чтобы следующий агент не «чинил» |
| 🟡-33 | `tests/hw01/test_logging.py:166` | `test_stop_without_start_does_nothing` — тест **без единого `assert`**: доказывает только «не бросает» | добавить утверждение (`assert not logging.getLogger(LOGGER_NAME).handlers`), иначе тест не доказывает свойство (правило 04) |
| 🟡-34 | смешанный стиль импортов | 30 файлов используют относительные (`from ..config import`), 25 — абсолютные (`from core.mdscan.models import`); внутри одного пакета встречаются оба (`runtime/pipeline_runner.py` — относительные, `runtime/markdown_worker.py` — абсолютные) | выбрать один стиль (относительные внутри пакета — обычная практика) и добавить `ruff` правило `TID252`; сейчас это шум при чтении, не дефект |

---

## 4. Что искали и **не нашли** (проверено, чисто)

| Что | Результат |
|---|---|
| Голые `except:` | **нет ни одного** |
| `except Exception: pass` | **нет ни одного**; все 19 широких `except` логируют (`logger.exception` / `error` / `critical`) и имеют `# noqa: BLE001` с мотивировкой |
| f-строки в `logger.*` | **нет ни одной** (H-06 закрыл); `.format(` в логах — нет |
| `print()` вне слоя вывода | нет. `core/tokenstat/__main__.py:67,69` — точка входа (докстринг это фиксирует); `reporting/rich_console_renderer.py:44-51` — `rich.Console.print` в поток рендерера; `tests/hw01/support/bench_*.py` — инструменты замера с `main()`. **Оставляем осознанно** |
| Глобальное изменяемое состояние | **нет**: ни одного модульного `dict`/`list`/`set` на верхнем уровне |
| Синглтоны / `GetInstance` | **нет** |
| Коллизии имён атрибутов с `threading.Thread` (Python 3.14) | **нет**. Зарезервированы `_args, _context, _daemonic, _ident, _initialized, _invoke_excepthook, _kwargs, _name, _native_id, _os_thread_handle, _started, _stderr, _target`; у `BaseObserver` (`_queue`, `_sentinel`), `ProgressReporter` (`_source`, `_view`, `_clock`, `_lock`, `_messages`, `_stopped`, `_interval_sec`, `_message_ttl_sec`), `MarkdownWorker`, `CollectingObserver` пересечений нет |
| `Path.resolve()` в горячих путях после H-05 | под контролем: `ResolvedPathCache` (кэш по каталогу), `LocalFileChecker._base_of` (кэш по каталогу, под `Lock`). Вне кэша — только по разу на репозиторий/цель (`local_path_source`, `git_adapter`, правила V4/V5). Оставшаяся статья — 🟠-8 (два кэша) |
| Зависимости между пакетами | слои чистые: `enums` ← `models` ← `parsing`/`discovery`/`checking`/`reporting`/`source`; `runtime` — сборка. Единственная «обратная» стрелка — `checking → runtime.notifier` (`checker_factory.py:9`, `http_checker.py:13`), но это **`Protocol`**, а не реализация: соответствует §2.5 dev/test-спеки (владелец `Notifier` — `runtime`). Циклов нет (`mypy` прошёл). `discovery → source` **нет** — контракт `GitFileLister` живёт у потребителя, `GitAdapter` подходит структурно |
| Тесты-пустышки | `assert True` — нет · `xfail` — нет · `skip` без причины — **нет** (все `importorskip`/`skipif` с `reason`, `test_http_live.py:50` и `test_cli.py:280` с текстом). Единственная находка — 🟡-33 |

---

## 5. Файлы >150 строк (правило 09 п.3)

| файл | строк | класс, строк | вердикт |
|---|---|---|---|
| `core/mdscan/config/defaults.py` | 476 | `Defaults` 432 | **оставляем осознанно** — данные + исключение п.2 для `config/`; докстринг это фиксирует |
| `homework/hw01_mdlinks/support/fixture_tree_builder.py` | 440 | — | **оставляем осознанно** — генератор данных эталонного дерева |
| `core/mdscan/source/github_org_source.py` | 318 | `GitHubOrgSource` 163 | 🟠-6 — разбить |
| `core/mdscan/reporting/markdown_report_builder.py` | 267 | `MarkdownReportBuilder` 156 | 🟠-7 — вынести отрисовку таблиц |
| `core/mdscan/config/scan_config.py` | 238 | `ScanConfig` 100 | **оставляем осознанно** — 11 frozen-секций, исключение п.2 |
| `homework/hw01_mdlinks/support/expectations.py` | 201 | — | **оставляем осознанно** — эталонные ожидания (данные) |
| `core/mdscan/runtime/pipeline_runner.py` | 183 | `PipelineRunner` 128 | 🟡 — механика D1 (порядок сентинелов) неделима; при следующем расширении смотреть первым |
| `core/mdscan/runtime/scan_orchestrator.py` | 175 | `ScanOrchestrator` 116 | 🟡 — Composition Root, связывание по определению большое |
| `core/mdscan/parsing/markdown_it_link_extractor.py` | 166 | `MarkdownItLinkExtractor` 104 | 🟡 — вынести `_wikilink_rule` в `parsing/rules/wikilink_inline_rule.py` (это самостоятельная сущность markdown-it) |
| `homework/hw01_mdlinks/solution.py` | 151 | `Hw01Metrics` 110 | 🟡-19 — на 1 строку за порогом |

**Тестовые файлы >150 строк** (в бюджет правила 09 не входят, привожу справочно):
`test_source.py` 594 · `test_checking.py` 546 · `test_cli.py` 494 · `test_parsing.py` 456 ·
`test_pipeline.py` 432 · `test_progress.py` 400 · `test_reporting.py` 378 ·
`test_orchestrator.py` 363 · `test_config.py` 363 · `test_discovery.py` 355 ·
`test_fixture_tree.py` 303 · `test_tokenstat.py` 290 · `test_models.py` 281 ·
`support/bench_load.py` 221 · `test_logging.py` 215 · `support/bench_http.py` 186 ·
`support/bench_scan.py` 177 · `support/http_server.py` 175.

---

## 6. Сводка дефектов волн 1–3 (без повторного открытия)

| # | Откуда | Дефект | Состояние на 2026-08-17 (проверено по коду) |
|---|---|---|---|
| Д-1 | H-01/H-02 | `data:`-URI → LOCAL → ложный BROKEN, строка 1.8 МБ | ✅ **исправлено**: `parsing/link_classifier.py:319` `OtherSchemeRule` перед `LocalPathRule`; `markdown_report_builder.py:249` `_MAX_CELL = 200` |
| Д-2 | H-01 | клоны организации последовательно | ✅ **исправлено (H-13)**: `github_org_source.py:211-236` — `ThreadPoolExecutor(clone_workers)` + `as_completed`, число потоков из `workers.discover` (`source_factory.py:323`) |
| Д-3 | H-01 | битая ссылка = два `WARNING` (чекер + воркер) | ✅ **исправлено (H-06)**: чекеры пишут `DEBUG` (`local_file_checker.py:416`, `anchor_checker.py:54`, `http_checker._log_outcome`), единственный `WARNING` — `markdown_worker._log_link:287` |
| Д-4 | H-01/H-02 | `broken_total` включает `TIMEOUT` | ⚖️ **решение Alex** (по определению `MdFileResult.broken_count`). ⚠️ но: 🔴-1 показывает, что консоль считает «битых» **иначе** — расхождение экрана и отчёта надо закрыть независимо от решения по семантике |
| Д-5 | H-02 | секция «Битые HTTP» пуста при `broken_http=7` | ❌ **открыт**, причина — 🟠-4 (два почти одинаковых метода, нет перекрёстной подписи). Косметика для H-12 |
| Д-6 | H-01/H-03 | попадание в кэш HTTP не отличимо в логе | ✅ **исправлено (H-06)**: `http_checker.py:270` — префикс `"http cache"` против `"http"` |
| Д-7 | H-02 | `std::string` / `af::array` из автодоков → битые локальные | ❌ **открыт**, ограничение `LocalPathRule` (тотальное правило-«дно», признака «это не путь» нет). **Решение Alex**: варианты — (а) не считать битым путь без разделителя и без расширения из `md_extensions`, (б) правило `CodeLikeRule` перед `LocalPathRule` (`::`, `<`, `>`, `(`), (в) оставить и задокументировать |
| Д-8 | H-02 | `include_nested_repos:true` подхватывает `.claude/worktrees/*` | ❌ **открыт**. Причина: `discovery/nested_repo_finder.py:250-271` ходит по ФС и `.gitignore` родителя не знает. **Решение Alex**: фильтровать найденные корни через `git check-ignore` родителя (одна пачка, не на каждый корень) |
| Д-9 | H-03/H-07 | `http.timeout_ms` не покрывает DNS (`getaddrinfo` 10–12 с) и не общий бюджет запроса | ❌ **открыт по природе `urllib`** (`http_checker._request:299-320` передаёт `timeout` только сокету). Кандидат: `socket.setdefaulttimeout` в Composition Root или резолв в отдельном потоке — **решение Alex**; иначе документировать (H-12) |
| Д-10 | H-01 | `duration_sec` не включает отрисовку консоли | ⚖️ **ожидаемо** (D6: фазы 2–3 вне замера). Место фиксации — `scan_orchestrator.py:90` (`summary` до `_publish`). Отметить в H-12 |
| Д-11 | H-01 | имя потока `discover_0` вместо `discover-1` | ❌ **открыт** → 🟡-24 |
| H-01 D-7 | H-01 | `mdscan.yaml` пишется в текущий каталог | ❌ **открыт** → 🟠-10 |
| H-01 D-9 | H-01 | в спеке этапа §1.2 «1 DNS», фактически ошибка TLS-сертификата | ❌ **открыт** — правка текста спеки, не кода |
| H-03 §6.4 | H-03 | попадание в кэш неотличимо в логе | ✅ то же, что Д-6 — исправлено |
| H-07 §8.1 | H-07 | 90 % вызовов `logging.debug` — чужие (`markdown_it`) | ⚖️ **решение Alex**: `logging.getLogger("markdown_it").disabled = True` в Composition Root. Дешево, но меняет чужой логгер |
| H-07 §8.2 | H-07 | `speedup` в метриках ДЗ = «один прогон против одного» | ⚖️ **решение Alex** (меняет поведение ДЗ). Место — `homework/hw01_mdlinks/solution.py:131-143` |
| H-07 §8.3 | H-07 | цель «блочный разбор ≤ 30 % от полного» не выполнена (49 %) | ⚖️ оценка в спеке была оптимистичной; цель по времени слоя «проверка» закрыта |
| H-07 §8.4 | H-07 | планка `speedup ≥ 0.95` привязана к устаревшему знаменателю | ⚖️ **решение Alex**: переформулировать как «накладные 10 потоков ≤ 0.05 с на 500 файлов» |
| H-09 З-1 | H-09 | очереди без `maxsize`, ≈4.6 КиБ/файл → 0.5 ГБ на 100 тыс. файлов | ⚖️ ограничение архитектуры (D1/D3), документировать в H-12; обратное давление — решение Alex |
| H-09 З-2 | H-09 | размер отчёта линеен, ≈158 байт/файл → 15 МиБ на 100 тыс. | ❌ **открыт**, кандидат в H-11: предел строк в таблице битых + «показано 500 из N». Место — `markdown_report_builder._block:260`. **Решение Alex** (меняет полноту отчёта) |
| H-09 З-3…З-5 | H-09 | цена `DEBUG` (×2 время), рост каталога `out/`, цена `tracemalloc` | ⚖️ не дефекты, материал для раздела «Производительность» (H-12) |

> **Про «Д-14…Д-17»**: таких номеров в `MemoryBank/` нет — отчёта H-05 как отдельного файла тоже нет
> (H-05 сдан правками кода, его результаты вошли в `hw01_h07_after_2026-08-17.md`). Находки H-07
> пронумерованы в его §8 как 1–4 — они в таблице выше строками `H-07 §8.1…§8.4`. Расхождение
> нумерации в промпте таска — не потерянные дефекты.

---

## 7. Итог

| Приоритет | Сколько |
|---|---|
| 🔴 | **1** |
| 🟠 | **10** |
| 🟡 | **34** |
| «оставляем осознанно» | 8 (см. §4 и §5) |

**Ничего не правил** — правки утверждает Alex.

### Что рекомендую сделать в H-12 (документация, без правки логики)

- Д-4 / 🔴-1 — зафиксировать, каким числом называется «битых» на экране и в отчёте.
- Д-9, Д-10, H-09 З-1/З-3 — в раздел «Производительность» и «границы применимости».
- 🟡-21 — строка «эти таймауты не настраиваются» в `Doc/Modules/mdscan/CLI.md`.
- H-07 §8.4 — переформулировать критерий `speedup` в спеке этапа.

### Что рекомендую как отдельный таск после приёмки (правка кода)

1. **🔴-1** — единственный источник чисел для консоли. Дешево (10 строк), закрывает и Д-4-путаницу.
2. **🟠-1, 🟠-2, 🟠-3** — три дубля «одного смысла в двух местах». Каждый ≤10 строк, все три — прямые
   нарушения правила 07, ради которого это правило и заведено.
3. **🟠-8** — один `ResolvedPathCache` на прогон: доводит H-05 до заявленного эффекта, замеряется
   `bench_scan.py --layers` (слой «обход»).
4. **🟠-4 + Д-5** — склейка двух HTTP-секций и перекрёстная подпись.
5. **🟡-25, 🟡-26, 🟡-27, 🟡-28** — «бесплатные» проценты того же класса, что H-06.
6. **🟠-6, 🟠-7** — разбиение двух больших файлов; делать **после** пунктов 1–5, иначе правки
   поедут по переезжающим строкам.
7. **🟠-10, Д-7, Д-8, H-09 З-2** — меняют наблюдаемое поведение → **сначала решение Alex**, потом код.

### Требуют решения Alex (поведение, не код)

Д-4 (семантика `broken_total`) · Д-7 (`std::string` как локальная ссылка) ·
Д-8 (nested + `.gitignore` родителя) · Д-9 (таймаут DNS) · 🟠-10 (`mdscan.yaml` в `cwd`) ·
H-09 З-2 (предел строк в отчёте) · H-07 §8.1 (глушить логгер `markdown_it`) ·
H-07 §8.2 (методика `speedup` в метриках ДЗ) · 🟡-31 (`exit_code` в `metrics.json`) ·
🟡-18 (`errors.py` как исключение из «класс = файл») · 🟡-14 (судьба `TokenMeter.start`/`mark`).

---

*Черновик 2026-08-17, таск H-11. Код не менялся: `git status` по `core/`, `homework/`, `tests/` чист.*
