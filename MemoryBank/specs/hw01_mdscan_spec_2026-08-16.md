# Спека 2/2 — ТЗ: hw01 «Markdown / Git Scanner» (нарезка тасков)

> **Тип**: чистое техническое задание. Без рассуждений — только контракты, шаги и критерии приёмки.
> Обоснования решений → спека 1/2: `hw01_mdscan_reasoning_2026-08-16.md`.
>
> - **ДЗ**: `hw01`, пакет ДЗ — `homework/hw01_mdlinks/`, код — `core/mdscan/`
> - **Дата**: 2026-08-16 · **Статус**: ⛔ **ЗАМОРОЖЕНА** — написана раньше времени, спека 1/2
>   ещё не прочитана Alex. Не использовать, пока не согласована спека 1/2 и Alex не снимет заморозку.
> - **Запуск после готовности**: `python run_hw.py hw01` и `python -m core.mdscan <path> [log] [result]`

---

## 0. Правила, действующие на КАЖДЫЙ таск (не нарушать)

> Эти правила повторяются в каждом таске. При старте любой сессии по hw01 — прочитать этот раздел.

### 0.1 Стиль

1. **Только ООП.** Свободная функция допустима лишь как приватный хелпер в модуле своего класса.
2. **Один класс = один файл.** Исключения: конфиг-модули (`config/`) и перечисления (`enums/`).
3. Класс > ~120 строк или файл > ~150 строк → разбить.
4. Все данные, пересекающие границу потока, — `@dataclass(frozen=True, slots=True)`.
5. Зависимости объявляются как `typing.Protocol`; конкретика связывается только в Composition Root
   (`homework/hw01_mdlinks/task.py` и `core/mdscan/__main__.py`).
6. Глобального состояния нет. Единственный Singleton — `EventBus`, и он скрыт за `Protocol`.
7. Type hints везде. Докстринги по-русски, с описанием контракта.
8. `print()` — только в `reporting/`. В остальном коде — логгер.
9. Python ≥ 3.11, `pathlib`, никаких абсолютных Windows-путей в коде и доках.
10. Не мутировать входные аргументы.

### 0.2 SOLID (обязательно к применению)

| Принцип | Требование к каждому таску |
|---|---|
| SRP | один класс — одна причина изменения; поиск ≠ разбор ≠ проверка ≠ вывод |
| OCP | новая категория ссылки / новая проверка / новый рендер = **новый класс**, старые не трогаем |
| LSP | реализации одного `Protocol` взаимозаменяемы, наружу исключений не бросают |
| ISP | `Publisher` (для worker) и `Consumer` (для Observer) — раздельные интерфейсы |
| DIP | верхние уровни зависят от `Protocol`, не от классов |

### 0.3 GRASP

Information Expert · Creator · Controller (`ScanOrchestrator`) · Low Coupling · High Cohesion ·
Polymorphism (вместо `if/elif` по типу) · Pure Fabrication (`EventBus`, `StatisticsCollector`,
`MarkdownReportBuilder`) · Indirection (шина) · Protected Variations (интерфейсы вокруг парсера,
чекера, рендера).

### 0.4 GoF — обязательная карта паттернов

| Паттерн | Где |
|---|---|
| Singleton | `EventBus` |
| Observer | `MarkdownObserver` |
| Strategy | `LinkExtractor`, `LinkChecker`, `ConsoleRenderer` |
| Chain of Responsibility | `ValidationChain` (CLI), `LinkClassifier` (категории ссылок) |
| Template Method | `HomeworkTask.run` (уже в репо), `BaseLinkChecker.check` |
| Facade | `ScanOrchestrator`, `core.mdscan.__init__` |
| Builder | `MarkdownReportBuilder` |
| Factory Method | `CheckerFactory`, `RendererFactory` |
| Adapter | `GitCommandAdapter` (обёртка `subprocess`) |
| Null Object | `NullChecker` |
| Command | `MarkdownTask` (единица работы для пула) |
| Value Object | `MdLink`, `MdFileResult`, `RepoInfo`, `LinkStatus`, `ScanConfig` |

### 0.5 Тестирование (жёсткий gate-протокол)

- Тесты — **pytest** (правило 04 репозитория, обновлено 2026-08-16). `TestRunner` — не использовать.
- **Следующий таск не начинается, пока тесты текущего не зелёные.** Прогон: `pytest tests/hw01 -q`.
- Тесты не ходят в реальную сеть: только `http.server` на `127.0.0.1`.
- Тесты не зависят от внешних репозиториев: git-деревья создаются в `tmp_path` через `git init`.
- Нет `git` в PATH → `pytest.skip`, не падение.
- Каждый таск завершается фиксацией: код + тесты + строка в `TASK_hw01_mdlinks.md`.

