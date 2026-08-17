"""Значения по умолчанию конфигурации сканера — **единственное** место, где они живут.

Модуль конфигурации: исключение из правила «один класс = один файл»
(`.claude/rules/09-oop-design.md` п. 2). Здесь три типа: описание поля, описание секции
и фасад `Defaults`, отдающий дерево значений, пути полей и описания.

Каждое поле несёт при себе:

* `value`       — значение по умолчанию (по его **типу** приводится `-поле:значение`);
* `description` — короткая строка для колонки «описание» в `ConfigPrinter` (D19.3);
* `comment`     — многострочный комментарий, попадающий в созданный `mdscan.yaml`
  (часть 2 спеки, раздел 2: файл должен быть самодокументированным).

Служебного поля `source.targets_resolved` здесь **нет** намеренно: его заполняет правило V5
цепочки валидации, в `mdscan.yaml` оно не выводится и через `-source.targets_resolved:`
не задаётся (будет `UnknownFieldError`).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Описание одного поля конфигурации: значение, описание, комментарий для yaml."""

    name: str
    value: Any
    description: str
    comment: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """Описание секции конфигурации (верхний уровень `mdscan.yaml`)."""

    name: str
    comment: tuple[str, ...]
    fields: tuple[FieldSpec, ...]


class Defaults:
    """Фасад над деревом значений по умолчанию (Information Expert)."""

    BANNER: tuple[str, ...] = (
        "============================================================================",
        " mdscan.yaml — конфигурация сканера Markdown-ссылок",
        " Приоритет значений:  defaults (код)  <  этот файл  <  командная строка",
        " Любое поле переопределяется ключом:  -путь.к.полю:значение",
        " Пример:  python -m core.mdscan yaml -workers.parse:8 -http.timeout_ms:5000",
        "============================================================================",
    )

    SECTIONS: tuple[SectionSpec, ...] = (
        SectionSpec(
            name="source",
            comment=(
                "ЧТО сканируем и откуда берём репозитории.",
                "Эти поля работают, когда цель = `yaml`",
                "(python -m core.mdscan yaml) или запуск через run_hw.py hw01.",
            ),
            fields=(
                FieldSpec(
                    "target",
                    "",
                    "цель сканирования (первый аргумент CLI)",
                    (
                        "ЦЕЛЬ. Пусто = цели нет.",
                        "Первый аргумент командной строки подставляется СЮДА.",
                        "Если адрес прописан здесь — запуск `... yaml` берёт его.",
                    ),
                ),
                FieldSpec(
                    "repositories",
                    [],
                    "список целей, когда их несколько",
                    (
                        "СПИСОК целей (когда их несколько).",
                        "Можно смешивать: локальные пути, репозитории, организации,",
                        "в том числе из РАЗНЫХ организаций.",
                        "Заполнены и target, и repositories → сканируем ВСЁ вместе,",
                        "дубли отсекает реестр.",
                    ),
                ),
                FieldSpec(
                    "kind",
                    "auto",
                    "как трактовать цель",
                    (
                        "как трактовать цель, если автоопределение ошиблось:",
                        "  auto        — определить самостоятельно (рекомендуется)",
                        "  local       — локальный каталог",
                        "  remote_repo — один удалённый репозиторий (клонируем)",
                        "  github_org  — организация целиком",
                    ),
                ),
                FieldSpec(
                    "discovery",
                    "auto",
                    "чем раскрываем организацию в список репозиториев",
                    (
                        "ЧЕМ раскрываем ОРГАНИЗАЦИЮ в список её репозиториев:",
                        "  auto  — сначала gh repo list, затем REST API по GITHUB_TOKEN",
                        "  gh    — только gh repo list",
                        "  api   — только REST API по GITHUB_TOKEN",
                        "Жёсткий режим = воспроизводимость: «не сработало» видно сразу,",
                        "а не превращается в тихий переход на другой путь.",
                    ),
                ),
                FieldSpec(
                    "auth",
                    "auto",
                    "протокол доступа к репозиториям",
                    (
                        "протокол доступа: auto | ssh | https | token.",
                        "свои приватные → ssh; чужие ПУБЛИЧНЫЕ → https (ключи не нужны);",
                        "CI без ключа → token (GITHUB_TOKEN из окружения).",
                    ),
                ),
                FieldSpec(
                    "visibility",
                    "all",
                    "какие репозитории брать",
                    ("какие репозитории брать: all | public | private",),
                ),
                FieldSpec(
                    "include_forks",
                    False,
                    "тащить ли форки",
                    ("true — тащить и форки (обычно это шум в отчёте)",),
                ),
                FieldSpec(
                    "include_archived",
                    False,
                    "тащить ли архивные репозитории",
                    ("true — тащить архивные репозитории",),
                ),
                FieldSpec(
                    "page_size",
                    100,
                    "размер страницы GitHub API",
                    ("размер страницы GitHub API; листаем до конца списка",),
                ),
                FieldSpec(
                    "clone_dir",
                    "out/hw01/_clones",
                    "куда клонируются удалённые репозитории",
                    ("куда клонируются удалённые репозитории (вне git проекта)",),
                ),
                FieldSpec(
                    "clone_depth",
                    1,
                    "глубина клона",
                    ("глубина клона; 1 = только последний коммит, быстро и мало места",),
                ),
                FieldSpec(
                    "keep_clones",
                    False,
                    "оставлять ли клоны после прогона",
                    ("false — клоны удаляются после прогона; true — оставить для отладки",),
                ),
            ),
        ),
        SectionSpec(
            name="scan",
            comment=("ЧТО ищем внутри репозитория",),
            fields=(
                FieldSpec(
                    "include_nested_repos",
                    False,
                    "обходить вложенные репозитории",
                    (
                        "false = ТОЛЬКО главный репозиторий (по умолчанию).",
                        "true  = плюс вложенные (submodule, worktree, клон внутри).",
                        "Каждый .md всё равно обрабатывается ровно один раз.",
                    ),
                ),
                FieldSpec(
                    "md_extensions",
                    [".md", ".markdown"],
                    "расширения файлов Markdown",
                    ("какие файлы считаем Markdown",),
                ),
                FieldSpec(
                    "respect_gitignore",
                    True,
                    "учитывать ли .gitignore",
                    (
                        "true = git ls-files --cached --others --exclude-standard",
                        "(tracked + новые файлы, минус игнорируемое: node_modules, build, .venv)",
                        "false или папка вне git = обычный rglob по md_extensions",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="workers",
            comment=(
                "ПАРАЛЛЕЛЬНОСТЬ. Два пула потоков (третье число — http.workers,",
                "это семафор внутри стадии 2, см. блок http).",
            ),
            fields=(
                FieldSpec(
                    "discover",
                    5,
                    "потоков на обход репозиториев",
                    (
                        "сколько РЕПОЗИТОРИЕВ обходится/клонируется одновременно.",
                        "Поднимать: много репозиториев в организации.",
                        "Снижать:   медленная сеть, лимиты GitHub.",
                    ),
                ),
                FieldSpec(
                    "parse",
                    5,
                    "потоков на разбор .md",
                    (
                        "сколько .md-ФАЙЛОВ разбирается одновременно.",
                        "Поднимать: тысячи файлов, быстрый диск.",
                        "Снижать:   слабый CPU.",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="parser",
            comment=("КАК разбираем Markdown (markdown-it-py)",),
            fields=(
                FieldSpec(
                    "preset",
                    "gfm-like",
                    "пресет markdown-it",
                    ("commonmark | gfm-like (GitHub-разметка: таблицы, автоссылки)",),
                ),
                FieldSpec(
                    "plugins",
                    ["footnote", "attrs", "wikilinks"],
                    "плагины mdit-py-plugins",
                    (
                        "footnote  — ссылки внутри сносок [^1]",
                        "attrs     — ссылки с атрибутами [текст](a){#id .class}",
                        "wikilinks — [[внутренние ссылки]] (Obsidian/вики); в mdit-py-plugins",
                        "            такого плагина нет — это встроенное правило экстрактора",
                        "linkify (голые URL) включается сам при наличии linkify-it-py",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="checks",
            comment=("ЧТО проверяем у найденных ссылок",),
            fields=(
                FieldSpec(
                    "local",
                    True,
                    "проверять локальные файлы",
                    ("существование локальных файлов, на которые ведут ссылки",),
                ),
                FieldSpec(
                    "anchors",
                    True,
                    "проверять якоря заголовков",
                    (
                        "существование якорей: `#раздел` — в своём файле,",
                        "`a.md#раздел` — в целевом; сверка по GitHub-slug заголовка",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="http",
            comment=("ПРОВЕРКА внешних ссылок",),
            fields=(
                FieldSpec(
                    "enabled",
                    True,
                    "проверять внешние ссылки",
                    ("false — внешние ссылки только считаем, но не проверяем",),
                ),
                FieldSpec(
                    "timeout_ms",
                    2000,
                    "таймаут HTTP-запроса, мс",
                    (
                        "сколько ждём ответ. Меньше — быстрее прогон, больше ложных",
                        "TIMEOUT; больше — дольше висим на мёртвых адресах.",
                    ),
                ),
                FieldSpec(
                    "workers",
                    5,
                    "семафор одновременных HTTP-запросов",
                    (
                        "СЕМАФОР: сколько HTTP-запросов идёт одновременно",
                        "(не отдельный конвейер — проверка выполняется внутри",
                        "parse-worker'а, см. C2, вариант A).",
                        "Снижать, если сайт отвечает 429 (слишком много запросов).",
                    ),
                ),
                FieldSpec(
                    "method",
                    "head_then_get",
                    "метод проверки",
                    ("сначала HEAD (дёшево), при 405/501 — повтор через GET",),
                ),
                FieldSpec(
                    "cache",
                    True,
                    "кэшировать результат по URL",
                    ("один и тот же URL за прогон проверяем один раз",),
                ),
                FieldSpec(
                    "user_agent",
                    "mdscan/0.1",
                    "заголовок User-Agent",
                    (
                        "многие сайты и GitHub отдают 403 на дефолтный",
                        "Python-urllib/3.x — без своего UA будут ложные BROKEN",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="progress",
            comment=("ВЫВОД ХОДА РАБОТЫ на экран (stderr), две зоны",),
            fields=(
                FieldSpec(
                    "enabled",
                    True,
                    "показывать прогресс",
                    ("false — ничего не показываем (например, в CI)",),
                ),
                FieldSpec(
                    "interval_sec",
                    1.0,
                    "период перерисовки статуса",
                    ("зона 1: как часто перерисовывается строка состояния",),
                ),
                FieldSpec(
                    "style",
                    "line",
                    "вид зоны 1",
                    ("line — одна строка | panel — рамка | off",),
                ),
                FieldSpec(
                    "message_lines",
                    1,
                    "строк-сообщений на экране",
                    ("зона 2: сколько строк-сообщений от модулей держим на экране",),
                ),
                FieldSpec(
                    "message_ttl_sec",
                    5.0,
                    "через сколько гаснет строка модуля",
                    ("через сколько секунд строка-сообщение гаснет сама",),
                ),
            ),
        ),
        SectionSpec(
            name="logging",
            comment=("ЛОГ в файл",),
            fields=(
                FieldSpec(
                    "enabled",
                    True,
                    "писать лог",
                    ("false — лог не пишем (по умолчанию включён)",),
                ),
                FieldSpec(
                    "level",
                    "INFO",
                    "уровень лога",
                    (
                        "DEBUG — каждая ссылка и каждый файл (много строк)",
                        "INFO  — файлы, репозитории, битые ссылки (по умолчанию)",
                        "WARNING — только проблемы",
                    ),
                ),
                FieldSpec(
                    "dir",
                    "out/hw01",
                    "каталог лога",
                    (
                        "КАТАЛОГ лога. Имя файла всегда формируется само:",
                        "<цель>_<ГГГГ-ММ-ДД>_<ЧЧ-ММ-СС>.log",
                    ),
                ),
            ),
        ),
        SectionSpec(
            name="report",
            comment=("ИТОГОВЫЙ Markdown-отчёт",),
            fields=(
                FieldSpec(
                    "dir",
                    "out/hw01",
                    "каталог отчёта",
                    ("КАТАЛОГ отчёта; имя файла — как у лога, с той же меткой времени",),
                ),
                FieldSpec(
                    "title",
                    "",
                    "заголовок отчёта",
                    ("заголовок отчёта; пусто → берётся из имени цели",),
                ),
                FieldSpec(
                    "console",
                    True,
                    "сводка в консоль",
                    ("false — не печатать итоговую таблицу в stdout (run_hw.py, CI)",),
                ),
            ),
        ),
        SectionSpec(
            name="run",
            comment=("ПОВЕДЕНИЕ ПРОГОНА",),
            fields=(
                FieldSpec(
                    "fail_on_broken",
                    True,
                    "код 1 при битых ссылках",
                    ("true — если нашли битые ссылки, код возврата 1 (удобно для CI)",),
                ),
            ),
        ),
    )

    @property
    def sections(self) -> tuple[SectionSpec, ...]:
        """Секции в порядке вывода в `mdscan.yaml` и в `ConfigPrinter`."""
        return self.SECTIONS

    @property
    def tree(self) -> dict[str, Any]:
        """Свежая (глубокая) копия дерева значений по умолчанию."""
        return {
            section.name: {field.name: copy.deepcopy(field.value) for field in section.fields}
            for section in self.SECTIONS
        }

    @property
    def paths(self) -> tuple[str, ...]:
        """Все известные пути полей вида `workers.parse` в порядке объявления."""
        return tuple(
            f"{section.name}.{field.name}" for section in self.SECTIONS for field in section.fields
        )

    @property
    def descriptions(self) -> dict[str, str]:
        """`путь поля → короткое описание` для колонки «описание» (D19.3)."""
        return {
            f"{section.name}.{field.name}": field.description
            for section in self.SECTIONS
            for field in section.fields
        }

    def has(self, path: str) -> bool:
        """Известен ли путь поля (`source.kind` — да, `source.targets_resolved` — нет)."""
        return path in self._by_path

    def value_at(self, path: str) -> Any:
        """Значение по умолчанию для пути; путь неизвестен → `KeyError`."""
        return copy.deepcopy(self._by_path[path].value)

    @property
    def _by_path(self) -> dict[str, FieldSpec]:
        """Индекс `путь → описание поля` (строится по требованию, спецификация неизменяема)."""
        return {
            f"{section.name}.{field.name}": field
            for section in self.SECTIONS
            for field in section.fields
        }
