"""T-04 — многопоточное логирование: очередь, формат, шапка, имена файлов."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from core.mdscan.log_setup.log_format import LogFormat
from core.mdscan.log_setup.log_naming import LogNaming
from core.mdscan.log_setup.logging_setup import LOGGER_NAME, LoggingSetup

# время | уровень | поток | repo | file | сообщение
LINE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
    r" \| (?:DEBUG|INFO|WARNING|ERROR|CRITICAL)"
    r" \| (?P<thread>\S+) \| (?P<repo>\S+) \| (?P<file>\S+) \| (?P<message>.*)$"
)

HEADER = {
    "scope": "dsp-gpu (github organization)",
    "started": "2026-08-16 05:00:12 +03:00",
    "input": "https://github.com/dsp-gpu",
    "workers": "discover=5 parse=5 http=5",
    "checks": "local=on http=on nested=on",
    "report": "out/hw01/dsp-gpu_2026-08-16_05-00-12.md",
}

WHEN = datetime(2026, 8, 16, 19, 7, 22)


@pytest.fixture
def setup() -> Iterator[LoggingSetup]:
    """`LoggingSetup`, который гарантированно останавливается и не течёт в соседний тест."""
    instance = LoggingSetup()
    try:
        yield instance
    finally:
        instance.stop()
        package_logger = logging.getLogger(LOGGER_NAME)
        for handler in list(package_logger.handlers):
            package_logger.removeHandler(handler)


def _lines(log_file: Path) -> list[str]:
    return log_file.read_text(encoding="utf-8").splitlines()


def _records(log_file: Path) -> list[str]:
    """Строки-записи: шапка помечена маркером `#` и в подсчёт не идёт."""
    return [line for line in _lines(log_file) if not line.startswith("#")]


# --- 1. 5 потоков x 200 записей -> ровно 1000 строк, ни одной битой ---------------------


def test_five_threads_write_exactly_1000_records(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "INFO", HEADER)
    gate = threading.Event()

    def work(index: int) -> None:
        gate.wait(timeout=10.0)
        for number in range(200):
            logger.info("запись %d-%d", index, number, extra={"repo": "repo-a", "file": "docs/a.md"})

    threads = [threading.Thread(target=work, args=(i,), name=f"parse-{i}") for i in range(5)]
    for thread in threads:
        thread.start()
    gate.set()
    for thread in threads:
        thread.join(timeout=30.0)
    assert not [t.name for t in threads if t.is_alive()]

    setup.stop()
    records = _records(log_file)
    assert len(records) == 1000
    assert all(LINE_RE.match(line) for line in records)
    assert len({line.split(" | ")[-1] for line in records}) == 1000


# --- 2. формат строки ------------------------------------------------------------------


def test_line_matches_format(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "DEBUG", {})
    logger.warning("link BROKEN", extra={"repo": "dsp-gpu", "file": "docs/a.md"})
    setup.stop()

    match = LINE_RE.match(_records(log_file)[0])
    assert match is not None
    assert match.group("thread") == "MainThread"
    assert match.group("repo") == "dsp-gpu"
    assert match.group("file") == "docs/a.md"
    assert match.group("message") == "link BROKEN"


def test_missing_context_renders_as_dash(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "INFO", {})
    logger.info("старт прогона")
    setup.stop()

    match = LINE_RE.match(_records(log_file)[0])
    assert match is not None
    assert (match.group("repo"), match.group("file")) == (LogFormat.MISSING, LogFormat.MISSING)


def test_package_logger_is_named_and_isolated(tmp_path: Path, setup: LoggingSetup) -> None:
    logger = setup.start(tmp_path / "scan.log", "INFO", {})
    assert logger.name == LOGGER_NAME
    assert logger.propagate is False
    assert logging.getLogger("core.mdscan.parsing").parent is logger


# --- 3. шапка --------------------------------------------------------------------------


def test_header_written_first_with_all_fields(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "INFO", HEADER)
    logger.info("после шапки")
    setup.stop()

    lines = _lines(log_file)
    head = lines[: len(HEADER)]
    assert all(line.startswith("# ") for line in head)
    assert len([line for line in lines if line.startswith("#")]) == len(HEADER)
    for position, (key, value) in enumerate(HEADER.items()):
        assert head[position].startswith(f"# {key}")
        assert head[position].endswith(f": {value}")


# --- 4. stop() дожидается очереди ------------------------------------------------------


def test_stop_waits_for_last_record(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "INFO", {})
    for number in range(500):
        logger.info("запись %d", number)
    setup.stop()

    records = _records(log_file)
    assert len(records) == 500
    assert records[-1].endswith("запись 499")


def test_stop_is_idempotent(tmp_path: Path, setup: LoggingSetup) -> None:
    log_file = tmp_path / "scan.log"
    logger = setup.start(log_file, "INFO", {})
    logger.info("единственная")
    setup.stop()
    setup.stop()

    assert len(_records(log_file)) == 1
    assert not logging.getLogger(LOGGER_NAME).handlers


def test_stop_without_start_does_nothing() -> None:
    LoggingSetup().stop()


# --- 5. имена файлов -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ("dsp-gpu", "dsp-gpu_2026-08-16_19-07-22.log"),
        ("Мой репозиторий", "Мой_репозиторий_2026-08-16_19-07-22.log"),
        ("  два   пробела  ", "два_пробела_2026-08-16_19-07-22.log"),
        (r'a<b>c:d"e/f\g|h?i*j', "abcdefghij_2026-08-16_19-07-22.log"),
        ("", "scan_2026-08-16_19-07-22.log"),
        ("   ", "scan_2026-08-16_19-07-22.log"),
        ("***", "scan_2026-08-16_19-07-22.log"),
    ],
    ids=["ascii", "cyrillic", "spaces", "forbidden-chars", "empty", "blank", "all-stripped"],
)
def test_log_naming_build(scope: str, expected: str) -> None:
    assert LogNaming().build(scope, WHEN, "log") == expected


def test_log_naming_shares_stamp_between_log_and_report() -> None:
    naming = LogNaming()
    assert naming.build("dsp-gpu", WHEN, "md") == "dsp-gpu_2026-08-16_19-07-22.md"
    assert naming.build("dsp-gpu", WHEN, ".md") == "dsp-gpu_2026-08-16_19-07-22.md"


# --- 6. logging.enabled: false ---------------------------------------------------------


def test_disabled_logging_creates_no_file(tmp_path: Path, setup: LoggingSetup) -> None:
    logger = setup.start(None, "INFO", HEADER)
    logger.info("не должно упасть", extra={"repo": "r", "file": "f"})
    logger.warning("и это тоже")
    setup.stop()

    assert list(tmp_path.iterdir()) == []


def test_disabled_logging_uses_null_handler(setup: LoggingSetup) -> None:
    logger = setup.start(None, "INFO", {})
    assert [type(handler) for handler in logger.handlers] == [logging.NullHandler]


def test_unknown_level_raises(setup: LoggingSetup, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="неизвестный уровень"):
        setup.start(tmp_path / "scan.log", "VERBOSE", {})