### 0.6 Бюджет

Продуктивный код ≈ 1000–1200 строк (см. таблицу раздела 8 спеки 1/2). Тесты в бюджет не входят.
Превышение бюджета модуля → сначала искать лишнюю абстракцию.

---

## 1. Контракт CLI

### 1.1 Позиционные аргументы (флагов нет)

| N | Форма вызова | Поведение |
|---|---|---|
| 0 | `python -m core.mdscan` | печать справки по ключам + значения по умолчанию, exit `0` |
| 1 | `… <path>` | скан `<path>`; лог → `out/hw01/md_scan.log`; отчёт → `out/hw01/md_scan_report.md` |
| 2 | `… <path> <log_path>` | лог по указанному пути, отчёт по умолчанию |
| 3 | `… <path> <log_path> <result_path>` | лог и отчёт по указанным путям |
| >3 | — | ошибка + справка, exit `2` |

`-h` / `--help` / `-?` единственным аргументом → та же справка, exit `0`.

### 1.2 Цепочка валидации (Chain of Responsibility, класс на правило)

| # | Класс | Проверка | Exit |
|---|---|---|---|
| V1 | `ArgCountRule` | аргументов ≤ 3 | 2 |
| V2 | `PathExistsRule` | `path` существует | 2 |
| V3 | `PathIsDirectoryRule` | `path` — каталог | 2 |
| V4 | `PathReadableRule` | есть право на чтение | 2 |
| V5 | `GitRepositoryRule` | `path` внутри Git | 0 (warning, не ошибка) |
| V6 | `OutputIsFileRule` | `log_path`/`result_path` — не существующий каталог | 2 |
| V7 | `ParentDirWritableRule` | родительский каталог существует/создаётся | 2 |
| V8 | `WritePermissionRule` | пробная запись успешна | 2 |
| V9 | `DistinctOutputsRule` | `log_path ≠ result_path` | 2 |
| V10 | `PathNormalizationRule` | `~`, относительные, пробелы, кириллица, UNC | — |

Нормализация: если передан сам каталог `.git` — подняться к родителю (не ошибка).

### 1.3 Коды возврата

`0` — успех, битых ссылок нет · `1` — успех, есть битые ссылки/файлы с ошибками ·
`2` — ошибка аргументов · `3` — внутренняя ошибка (git/запись отчёта).

---

## 2. Конфигурация (`core/mdscan/config/`)

`ScanConfig` — frozen VO. Поля и значения по умолчанию:

| Поле | Тип | По умолчанию |
|---|---|---|
| `root_path` | `Path` | из CLI |
| `log_path` | `Path` | `out/hw01/md_scan.log` |
| `report_path` | `Path` | `out/hw01/md_scan_report.md` |
| `max_workers` | `int` | `5` |
| `md_extensions` | `tuple[str, ...]` | `(".md", ".markdown")` |
| `include_nested_repos` | `bool` | `True` |
| `check_local` | `bool` | `True` |
| `check_http` | `bool` | `True` |
| `http_timeout_sec` | `float` | `5.0` |
| `http_max_parallel` | `int` | `5` |
| `require_git` | `bool` | `False` |
| `fail_on_broken` | `bool` | `True` (влияет на exit `1`) |

---

## 3. Публичные контракты (Protocol)

```python
class Publisher(Protocol):
    def publish(self, item: object) -> None: ...

class Consumer(Protocol):
    def get(self) -> object: ...
    def task_done(self) -> None: ...
    def join(self) -> None: ...

class LinkExtractor(Protocol):
    def extract(self, text: str) -> tuple[MdLink, ...]: ...

class LinkRule(Protocol):
    def matches(self, target: str) -> bool: ...
    @property
    def kind(self) -> LinkKind: ...

class LinkChecker(Protocol):
    def check(self, link: MdLink, base_dir: Path) -> LinkStatus: ...

class ConsoleRenderer(Protocol):
    def render(self, summary: ScanSummary) -> None: ...

class ValidationRule(Protocol):
    def validate(self, args: CliArguments) -> ValidationResult: ...
```

Модели (frozen VO): `MdLink(target, kind, line)` · `MdFileResult(repo_root, md_file, links,
statuses, error, seconds, thread_name)` · `RepoInfo(root, is_nested, remote_url)` ·
`LinkStatus(link, ok, detail, http_code)` · `ScanSummary(...агрегаты для отчёта...)`.

