# Техническое задание: анализ Git-репозиториев и Markdown-ссылок

## 1. Цель

Нужно реализовать Python-программу, которая получает входной каталог и:

1. Определяет, принадлежит ли каталог Git-репозиторию.
2. Находит корень главного Git-репозитория.
3. Проверяет, есть ли внутри него независимые вложенные Git-репозитории и/или submodule/worktree (`.git` может быть как каталогом, так и файлом).
4. Если репозиторий один — анализирует его.
5. Если репозиториев несколько — формирует список репозиториев и обрабатывает каждый по тем же правилам, последовательно обходя список.
6. Находит все `*.md` и `*.markdown` во всех выбранных репозиториях.
7. Параллельно, максимум пятью потоками, читает и разбирает Markdown-файлы.
8. Каждый worker-поток самостоятельно отправляет результат разбора в общую шину событий.
9. Observer получает все события, логирует их, сохраняет данные для последующего анализа и итогового отчёта.
10. После завершения обработки всех MD-файлов всех репозиториев главная программа отправляет специальное событие конца потока. Observer получает его и понимает, что новых результатов больше не будет.
11. После завершения печатает красивую цветную сводку в консоль и создаёт Markdown-отчёт с логами/статистикой.

---

## 2. Главный выбор архитектуры

### Рекомендуемый вариант

Использовать **потоки**, не `asyncio`:

- `ThreadPoolExecutor(max_workers=5)` для обработки Markdown-файлов;
- обычную `queue.Queue` для передачи результатов;
- один отдельный поток `Observer` (consumer);
- `QueueHandler` + `QueueListener` для безопасного многопоточного логирования;
- `rich` для цветной консольной сводки;
- итоговый Markdown-отчёт.

### Почему не asyncio как основной вариант

Основные операции здесь синхронные:

- обход каталогов (`Path.rglob()`);
- чтение файлов (`Path.read_text()`);
- запуск Git-команд (`subprocess.run()`);
- разбор Markdown регулярными выражениями или синхронным парсером.

В `asyncio` их пришлось бы оборачивать в `asyncio.to_thread()`, поэтому код стал бы сложнее, а заметной выгоды для текущей задачи не было бы.

`asyncio` можно добавить позднее, если появятся массовые асинхронные HTTP-проверки ссылок, GitHub API, `aiohttp`, асинхронная БД или веб-интерфейс.

---

## 3. Ключевая корректировка: кто пишет результаты

### Неправильный подход

Worker возвращает результат в главный поток, а главный поток потом пишет его в общее хранилище.

### Требуемый подход

Каждый из пяти worker-потоков должен:

1. взять один MD-файл;
2. прочитать файл;
3. извлечь ссылки;
4. создать объект результата;
5. **самостоятельно вызвать `event_bus.publish(result)`**.

То есть запись в шину событий происходит непосредственно в worker-потоке.

Схема:

```text
ThreadPoolExecutor(max_workers=5)
  worker-1: parse A.md -> EventBus.publish(result_A)
  worker-2: parse B.md -> EventBus.publish(result_B)
  worker-3: parse C.md -> EventBus.publish(result_C)
  worker-4: parse D.md -> EventBus.publish(result_D)
  worker-5: parse E.md -> EventBus.publish(result_E)

EventBus (Singleton)
  -> Queue[MdFileResult | END_OF_STREAM]
  -> Observer thread
```

---

## 4. Singleton и потокобезопасная очередь

Нужен Singleton `EventBus`/`ResultBus`.

Singleton хранит **одну общую потокобезопасную очередь** `queue.Queue`.

Важное уточнение:

- Singleton нужен только как единая точка доступа к общей шине в рамках одного процесса.
- Потокобезопасность хранения сообщений обеспечивает не Singleton, а `queue.Queue`.
- `queue.Queue` безопасна для нескольких producer-потоков и consumer-потоков.
- Для `queue.put()` / `queue.get()` отдельный `Lock` не нужен.
- `Lock` может быть нужен только при ленивом создании экземпляра Singleton.

### Сентинел завершения

Не использовать `0`, `None` или пустую строку как команду завершения. Это может пересечься с настоящими данными.

