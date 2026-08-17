"""Тесты T-11 — прогресс: зона 1 по таймеру, зона 2 с TTL, фабрика (rich | plain | None).

Время управляемое: `FakeClock` + прямой вызов `ProgressReporter.tick()`,
поэтому ни один тест не ждёт реальных секунд (спека разработки §3.3).
Сеть и файлы не используются вовсе.
"""

from __future__ import annotations

import io
import sys
import threading
from collections.abc import Sequence

import pytest

from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.models.progress_snapshot import ProgressSnapshot
from core.mdscan.runtime.plain_progress_view import CLEAR_BELOW, CLEAR_LINE, PlainProgressView
from core.mdscan.runtime.progress_factory import ProgressFactory
from core.mdscan.runtime.progress_reporter import ProgressReporter

# --------------------------------------------------------------------------------------
# заглушки чужих контрактов (duck typing, без наследования — спека разработки §3.3)
# --------------------------------------------------------------------------------------


class FakeClock:
    """Управляемые часы: тест сам двигает время вперёд."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class StubSource:
    """Заглушка `ProgressSource`: отдаёт заранее положенный срез."""

    def __init__(self, snapshot: ProgressSnapshot) -> None:
        self.value = snapshot
        self.calls = 0

    def snapshot(self) -> ProgressSnapshot:
        self.calls += 1
        return self.value


class RecordingView:
    """Заглушка `ProgressView`: запоминает, что и когда её просили нарисовать."""

    def __init__(self) -> None:
        self.frames: list[tuple[ProgressSnapshot, tuple[str, ...]]] = []
        self.clears = 0
        self.drawn = threading.Event()

    def draw(self, snapshot: ProgressSnapshot, messages: Sequence[str]) -> None:
        self.frames.append((snapshot, tuple(messages)))
        self.drawn.set()

    def clear(self) -> None:
        self.clears += 1

    @property
    def last_messages(self) -> tuple[str, ...]:
        return self.frames[-1][1]


class BrokenView:
    """Заглушка `ProgressView`, которая всегда падает: проверка правила 11."""

    def draw(self, snapshot: ProgressSnapshot, messages: Sequence[str]) -> None:
        raise RuntimeError("экран отвалился")

    def clear(self) -> None:
        raise RuntimeError("стереть тоже не вышло")


class TtyStream(io.StringIO):
    """Текстовый поток, притворяющийся терминалом."""

    def isatty(self) -> bool:
        return True


def _snapshot(**overrides: int) -> ProgressSnapshot:
    """Срез счётчиков с различимыми значениями (каждое поле — своё число)."""
    fields: dict[str, int] = {
        "repos_total": 10,
        "repos_done": 3,
        "md_found": 128,
        "parsed": 96,
        "task_qsize": 32,
        "result_qsize": 4,
        "links": 640,
        "broken": 7,
    }
    fields.update(overrides)
    return ProgressSnapshot(**fields)


def _config(**progress_fields: object) -> ScanConfig:
    """`ScanConfig` из значений по умолчанию с переопределённой секцией `progress`."""
    draft = ConfigDraft.from_defaults()
    for name, value in progress_fields.items():
        draft.assign(f"progress.{name}", value, SOURCE_CMDLINE)
    return ScanConfig.from_draft(draft)


def _reporter(
    view: object,
    clock: FakeClock,
    *,
    message_lines: int = 1,
    ttl: float = 5.0,
    source: StubSource | None = None,
) -> ProgressReporter:
    """Репортёр на управляемых часах; поток не стартует — такты зовём вручную."""
    return ProgressReporter(
        source=source or StubSource(_snapshot()),
        view=view,  # type: ignore[arg-type]
        interval_sec=1.0,
        message_lines=message_lines,
        message_ttl_sec=ttl,
        clock=clock,
    )


# --------------------------------------------------------------------------------------
# 1. строка-сообщение гаснет через TTL
# --------------------------------------------------------------------------------------


def test_message_disappears_after_ttl() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock, ttl=5.0)

    reporter.show("[parse] docs/install.md — 12 ссылок")
    reporter.tick()
    assert view.last_messages == ("[parse] docs/install.md — 12 ссылок",)

    clock.advance(4.9)
    reporter.tick()
    assert view.last_messages == ("[parse] docs/install.md — 12 ссылок",), "TTL ещё не истёк"

    clock.advance(0.1)
    reporter.tick()
    assert view.last_messages == (), "по истечении TTL строка гаснет сама"


def test_message_ttl_counted_from_show_time() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock, message_lines=2, ttl=5.0)

    reporter.show("раннее")
    clock.advance(3.0)
    reporter.show("позднее")

    clock.advance(2.0)  # t = 5.0: раннее истекло, позднее живо до t = 8.0
    reporter.tick()
    assert view.last_messages == ("позднее",)


# --------------------------------------------------------------------------------------
# 2. новое сообщение вытесняет старое
# --------------------------------------------------------------------------------------


def test_new_message_replaces_old_when_one_line() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock, message_lines=1)

    reporter.show("[parse] a.md")
    reporter.show("[http] https://example.org — 404")
    reporter.tick()

    assert view.last_messages == ("[http] https://example.org — 404",)


def test_message_lines_two_keeps_both_in_order() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock, message_lines=2)

    reporter.show("первое")
    reporter.show("второе")
    reporter.show("третье")
    reporter.tick()

    assert view.last_messages == ("второе", "третье"), "держим две последние строки"


def test_show_is_thread_safe() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock, message_lines=200, ttl=1000.0)

    def flood(prefix: str) -> None:
        for index in range(100):
            reporter.show(f"{prefix}-{index}")

    threads = [threading.Thread(target=flood, args=(f"t{n}",)) for n in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)
        assert not thread.is_alive()

    reporter.tick()
    assert len(view.last_messages) == 200, "ни одна запись не потеряна и не задвоена"


# --------------------------------------------------------------------------------------
# 3-4. фабрика: не TTY / выключено конфигом → None
# --------------------------------------------------------------------------------------


def test_factory_returns_none_when_stream_is_not_tty() -> None:
    stream = io.StringIO()  # isatty() → False
    assert ProgressFactory().create(_config(), StubSource(_snapshot()), stream) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("enabled", False), ("style", "off")],
    ids=["enabled=false", "style=off"],
)
def test_factory_returns_none_when_disabled_by_config(field: str, value: object) -> None:
    config = _config(**{field: value})
    stream = TtyStream()
    assert ProgressFactory().create(config, StubSource(_snapshot()), stream) is None
    assert stream.getvalue() == "", "выключенный прогресс ничего не пишет"


def test_factory_builds_reporter_for_tty_without_starting_thread() -> None:
    stream = TtyStream()
    reporter = ProgressFactory().create(_config(), StubSource(_snapshot()), stream)

    assert reporter is not None
    assert isinstance(reporter, ProgressReporter)
    assert not reporter.is_alive(), "фабрика поток не стартует — это делает оркестратор"
    assert reporter.daemon is True


# --------------------------------------------------------------------------------------
# 5. stop() стирает строку и завершает поток
# --------------------------------------------------------------------------------------


def test_stop_clears_view_and_joins_thread() -> None:
    view = RecordingView()
    reporter = ProgressReporter(
        source=StubSource(_snapshot()),
        view=view,  # type: ignore[arg-type]
        interval_sec=0.01,
        message_lines=1,
        message_ttl_sec=5.0,
    )

    reporter.start()
    assert view.drawn.wait(timeout=5.0), "поток обязан нарисовать хотя бы один кадр"
    reporter.stop()

    assert not reporter.is_alive()
    assert reporter not in threading.enumerate(), "поток прогресса не остался жить"
    assert view.clears == 1, "строка стёрта ровно один раз"


def test_stop_without_start_only_clears() -> None:
    clock = FakeClock()
    view = RecordingView()
    reporter = _reporter(view, clock)

    reporter.stop()

    assert view.clears == 1
    assert view.frames == []


def test_broken_view_does_not_kill_reporter() -> None:
    clock = FakeClock()
    reporter = _reporter(BrokenView(), clock)

    reporter.start()
    reporter.stop()  # исключения из draw/clear логируются, наружу не выходят

    assert not reporter.is_alive()


# --------------------------------------------------------------------------------------
# 6. зона 1 показывает все поля ProgressSnapshot
# --------------------------------------------------------------------------------------


def test_status_line_contains_every_snapshot_field() -> None:
    stream = io.StringIO()
    snapshot = _snapshot()
    PlainProgressView(stream).draw(snapshot, ())

    output = stream.getvalue()
    for value in (
        snapshot.repos_total,
        snapshot.repos_done,
        snapshot.md_found,
        snapshot.parsed,
        snapshot.task_qsize,
        snapshot.result_qsize,
        snapshot.links,
        snapshot.broken,
    ):
        assert str(value) in output
    assert CLEAR_LINE in output, "строка статуса очищается ANSI-последовательностью"


def test_reporter_passes_source_snapshot_to_view() -> None:
    clock = FakeClock()
    view = RecordingView()
    source = StubSource(_snapshot(repos_done=9, broken=42))
    reporter = _reporter(view, clock, source=source)

    reporter.tick()

    assert source.calls == 1
    assert view.frames[-1][0] is source.value


def test_plain_view_redraws_in_place_and_clears() -> None:
    stream = io.StringIO()
    view = PlainProgressView(stream)

    view.draw(_snapshot(), ("сообщение",))
    first = stream.getvalue()
    assert first.count("\n") == 1, "две строки — статус и сообщение, без хвостового перевода"

    view.draw(_snapshot(parsed=97), ())
    redraw = stream.getvalue()[len(first) :]
    assert redraw.startswith("\r"), "перерисовка начинается с возврата каретки"
    assert "\x1b[1A" in redraw, "курсор поднимается к началу блока"
    assert CLEAR_BELOW in redraw, "хвост прошлого блока стирается"

    before_clear = len(stream.getvalue())
    view.clear()
    assert stream.getvalue()[before_clear:] == f"\r{CLEAR_BELOW}"

    after_clear = len(stream.getvalue())
    view.clear()
    assert stream.getvalue()[after_clear:] == "", "повторный clear() ничего не пишет"


# --------------------------------------------------------------------------------------
# 7. plain работает без rich; rich — когда библиотека есть
# --------------------------------------------------------------------------------------


def test_factory_falls_back_to_plain_view_without_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "rich", None)  # find_spec("rich") → None
    stream = TtyStream()

    reporter = ProgressFactory().create(_config(), StubSource(_snapshot()), stream)

    assert reporter is not None
    reporter.tick()
    assert "repos" in stream.getvalue(), "PlainProgressView рисует без rich"


def test_rich_view_draws_and_clears() -> None:
    pytest.importorskip("rich", reason="rich не установлен — ветка красивой отрисовки пропущена")
    from core.mdscan.runtime.rich_progress_view import RichProgressView

    stream = TtyStream()
    view = RichProgressView(stream)

    view.draw(_snapshot(), ("[http] https://example.org — 404",))
    view.draw(_snapshot(parsed=97), ())
    view.clear()
    view.clear()  # повторный вызов безопасен

    assert stream.getvalue() != ""


def test_factory_uses_rich_view_when_available() -> None:
    pytest.importorskip("rich", reason="rich не установлен — выбор rich-ветки не проверяем")
    from core.mdscan.runtime.rich_progress_view import RichProgressView

    stream = TtyStream()
    reporter = ProgressFactory().create(_config(), StubSource(_snapshot()), stream)

    assert reporter is not None
    # заглядываем в приватное поле намеренно: проверяем именно выбор фабрики, а не отрисовку
    assert isinstance(reporter._view, RichProgressView)
    reporter.tick()
    assert stream.getvalue() != "", "rich-ветка тоже рисует в переданный поток"