`LinkKind(Enum)`: `LOCAL · ANCHOR · GITHUB · URL · MAILTO · TEL · UNKNOWN`.

---

## 4. Инварианты (проверяются тестами)

1. Максимум 5 worker-потоков одновременно.
2. Результат публикует **сам worker**, не главный поток.
3. `END_OF_STREAM` — уникальный объект, публикуется **строго после** завершения всех futures, ровно один раз.
4. `events_received == tasks_submitted + 1` (с сентинелом).
5. На каждый `get()` — `task_done()` в `finally`; `bus.join()` не виснет.
6. MD-файл nested-репозитория попадает в задачи **ровно один раз**.
7. Ошибка одного файла публикуется как событие и не останавливает остальные.
8. Отчёт строится только после `bus.join()` и `observer.join()`.
9. Два прогона на одном дереве дают одинаковый отчёт (кроме времени).
10. Ссылки внутри fenced/inline code не извлекаются.

---

## 5. Таски (T00…T11) — порядок обязателен

Формат: **что сделать → файлы → DoD (тесты)**.

### T00 · Скелет пакета
Создать `core/mdscan/` с подпакетами (`config`, `enums`, `models`, `cli`, `discovery`, `parsing`,
`checking`, `runtime`, `log_setup`, `reporting`), `LinkKind`, `ScanConfig`, `defaults`.
**DoD**: `import core.mdscan` работает; дефолты `ScanConfig` соответствуют разделу 2; `pytest` зелёный.

### T01 · CLI: разбор 0–3 аргументов + цепочка валидации
`cli/cli_arguments.py`, `cli/argument_parser.py`, `cli/usage_printer.py`,
`cli/validation/{rule.py, chain.py, rule_*.py}` (V1…V10).
**DoD**: тесты на 0/1/2/3/4 аргумента; на каждое правило V1–V10; на `-h`; на коды возврата `0`/`2`;
на путь с пробелами и кириллицей; на переданный `.git` (нормализация к родителю).

### T02 · Модели-VO
`models/{md_link, md_file_result, repo_info, link_status, scan_summary}.py`.
**DoD**: неизменяемость (`FrozenInstanceError`), равенство/хеш, `slots`, конверсия в строки отчёта.

### T03 · Git-адаптер и корень репозитория
`discovery/git_command_adapter.py`, `discovery/git_root_resolver.py`.
**DoD**: каталог вне git; обычный репозиторий; `git` отсутствует в PATH → понятная ошибка/skip;
таймаут `subprocess`.

### T04 · Вложенные репозитории
`discovery/nested_repo_finder.py`, `discovery/repository_collector.py`.
**DoD**: nested clone (`.git`-каталог); submodule (`.git`-файл); worktree; подтверждение через
повторный `rev-parse`; `RepoInfo.remote_url` заполняется, если `origin` есть.

### T05 · Поиск MD-файлов с дедупликацией
`discovery/markdown_file_finder.py`.
**DoD**: `.md` и `.markdown`; файл nested-репо ровно один раз (инвариант 6); пропуск `.git/`;
пустое дерево → пустой список без ошибки.

### T06 · Чтение и разбор Markdown
`parsing/markdown_reader.py`, `parsing/code_block_masker.py`, `parsing/regex_link_extractor.py`,
`parsing/rules/rule_*.py` (anchor, mailto, tel, github, http, local) + `parsing/link_classifier.py`.
**DoD**: golden-набор (раздел 6); `[x](docs/a.md)`, `![x](img/a.png)`, `[id]: docs/a.md`, `<path with
spaces.md>`, `#anchor`, `file:///…`, `mailto:`, `tel:`; UTF-8 и UTF-8-SIG; ссылка внутри ``` code ```
не извлекается; ошибка чтения → `MdFileResult.error`.

### T07 · Шина, worker, observer
`runtime/{event_bus_protocol, event_bus, end_of_stream, markdown_task, markdown_worker,
markdown_observer, statistics_collector}.py`.
**DoD**: инварианты 1–5, 7; тест с искусственно замедленным worker'ом; тест изоляции Singleton
между тестами (фикстура сброса); N producer-потоков → N событий.

### T08 · Логирование
`log_setup/{logging_setup, log_format}.py` — `QueueHandler` + `QueueListener`.
**DoD**: 5 потоков × N записей → ровно N строк в файле; формат
`время | уровень | поток | repo | file | сообщение`; listener останавливается корректно.