Нужно создать уникальный объект:

```python
END_OF_STREAM = object()
```

Главный поток отправляет его **ровно один раз и только после того, как завершились все worker-задачи**.

```python
bus.publish(END_OF_STREAM)
```

Observer, увидев `END_OF_STREAM`, должен завершить цикл обработки.

---

## 5. Модель событий

Пример минимальных моделей:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MdLink:
    target: str
    kind: str  # local | github | url | anchor | mailto | tel


@dataclass(frozen=True, slots=True)
class MdFileResult:
    repo_root: Path
    md_file: Path
    links: tuple[MdLink, ...]
    error: str | None = None
```

### Что должен содержать результат одного файла

- полный путь или путь относительно корня репозитория;
- репозиторий-владелец;
- извлечённые ссылки;
- тип каждой ссылки;
- ошибка чтения или разбора, если возникла;
- при желании: число ссылок, размер файла, время обработки, имя потока.

---

## 6. EventBus: контракт

Нужен объект примерно с таким интерфейсом:

```python
class EventBus:
    def publish(self, item: MdFileResult | object) -> None:
        ...

    def get(self) -> MdFileResult | object:
        ...

    def task_done(self) -> None:
        ...

    def join(self) -> None:
        ...
```

### Требования

- `publish()` вызывают worker-потоки.
- `get()` вызывает Observer.
- После каждого успешного `get()` Observer обязан вызвать `task_done()` в блоке `finally`.
- Главный поток вызывает `bus.join()`, чтобы дождаться, пока Observer обработает все события, уже положенные в очередь.

Пример каркаса:

```python
import threading
from queue import Queue


class EventBus:
    _instance = None
    _creation_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._creation_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._queue = Queue()
                    cls._instance = obj
        return cls._instance

    def publish(self, item):
        self._queue.put(item)

    def get(self):
        return self._queue.get()

    def task_done(self):
        self._queue.task_done()

    def join(self):
        self._queue.join()
```

---

## 7. Observer pattern

Нужен отдельный класс Observer, предпочтительно наследник `threading.Thread`.

### Ответственность Observer

Observer является consumer-ом событий из EventBus. Он должен:

- получать `MdFileResult`;
- последовательно сохранять результаты в `self.results`;
- логировать успешную обработку и ошибки;
- собирать статистику;
- при необходимости передавать результаты в БД, граф зависимостей или другой аналитический слой;
- завершиться по `END_OF_STREAM`;
- после завершения предоставить итоговый список результатов.

Пример базовой логики:

```python
class MarkdownObserver(threading.Thread):
    def __init__(self, bus, logger):
        super().__init__(name="markdown-observer", daemon=False)
        self.bus = bus
        self.logger = logger
        self.results = []
        self.completed = threading.Event()

    def run(self):
        while True:
            item = self.bus.get()
            try:
                if item is END_OF_STREAM:
                    self.completed.set()
                    return

                self.results.append(item)
                self.handle_result(item)
            finally:
                self.bus.task_done()

    def handle_result(self, result):
        if result.error:
            self.logger.error("Ошибка: %s", result.error)
        else:
            self.logger.info(
                "Обработан файл %s, найдено ссылок: %d",
                result.md_file,
                len(result.links),
            )
```

### Несколько Observer-ов

Одна очередь не реализует broadcast: если несколько consumer-ов читают одну очередь, одно сообщение получит только один из них.

Если в будущем нужны независимые обработчики (`LoggerObserver`, `StatisticsObserver`, `ReportObserver`, `DatabaseObserver`), EventBus должен хранить отдельную очередь на каждого подписчика и при `publish()` копировать сообщение в каждую очередь. Для первой версии достаточно одного `MarkdownObserver`, внутри которого можно вызвать несколько обработчиков.

---

## 8. Worker: обработка одного Markdown-файла

Worker должен быть обычной функцией, запускаемой в `ThreadPoolExecutor`:

```python
def parse_md_file(repo_root: Path, md_file: Path, bus: EventBus) -> None:
    try:
        text = read_markdown(md_file)
        links = extract_links(text)

        result = MdFileResult(
            repo_root=repo_root,
            md_file=md_file,
            links=links,
        )
        bus.publish(result)

    except Exception as exc:
        bus.publish(
            MdFileResult(
                repo_root=repo_root,
                md_file=md_file,
                links=(),
                error=f"{type(exc).__name__}: {exc}",
            )
        )
