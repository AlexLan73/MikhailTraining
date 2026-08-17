"""Тесты модуля проверки ссылок (T-07): локальные пути, якоря, HTTP.

Сеть — **только** `127.0.0.1` (локальный сервер из `support/http_server.py`),
синхронизация — `Event` и `join(timeout=…)`, `time.sleep` в тестах нет (§3.2).

`HeadingSource` здесь — заглушка: настоящую реализацию (`MarkdownItHeadingSource`)
даёт T-06, и модуль проверки о ней ничего не знает (§2.5, DIP).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.mdscan.checking.anchor_checker import AnchorChecker
from core.mdscan.checking.checker_factory import CheckerFactory
from core.mdscan.checking.http_checker import HttpChecker
from core.mdscan.checking.local_file_checker import LocalFileChecker
from core.mdscan.checking.null_checker import NullChecker
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.models.md_link import MdLink

from .support.http_server import LocalHttpServer

#: Запас времени на любой join в тестах — тест обязан падать, а не висеть.
_JOIN_TIMEOUT_SEC = 30.0


# --------------------------------------------------------------------------
# заглушки чужих контрактов и сборка конфигурации
# --------------------------------------------------------------------------


class _LineHeadings:
    """Заглушка `HeadingSource`: строки, начинающиеся с решёток (duck typing)."""

    def headings(self, text: str) -> tuple[str, ...]:
        found = [
            line.strip().lstrip("#").strip()
            for line in text.splitlines()
            if line.strip().startswith("#")
        ]
        return tuple(found)


class _RecordingNotifier:
    """Заглушка `Notifier`: запоминает строки зоны 2, чтобы их можно было проверить."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def show(self, text: str) -> None:
        self.messages.append(text)


def _config(**overrides: object) -> ScanConfig:
    """Конфигурация из defaults + переопределения (`http__timeout_ms=300` → `http.timeout_ms`)."""
    draft = ConfigDraft.from_defaults()
    for name, value in overrides.items():
        draft.assign(name.replace("__", "."), value, SOURCE_CMDLINE)
    return ScanConfig.from_draft(draft)


def _factory(**overrides: object) -> tuple[CheckerFactory, _RecordingNotifier]:
    """Фабрика чекеров и её нотификатор (в тестах нужны оба)."""
    notifier = _RecordingNotifier()
    return CheckerFactory(_config(**overrides), _LineHeadings(), notifier), notifier


def _link(target: str, kind: LinkKind = LinkKind.LOCAL) -> MdLink:
    """Ссылка в состоянии «извлечена и классифицирована», статус ещё не проверен."""
    return MdLink(target=target, origin=LinkOrigin.INLINE, line=1, kind=kind)


# --------------------------------------------------------------------------
# фикстуры
# --------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Мини-дерево: корневой README, каталог docs с заголовками, вложенный файл."""
    (tmp_path / "README.md").write_text("# Корень\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text(
        "# Заголовок файла\n\n## Как запустить\n\nтекст\n\n## Как запустить\n\n## Раздел\n",
        encoding="utf-8",
    )
    (docs / "index.md").write_text("# Индекс\n", encoding="utf-8")
    (docs / "путь с пробелами.md").write_text("# Пробелы\n", encoding="utf-8")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "deep.md").write_text("# Глубоко\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def http_server() -> Iterator[LocalHttpServer]:
    """Локальный сервер на `127.0.0.1`; гасится всегда, включая упавший тест."""
    server = LocalHttpServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


# --------------------------------------------------------------------------
# 1. локальные ссылки
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("a.md", CheckStatus.OK, id="сосед-есть"),
        pytest.param("../README.md", CheckStatus.OK, id="на-уровень-вверх"),
        pytest.param("путь с пробелами.md", CheckStatus.OK, id="пробелы-в-имени"),
        pytest.param("%D0%BF%D1%83%D1%82%D1%8C%20%D1%81%20%D0%BF%D1%80%D0%BE%D0%B1%D0%B5%D0%BB%D0%B0%D0%BC%D0%B8.md", CheckStatus.OK, id="percent-encoded"),
        pytest.param("нет-такого.md", CheckStatus.BROKEN, id="файла-нет"),
        pytest.param("../нет/совсем.md", CheckStatus.BROKEN, id="каталога-нет"),
    ],
)
def test_local_target_existence_defines_status(tree: Path, target: str, expected: CheckStatus) -> None:
    """Существование цели относительно файла-владельца определяет статус."""
    factory, _ = _factory()
    link = _link(target)
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert link.status is expected