### T09 · Проверка ссылок
`checking/{link_checker, local_file_checker, http_checker, null_checker, checker_factory}.py`.
**DoD**: локальные — существующая/битая цель, относительный путь резолвится **от файла-владельца**,
якорь в существующем файле; HTTP — против локального `http.server`: `200`, `301`, `404`, `500`,
таймаут; `check_http=False` → `NullChecker`, ни одного сетевого вызова.

### T10 · Отчёты
`reporting/{markdown_report_builder, console_renderer, rich_console_renderer,
plain_console_renderer, renderer_factory}.py`.
**DoD**: отчёт содержит секции — запуск/длительность, входной путь, список репозиториев (+`origin`),
статистика по типам ссылок, таблица файлов, битые локальные, битые HTTP, файлы с ошибками;
рендер без установленного `rich` работает (эмуляция отсутствия модуля в тесте).

### T11 · Оркестратор, ДЗ, метрики
`runtime/scan_orchestrator.py`, `core/mdscan/__main__.py`, `homework/hw01_mdlinks/task.py`
(`Hw01MdLinks(HomeworkTask)`, `hw_id="hw01"`), регистрация в `homework/registry.py`,
заполнение `homework/hw01_mdlinks/README.md`.
**DoD**: интеграционный тест на временном дереве (main + nested + submodule, 5–10 MD, битые и живые
ссылки); `python run_hw.py hw01` отрабатывает; `HomeworkReport.metrics` содержит метрики раздела 6;
повторный прогон детерминирован (инвариант 9); порядок завершения соблюдён (инвариант 8).

---

## 6. Метрики (обязательный результат ДЗ)

`Hw01MdLinks.solve()` возвращает `dict[str, float]`.

### 6.1 Операционные
`repos_total`, `repos_nested`, `md_files_total`, `files_ok`, `files_failed`, `links_total`,
`links_local`, `links_github`, `links_url`, `links_anchor`, `links_mailto`, `links_tel`,
`broken_local`, `broken_http`, `broken_ratio`, `error_rate`, `duration_sec`,
`throughput_files_per_sec`.

### 6.2 Качество извлечения (golden-набор)
Данные: `homework/hw01_mdlinks/fixtures/golden/*.md` (8–12 файлов, < 100 КБ суммарно, идут в git)
и `expected.json` с ручной разметкой `(file, target, kind)`.

Алгоритм: `U = expected ∪ extracted`; для каждого элемента `y_true = 1 если ∈ expected`,
`y_pred = 1 если ∈ extracted`; метрики считаются **существующими** функциями `core.metrics`:

- `extract_precision` = `core.metrics.precision(y_true, y_pred)`
- `extract_recall` = `core.metrics.recall(y_true, y_pred)`
- `extract_f1` = `core.metrics.f1_score(y_true, y_pred)`
- `classify_accuracy` = `core.metrics.accuracy(kinds_true, kinds_pred)` на верно извлечённых
- разбор ошибок — `core.metrics.confusion_matrix` (в Markdown-отчёт, не в метрики)

**Порог приёмки**: `extract_f1 ≥ 0.95`, `classify_accuracy ≥ 0.98`. Ниже — сдаём как есть
с честной причиной в README ДЗ (правило 08).

### 6.3 Параллельность
`duration_serial_sec` (прогон с `max_workers=1`), `speedup = duration_serial_sec / duration_sec`,
`parallel_efficiency = speedup / workers`, `workers_used` (уникальные `thread_name`).
Замер на синтетическом дереве ~200 MD-файлов в `tmp_path`. Ожидание: `speedup` ≈ 1.5–3×.

---

## 7. Definition of Done (всё ДЗ)

- [ ] T00…T11 закрыты, тесты каждого шага зелёные (`pytest tests/hw01 -q`).
- [ ] `python run_hw.py hw01` отрабатывает от начала до конца.
- [ ] `python -m core.mdscan` с 0/1/2/3 аргументами ведёт себя по разделу 1.
- [ ] Инварианты 1–10 покрыты тестами.
- [ ] `homework/hw01_mdlinks/README.md`: условие, что сделано, запуск, **реальные числа**, выводы.
- [ ] Метрики разделов 6.1–6.3 попали в `HomeworkReport.metrics`.
- [ ] Отчёт и лог пишутся в `out/hw01/` (в git не идут), golden-фикстуры — идут.
- [ ] `ruff check` и `mypy core/mdscan` чистые.
- [ ] Бюджет кода не превышен более чем на 20 % без согласования.
- [ ] `MemoryBank`: `TASK_hw01_mdlinks.md` закрыт, `MASTER_INDEX.md` и changelog обновлены.

---

*Спека 2/2. Основание решений — `hw01_mdscan_reasoning_2026-08-16.md`.*