```

Важно: worker не должен скрывать исключение без результата. Ошибка также должна быть опубликована как событие, чтобы Observer включил её в лог и отчёт.

---

## 9. Очерёдность завершения

Это критически важная часть.

Правильный порядок:

```python
# 1. Observer уже запущен.
observer.start()

# 2. Workers разбирают MD-файлы и сами публикуют результаты в EventBus.
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(parse_md_file, repo, md_file, bus)
        for repo, md_file in tasks
    ]

    for future in as_completed(futures):
        future.result()  # не терять неожиданные ошибки

# 3. Теперь точно нет worker-ов, которые могут добавить новое событие.
bus.publish(END_OF_STREAM)

# 4. Дождаться обработки Observer-ом всех MdFileResult и END_OF_STREAM.
bus.join()
observer.join()

# 5. Только теперь формировать итоговый Markdown-отчёт.
```

Нельзя отправлять `END_OF_STREAM` раньше завершения worker-ов: Observer может выйти, а поздний worker положит результат в очередь, который уже никто не прочитает.

---

## 10. Git: один репозиторий или набор репозиториев

### Основной репозиторий

Нужно получить Git-root входного каталога:

```bash
git -C <path> rev-parse --show-toplevel
```

Если команда неуспешна — каталог не принадлежит Git-репозиторию. Поведение нужно определить через параметр/политику:

- либо завершить работу с понятной ошибкой;
- либо разрешить сканировать обычный каталог без Git.

### Вложенные репозитории

Внутри главного репозитория искать маркеры `.git`:

- `.git` может быть каталогом: самостоятельный clone;
- `.git` может быть файлом: типично для submodule или worktree.

Для каждой найденной директории-кандидата нужно снова вызвать `git -C <candidate> rev-parse --show-toplevel`, чтобы подтвердить, что это отдельный Git-root.

### Требуемое поведение

- Если найден только главный репозиторий: список репозиториев содержит один элемент.
- Если найдены вложенные: список содержит главный и все вложенные независимые репозитории.
- Для каждого репозитория применяется один и тот же pipeline поиска MD-файлов и постановки задач.

### Важный нюанс

При сборе MD-файлов главного репозитория надо исключить поддеревья вложенных репозиториев, иначе один и тот же MD-файл будет обработан дважды: один раз как часть главного дерева, второй — как часть nested repo.

Правило:

```text
главный repo: сканировать все MD, кроме каталогов nested repo;
каждый nested repo: сканировать собственное дерево MD.
```

---

## 11. Извлечение Markdown-ссылок

Нужно искать как минимум:

- inline links: `[text](target)`;
- изображения: `![alt](target)`;
- reference definitions: `[id]: target`;
- ссылки в `<target>`;
- локальные относительные пути: `docs/a.md`, `../assets/image.png`;
- anchors: `#install`;
- URL: `https://example.org`;
- GitHub: `https://github.com/org/repo`, `raw.githubusercontent.com`, `gist.github.com`;
- `mailto:` и `tel:`.

### Классификация

Минимальные категории:

```text
local
anchor
github
url
mailto
tel
```

### Ограничение regex

Регулярные выражения подходят для практической первой версии, но не покрывают весь Markdown:

- многострочные ссылки;
- сложные title;
- ссылки в HTML;
- inline/reference links `[text][id]` с разыменованием;
- fenced code blocks;
- особенности MkDocs, Obsidian, GitHub Flavored Markdown.

Если нужна строгая поддержка Markdown — заменить regex на полноценный AST-парсер. Не следует поддерживать самодельный regex-парсер, если нужна полная корректность спецификации.

### Готовая библиотека

`linkcheckmd` полезна как валидатор ссылок (например, в CI), но её публичный API ориентирован на проверку и текстовый вывод, а не на возврат удобного структурированного `list` событий. Поэтому:

- для извлечения структурированных данных использовать собственный extractor/парсер;
- `linkcheckmd` можно отдельно запускать для проверки битых ссылок;
- не наследоваться от функции `check_links()`: от функции наследоваться нельзя;
- не перехватывать stdout библиотеки как основной API: это хрупко.

---

## 12. Логирование

Требуется многопоточное логирование.

Рекомендуемая схема:

```text
workers + observer
   -> logging.QueueHandler
   -> Queue[LogRecord]
   -> logging.QueueListener
   -> FileHandler (logs/md_scan.log)
```

Это позволяет не блокировать worker-потоки файловой записью логов и не смешивать записи.

Формат лога должен включать:

```text
время | уровень | имя потока | repo | md file | сообщение
```

Пример:

```text
2026-08-16 01:40:22 | INFO  | md-worker_2 | repo=project | file=docs/install.md | links=5
2026-08-16 01:40:23 | ERROR | markdown-observer | repo=project | file=docs/bad.md | UnicodeDecodeError: ...
```

Минимальные уровни:

- `INFO`: файл обработан, число ссылок;
- `WARNING`: странная/неподдерживаемая ссылка;
- `ERROR`: ошибка чтения, разбора, Git-операции;
- `DEBUG`: подробности для диагностики.

---

## 13. Консольный интерфейс

Нужен красивый цветной вывод. Рекомендуется библиотека `rich`.

Показать:

- число найденных репозиториев;
- число MD-файлов;
- число успешно обработанных файлов;
- число файлов с ошибкой;
- число ссылок по категориям;
- число GitHub-ссылок;
- время выполнения;
- путь к логу;
- путь к Markdown-отчёту.

Пример итоговой таблицы:

```text
Markdown repository scan
┌────────────────────────┬────────┐
│ Repositories           │ 3      │
│ Processed MD files     │ 124    │
│ Files with errors      │ 1      │
│ Local links            │ 630    │
│ GitHub links           │ 89     │
│ External URLs          │ 47     │
│ Duration               │ 1.28 s │
└────────────────────────┴────────┘
```

Необязательно печатать каждую ссылку в консоль: это лучше оставить для `DEBUG`-логов или отдельного режима verbose.

---

## 14. Markdown-отчёт

После завершения Observer нужно создать один Markdown-файл, например:

```text
output/md_scan_report.md
```

Отчёт должен содержать:

1. Дату/время запуска и длительность.
2. Входной путь.
3. Список обнаруженных репозиториев.
4. Список remote URL (`origin`), если доступен.
5. Число обработанных MD-файлов по репозиторию.
6. Число ошибок.
7. Таблицу количества ссылок по типам.
8. Таблицу обработанных MD-файлов:
   - repository;
   - relative MD path;
   - число ссылок;
   - статус;
   - текст ошибки, если есть.
9. Отдельные разделы, по возможности:
   - GitHub-ссылки;
   - внешние URL;
   - отсутствующие локальные цели (если реализована проверка существования);
   - файлы с ошибками.

Пример начала отчёта:

```markdown
# Markdown Link Scan Report

- Started: 2026-08-16T01:40:00+03:00
- Repositories: 3
- Processed Markdown files: 124
- Failed files: 1

## Repositories

- `/work/main-project`
- `/work/main-project/vendor/lib-a`
- `/work/main-project/examples/demo`

## Link statistics

| Type | Count |
|---|---:|
| local | 630 |
| github | 89 |
| url | 47 |
| anchor | 55 |

## File results

| Repository | File | Links | Status |
|---|---|---:|---|
| main-project | `README.md` | 19 | OK |
| main-project | `docs/install.md` | 12 | OK |
| lib-a | `README.md` | 0 | ERROR: UnicodeDecodeError... |
```

---

## 15. Предлагаемая структура проекта