def test_broken_local_link_explains_reason(tree: Path) -> None:
    """У битой локальной ссылки заполнен `detail` — иначе отчёт бесполезен."""
    factory, _ = _factory()
    link = _link("нет-такого.md")
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert "нет-такого.md" in link.detail


# --------------------------------------------------------------------------
# 2. относительный путь из вложенного файла
# --------------------------------------------------------------------------


def test_parent_relative_path_resolved_from_owner_file(tree: Path) -> None:
    """`../../README.md` из `a/b/deep.md` ведёт в корень дерева (требование T10)."""
    factory, _ = _factory()
    link = _link("../../README.md")
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "a" / "b" / "deep.md")
    assert link.status is CheckStatus.OK


def test_same_target_from_other_file_is_broken(tree: Path) -> None:
    """Тот же `../../README.md` из `docs/index.md` уходит выше дерева — битая."""
    factory, _ = _factory()
    link = _link("../../README.md")
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert link.status is CheckStatus.BROKEN


def test_file_uri_is_skipped(tree: Path) -> None:
    """`file://…` — адрес чужой машины: `SKIPPED`, а не ложная битая ссылка."""
    factory, _ = _factory()
    link = _link("file:///tmp/report.html")
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert link.status is CheckStatus.SKIPPED
    assert "file://" in link.detail


# --------------------------------------------------------------------------
# 3. якоря и GitHub-slug
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("#заголовок-файла", CheckStatus.OK, id="первый-заголовок"),
        pytest.param("#как-запустить", CheckStatus.OK, id="slug-из-двух-слов"),
        pytest.param("#как-запустить-1", CheckStatus.OK, id="повтор-получает-суффикс"),
        pytest.param("#%D1%80%D0%B0%D0%B7%D0%B4%D0%B5%D0%BB", CheckStatus.OK, id="percent-encoded"),
        pytest.param("#нет-такого", CheckStatus.BROKEN, id="якоря-нет"),
        pytest.param("#как-запустить-2", CheckStatus.BROKEN, id="лишний-суффикс"),
    ],
)
def test_anchor_matches_github_slug(tree: Path, target: str, expected: CheckStatus) -> None:
    """`## Как запустить` ↔ `#как-запустить`, повтор заголовка → `-1` (инвариант 24)."""
    factory, _ = _factory()
    link = _link(target, LinkKind.ANCHOR)
    factory.for_kind(LinkKind.ANCHOR).check(link, tree / "docs" / "a.md")
    assert link.status is expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("a.md#раздел", CheckStatus.OK, id="файл-и-якорь-есть"),
        pytest.param("a.md#нет-такого", CheckStatus.BROKEN, id="файл-есть-якоря-нет"),
        pytest.param("нет.md#раздел", CheckStatus.BROKEN, id="файла-нет"),
    ],
)
def test_local_link_with_anchor_checks_target_file(
    tree: Path, target: str, expected: CheckStatus
) -> None:
    """`a.md#раздел` проверяет и файл, и заголовок **в целевом** файле."""
    factory, _ = _factory()
    link = _link(target)
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert link.status is expected


def test_headings_read_once_per_file(tree: Path) -> None:
    """Кэш заголовков: два якоря в один файл — одно чтение (общий экземпляр на прогон)."""
    reads: list[str] = []

    class _CountingHeadings:
        def headings(self, text: str) -> tuple[str, ...]:
            reads.append(text)
            return _LineHeadings().headings(text)

    checker = AnchorChecker(_CountingHeadings())
    for target in ("#раздел", "#как-запустить"):
        checker.check(_link(target, LinkKind.ANCHOR), tree / "docs" / "a.md")
    assert len(reads) == 1


def test_anchors_disabled_leaves_anchor_part_unchecked(tree: Path) -> None:
    """`checks.anchors: false` → ANCHOR получает `NullChecker`, якорь `a.md#x` не проверяется."""
    factory, _ = _factory(checks__anchors=False)
    anchor_link = _link("#нет-такого", LinkKind.ANCHOR)
    factory.for_kind(LinkKind.ANCHOR).check(anchor_link, tree / "docs" / "a.md")
    local_link = _link("a.md#нет-такого")
    factory.for_kind(LinkKind.LOCAL).check(local_link, tree / "docs" / "index.md")
    assert anchor_link.status is CheckStatus.SKIPPED
    assert local_link.status is CheckStatus.OK


def test_local_checks_disabled_skips_local_links(tree: Path) -> None:
    """`checks.local: false` → LOCAL получает `NullChecker` (диск не трогаем)."""
    factory, _ = _factory(checks__local=False)
    link = _link("нет-такого.md")
    factory.for_kind(LinkKind.LOCAL).check(link, tree / "docs" / "index.md")
    assert link.status is CheckStatus.SKIPPED


def test_unreadable_target_becomes_broken_not_exception(tree: Path) -> None:
    """Ошибка чтения заголовков не бросается наружу, а превращается в `BROKEN` (D2.1)."""
    checker = AnchorChecker(_LineHeadings())
    link = _link("#раздел", LinkKind.ANCHOR)
    checker.check(link, tree / "docs" / "нет-файла.md")
    assert link.status is CheckStatus.BROKEN
    assert link.detail


# --------------------------------------------------------------------------
# 4–6, 9. HTTP на локальном сервере
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        pytest.param("/ok", CheckStatus.OK, 200, id="200-ok"),
        pytest.param("/moved", CheckStatus.OK, 200, id="301-редирект-до-200"),
        pytest.param("/missing", CheckStatus.BROKEN, 404, id="404-битая"),
        pytest.param("/boom", CheckStatus.BROKEN, 500, id="500-битая"),
    ],
)
def test_http_codes_map_to_statuses(
    http_server: LocalHttpServer, tmp_path: Path, path: str, status: CheckStatus, code: int
) -> None:
    """2xx/3xx → `OK`, 4xx/5xx → `BROKEN`; код ответа попадает в `http_code`."""
    factory, notifier = _factory()
    link = _link(http_server.url(path), LinkKind.URL)
    factory.for_kind(LinkKind.URL).check(link, tmp_path / "doc.md")
    assert link.status is status
    assert link.http_code == code
    assert notifier.messages == [f"[http] {code} {link.target}"]