```text
md_repo_scanner/
├── main.py                 # CLI и orchestration
├── models.py               # MdLink, MdFileResult, RepoInfo, MdTask
├── git_discovery.py        # Git root, nested repo discovery, remote URL
├── markdown_parser.py      # read_markdown, extract_links, classify_link
├── event_bus.py            # Singleton EventBus
├── observer.py             # MarkdownObserver
├── workers.py              # parse_md_file
├── logging_setup.py        # QueueHandler/QueueListener
├── report.py               # Markdown report + Rich summary
├── config.py               # CLI/config defaults
└── tests/
    ├── test_git_discovery.py
    ├── test_markdown_parser.py
    ├── test_event_bus.py
    └── test_integration.py
```

---

## 16. CLI

Нужен простой CLI, например:

```bash
python -m md_repo_scanner /path/to/project \
  --workers 5 \
  --output-dir output \
  --include-nested-repos \
  --verbose
```

Полезные аргументы:

```text
path                    входная папка
--workers N             число worker-потоков, default=5
--output-dir DIR        каталог отчётов и логов
--include-nested-repos  искать и анализировать вложенные Git repositories
--no-git-required       разрешить входной каталог без Git
--check-local-files     проверять существование локальных целей
--verbose               подробный вывод
--fail-on-error         завершать процесс с ненулевым кодом при ошибках
```

---

## 17. Тесты, которые обязательно нужны

### Git discovery

- Каталог вне Git.
- Один репозиторий.
- Вложенный clone с `.git`-каталогом.
- Submodule с `.git`-файлом.
- Исключение nested repo из обхода main repo.

### Markdown parsing

- `[x](docs/a.md)`.
- `![x](img/a.png)`.
- `[x](https://github.com/org/repo)`.
- `[x](https://example.org/a)`.
- `[x](#anchor)`.
- `[id]: docs/a.md`.
- `<path with spaces.md>`.
- UTF-8 и UTF-8-SIG.
- Ошибка чтения файла.

### Concurrency/event bus

- Все результаты, опубликованные worker-ами, получены Observer-ом.
- `END_OF_STREAM` отправляется только после worker completion.
- `queue.join()` не зависает.
- На каждый `get()` есть `task_done()`.
- Ошибка одного файла не останавливает обработку остальных.

### Integration

- Временное дерево с главным и вложенным репозиторием.
- Несколько MD-файлов.
- Итоговый отчёт существует и содержит ожидаемые секции.
- Лог существует.

---

## 18. Приоритет реализации

### Этап 1: минимально работающий продукт

- Один Git-репозиторий.
- Поиск `*.md`.
- `ThreadPoolExecutor(max_workers=5)`.
- `EventBus` + `Queue` + один Observer.
- Извлечение inline URL/путей.
- Консольная сводка.

### Этап 2: полноценный аудит

- Вложенные репозитории/submodules.
- Логи через `QueueHandler`/`QueueListener`.
- Markdown-отчёт.
- Классификация ссылок.
- Проверка локальных путей.

### Этап 3: качество и расширяемость

- Полноценный Markdown AST parser.
- Проверка HTTP/GitHub URL.
- CI-интеграция с `linkcheckmd`.
- Несколько Observer-ов (fan-out/broadcast).
- JSON/CSV экспорт.
- Граф зависимостей MD-файлов.

---

## 19. Краткий итог для реализации

Нужно реализовать **потоковый producer-consumer pipeline**:

```text
Repository discovery
  -> create (repo_root, md_file) tasks
  -> ThreadPoolExecutor(5)
  -> each worker parses exactly one MD file
  -> each worker calls Singleton EventBus.publish(MdFileResult)
  -> one Observer consumes Queue events
  -> all workers complete
  -> main thread publishes END_OF_STREAM
  -> Observer finishes all queued data
  -> generate log, colored console summary, Markdown report
```

Основные инварианты:

1. Максимум пять MD worker-потоков.
2. Worker публикует результат сам, не через главный поток.
3. Queue находится в Singleton EventBus и является потокобезопасной.
4. Observer — единственный consumer первой версии.
5. END_OF_STREAM публикуется строго после завершения всех worker-ов.
6. Итоговый отчёт формируется только после `bus.join()` и `observer.join()`.
7. Вложенные Git-репозитории не должны давать двойного сканирования MD-файлов.