def test_hanging_endpoint_gives_timeout(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """Молчащий адрес → `TIMEOUT` за время порядка `http.timeout_ms`, тест не виснет."""
    factory, _ = _factory(http__timeout_ms=300)
    link = _link(http_server.url("/hang"), LinkKind.URL)
    started = time.monotonic()
    factory.for_kind(LinkKind.URL).check(link, tmp_path / "doc.md")
    elapsed = time.monotonic() - started
    assert link.status is CheckStatus.TIMEOUT
    assert link.http_code == 0
    assert elapsed < 10.0


def test_head_not_allowed_falls_back_to_get(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """`method: head_then_get` — на 405 повторяем тот же адрес через GET."""
    http_server.head_405 = True
    factory, _ = _factory()
    link = _link(http_server.url("/ok"), LinkKind.URL)
    factory.for_kind(LinkKind.URL).check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.OK
    assert http_server.hits("/ok") == 2


def test_same_url_requested_once(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """Кэш по URL: один и тот же адрес за прогон уходит в сеть один раз."""
    factory, notifier = _factory()
    checker = factory.for_kind(LinkKind.URL)
    links = [_link(http_server.url("/ok"), LinkKind.URL) for _ in range(2)]
    for link in links:
        checker.check(link, tmp_path / "doc.md")
    assert http_server.hits("/ok") == 1
    assert [link.status for link in links] == [CheckStatus.OK, CheckStatus.OK]
    assert len(notifier.messages) == 2


def test_cache_disabled_repeats_request(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """`http.cache: false` — кэша нет, каждый вызов идёт в сеть."""
    factory, _ = _factory(http__cache=False)
    checker = factory.for_kind(LinkKind.URL)
    for _ in range(2):
        checker.check(_link(http_server.url("/ok"), LinkKind.URL), tmp_path / "doc.md")
    assert http_server.hits("/ok") == 2


def test_user_agent_is_sent(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """Сервер требует свой `User-Agent`: с `http.user_agent` — 200, с чужим — 403."""
    http_server.expected_user_agent = "mdscan/0.1"
    expected_factory, _ = _factory(http__user_agent="mdscan/0.1")
    foreign_factory, _ = _factory(http__user_agent="Python-urllib/3.x")
    good = _link(http_server.url("/ok"), LinkKind.URL)
    bad = _link(http_server.url("/ok"), LinkKind.URL)
    expected_factory.for_kind(LinkKind.URL).check(good, tmp_path / "doc.md")
    foreign_factory.for_kind(LinkKind.URL).check(bad, tmp_path / "doc.md")
    assert good.status is CheckStatus.OK
    assert bad.status is CheckStatus.BROKEN
    assert bad.http_code == 403


def _standalone_http_checker(timeout_ms: int = 500) -> HttpChecker:
    """`HttpChecker` без фабрики — для случаев, когда сервер не нужен вовсе."""
    return HttpChecker(
        timeout_ms=timeout_ms,
        workers=1,
        user_agent="mdscan/0.1",
        method="head_then_get",
        cache_enabled=True,
        notifier=_RecordingNotifier(),
    )


def test_closed_port_does_not_raise(tmp_path: Path) -> None:
    """Закрытый порт `127.0.0.1:1` → статус ссылки, а не исключение наружу (D2.1).

    Конкретный исход зависит от ОС (отказ в соединении или молчание файрвола),
    поэтому проверяем главное: наружу ничего не летит, ссылка помечена не-`OK`
    и с пояснением.
    """
    link = _link("http://127.0.0.1:1/ok", LinkKind.URL)
    _standalone_http_checker().check(link, tmp_path / "doc.md")
    assert link.status in (CheckStatus.BROKEN, CheckStatus.TIMEOUT)
    assert link.detail


def test_malformed_url_is_broken(tmp_path: Path) -> None:
    """Мусорный адрес не роняет прогон: `BROKEN` с пояснением, сети нет."""
    link = _link("http://", LinkKind.URL)
    _standalone_http_checker().check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.BROKEN
    assert link.detail


# --------------------------------------------------------------------------
# 7. семафор
# --------------------------------------------------------------------------


def test_semaphore_limits_concurrent_requests(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """`http.workers: 2` → в пике на сервере не больше 2 запросов (инвариант 22)."""
    factory, _ = _factory(http__workers=2, http__timeout_ms=20000)
    checker = factory.for_kind(LinkKind.URL)
    links = [_link(http_server.url(f"/slow?n={index}"), LinkKind.URL) for index in range(10)]
    threads = [
        threading.Thread(target=checker.check, args=(link, tmp_path / "doc.md"), name=f"probe-{n}")
        for n, link in enumerate(links)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT_SEC)
    assert not [thread.name for thread in threads if thread.is_alive()]
    assert http_server.hits("/slow") == 10
    assert http_server.peak_concurrency == 2
    assert all(link.status is CheckStatus.OK for link in links)


# --------------------------------------------------------------------------
# 8, 10. фабрика чекеров
# --------------------------------------------------------------------------


def test_http_disabled_makes_no_requests(http_server: LocalHttpServer, tmp_path: Path) -> None:
    """`http.enabled: false` → URL/GITHUB получают `NullChecker`, сети нет вовсе."""
    factory, notifier = _factory(http__enabled=False)
    for kind in (LinkKind.URL, LinkKind.GITHUB):
        link = _link(http_server.url("/ok"), kind)
        factory.for_kind(kind).check(link, tmp_path / "doc.md")
        assert link.status is CheckStatus.SKIPPED
    assert http_server.hits("/ok") == 0
    assert notifier.messages == []


def test_for_kind_returns_shared_instances() -> None:
    """Экземпляры общие: иначе у каждого worker'а свой семафор и свой кэш."""
    factory, _ = _factory()
    assert factory.for_kind(LinkKind.URL) is factory.for_kind(LinkKind.URL)
    assert factory.for_kind(LinkKind.URL) is factory.for_kind(LinkKind.GITHUB)
    assert factory.for_kind(LinkKind.LOCAL) is factory.for_kind(LinkKind.LOCAL)
    assert factory.for_kind(LinkKind.ANCHOR) is factory.for_kind(LinkKind.ANCHOR)


@pytest.mark.parametrize(
    "kind",
    [LinkKind.MAILTO, LinkKind.TEL, LinkKind.WIKILINK, LinkKind.FOOTNOTE_URL, LinkKind.UNKNOWN],
)
def test_unchecked_kinds_get_null_checker(tmp_path: Path, kind: LinkKind) -> None:
    """`mailto` / `tel` / `wikilink` / `footnote_url` / `unknown` — только считаем."""
    factory, _ = _factory()
    checker = factory.for_kind(kind)
    link = _link("mailto:alex@example.org", kind)
    checker.check(link, tmp_path / "doc.md")
    assert isinstance(checker, NullChecker)
    assert link.status is CheckStatus.SKIPPED


def test_factory_builds_expected_implementations() -> None:
    """Таблица выдачи соответствует спеке: LOCAL → `LocalFileChecker`, URL → `HttpChecker`."""
    factory, _ = _factory()
    assert isinstance(factory.for_kind(LinkKind.LOCAL), LocalFileChecker)
    assert isinstance(factory.for_kind(LinkKind.ANCHOR), AnchorChecker)
    assert isinstance(factory.for_kind(LinkKind.URL), HttpChecker)
