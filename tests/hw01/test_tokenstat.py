"""Тесты T-15: подсчёт токенов по JSONL-транскрипту (core.tokenstat).

Все данные — синтетический JSONL в `tmp_path`; реальные транскрипты не читаются.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pytest

from core.tokenstat import TokenTotals, TranscriptTokenMeter
from core.tokenstat.token_aggregator import TokenAggregator
from core.tokenstat.transcript_reader import TranscriptReader
from core.tokenstat.transcript_token_meter import ORCHESTRATOR_AGENT

FIXED_NOW = datetime(2026, 8, 16, 20, 30, 40)


def assistant(
    request_id: str,
    *,
    model: str = "claude-opus-5",
    inp: int = 10,
    out: int = 5,
    cache_creation: int = 3,
    cache_read: int = 2,
    thinking: int | None = 1,
) -> str:
    """Строка транскрипта с ответом модели."""
    usage: dict[str, object] = {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
    }
    if thinking is not None:
        usage["output_tokens_details"] = {"thinking_tokens": thinking}
    return json.dumps(
        {
            "type": "assistant",
            "requestId": request_id,
            "timestamp": "2026-08-16T17:00:00.000Z",
            "message": {"model": model, "role": "assistant", "usage": usage},
        }
    )


def user(text: str) -> str:
    """Строка транскрипта с сообщением пользователя (в подсчёт не идёт)."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def write(path: Path, lines: list[str]) -> None:
    """Записать файл транскрипта."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append(path: Path, lines: list[str]) -> None:
    """Дописать строки в конец транскрипта."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


@pytest.fixture
def session(tmp_path: Path) -> Path:
    """Главный файл сессии с двумя строками «до старта»."""
    path = tmp_path / "sess.jsonl"
    write(path, [user("привет"), assistant("req-old", inp=1000, out=1000)])
    return path


def agent_file(session_file: Path, name: str) -> Path:
    """Путь к файлу субагента рядом с сессией."""
    return session_file.parent / session_file.stem / "subagents" / f"agent-{name}.jsonl"


def meter(session_file: Path) -> TranscriptTokenMeter:
    """Счётчик с фиксированными часами."""
    return TranscriptTokenMeter(session_file, clock=lambda: FIXED_NOW)


# --- 1 ---------------------------------------------------------------------
def test_totals_match_reference(session: Path) -> None:
    """Суммы по полям совпадают с эталоном, thinking учитывается отдельно."""
    counter = meter(session)
    counter.start("T-15")
    append(
        session,
        [
            assistant("req-1", inp=100, out=20, cache_creation=7, cache_read=5, thinking=9),
            assistant("req-2", inp=1, out=2, cache_creation=3, cache_read=4, thinking=None),
        ],
    )
    counter.stop()

    assert counter.total == TokenTotals(
        requests=2, input=101, output=22, cache_creation=10, cache_read=9, thinking=9
    )
    assert counter.total.billable == 101 + 22 + 10 + 9


# --- 2 ---------------------------------------------------------------------
def test_lines_before_start_are_ignored(session: Path) -> None:
    """Строки, существовавшие до метки старта, в окно не попадают."""
    counter = meter(session)
    counter.start("T-15")
    append(session, [assistant("req-1", inp=7, out=3)])
    counter.stop()

    assert counter.total.requests == 1
    assert counter.total.input == 7
    assert counter.by_agent()[ORCHESTRATOR_AGENT].input == 7


# --- 3 ---------------------------------------------------------------------
def test_grouping_by_agent(session: Path) -> None:
    """Каждый агент и оркестрант считаются отдельно."""
    counter = meter(session)
    counter.start("wave-0")
    append(session, [assistant("req-main", inp=5, out=5)])
    write(agent_file(session, "aaa"), [user("TASK=T-06\n\nразбор"), assistant("req-a", inp=50, out=10)])
    write(agent_file(session, "bbb"), [user("TASK=T-07\n\nпроверка"), assistant("req-b", inp=70, out=20)])
    counter.stop()

    by_agent = counter.by_agent()
    assert set(by_agent) == {ORCHESTRATOR_AGENT, "agent-aaa", "agent-bbb"}
    assert by_agent["agent-aaa"].input == 50
    assert by_agent["agent-bbb"].output == 20
    assert counter.total.requests == 3


# --- 4 ---------------------------------------------------------------------
def test_broken_line_warns_and_parsing_continues(
    session: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Битая строка JSONL → WARNING, остальные строки разобраны."""
    counter = meter(session)
    counter.start("T-15")
    append(session, [assistant("req-1", inp=4), "{это не json", assistant("req-2", inp=6)])
    with caplog.at_level(logging.WARNING, logger="core.tokenstat"):
        counter.stop()

    assert counter.total.requests == 2
    assert counter.total.input == 10
    assert any("битая строка JSONL" in record.message for record in caplog.records)


# --- 5 ---------------------------------------------------------------------
def test_report_contains_total_and_breakdown(session: Path) -> None:
    """Отчёт содержит итог, таблицу по агентам и свод «агенты» / «оркестрант»."""
    counter = meter(session)
    counter.start("wave-0")
    append(session, [assistant("req-main", inp=5, out=5)])
    write(agent_file(session, "aaa"), [user("TASK=T-06"), assistant("req-a", inp=50, out=10)])
    counter.stop()

    text = counter.report()
    assert "# Токены прогона — wave-0" in text
    assert "## Итог" in text
    assert "## По агентам" in text
    assert "| agent-aaa | T-06 |" in text
    assert "| агенты |" in text
    assert "| оркестрант |" in text
    assert counter.report() == text  # детерминизм


def test_report_written_to_file(session: Path, tmp_path: Path) -> None:
    """`write()` кладёт отчёт файлом `tokens_<дата>_<время>.md`."""
    counter = meter(session)
    counter.start("wave-0")
    append(session, [assistant("req-main")])
    counter.stop()

    path = counter.write(tmp_path / "out")
    assert path.name == "tokens_2026-08-16_20-30-40.md"
    assert "## Свод" in path.read_text(encoding="utf-8")


# --- 6 ---------------------------------------------------------------------
def test_agent_task_label_and_preexisting_agent_ignored(session: Path) -> None:
    """Ярлык TASK= даёт таск; файл агента, бывший до старта, не учитывается."""
    old = agent_file(session, "old")
    write(old, [user("TASK=T-01\n\nстарый прогон"), assistant("req-old-agent", inp=999)])

    counter = meter(session)
    counter.start("wave-1")
    write(agent_file(session, "new"), [user("TASK=T-06\n\nработа"), assistant("req-new", inp=11)])
    counter.stop()

    by_agent = counter.by_agent()
    assert "agent-old" not in by_agent
    assert by_agent["agent-new"].input == 11
    assert counter.total.input == 11


# --- 7 ---------------------------------------------------------------------
def test_duplicate_request_id_counted_once(session: Path) -> None:
    """Три строки одного requestId (стриминг) учитываются один раз."""
    counter = meter(session)
    counter.start("T-15")
    line = assistant("req-stream", inp=30, out=8, cache_creation=2, cache_read=1, thinking=4)
    append(session, [line, line, line])
    counter.stop()

    assert counter.total == TokenTotals(
        requests=1, input=30, output=8, cache_creation=2, cache_read=1, thinking=4
    )


# --- дополнительные проверки контракта -------------------------------------
def test_mark_used_when_task_label_missing(session: Path) -> None:
    """Нет ярлыка TASK= в файле → таск берётся из `mark()`."""
    counter = meter(session)
    counter.start("wave-1")
    write(agent_file(session, "zzz"), [user("просто промпт"), assistant("req-z", inp=3)])
    counter.mark("agent-zzz", "T-09")
    counter.stop()

    assert "| agent-zzz | T-09 |" in counter.report()


def test_task_label_wins_over_mark(session: Path) -> None:
    """Ярлык в файле важнее ручной привязки."""
    counter = meter(session)
    counter.start("wave-1")
    write(agent_file(session, "yyy"), [user("TASK=T-06\n\nработа"), assistant("req-y")])
    counter.mark("agent-yyy", "T-09")
    counter.stop()

    assert "| agent-yyy | T-06 |" in counter.report()


def test_missing_session_file_gives_empty_totals(tmp_path: Path) -> None:
    """Нет файла сессии → нулевой итог и никаких исключений."""
    counter = meter(tmp_path / "нет.jsonl")
    counter.start("T-15")
    counter.stop()

    assert counter.total == TokenTotals()


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (TokenTotals(), TokenTotals(requests=1, input=2), TokenTotals(requests=1, input=2)),
        (
            TokenTotals(requests=1, output=3, thinking=1),
            TokenTotals(requests=2, output=4, thinking=2),
            TokenTotals(requests=3, output=7, thinking=3),
        ),
    ],
    ids=["с-нулём", "две-суммы"],
)
def test_totals_addition(left: TokenTotals, right: TokenTotals, expected: TokenTotals) -> None:
    """`TokenTotals.__add__` складывает поэлементно."""
    assert left + right == expected


def test_totals_frozen() -> None:
    """`TokenTotals` неизменяем."""
    totals = TokenTotals(requests=1)
    with pytest.raises(AttributeError):
        totals.requests = 2  # type: ignore[misc]


def test_aggregator_groups_by_task_and_model(session: Path) -> None:
    """Агрегатор группирует и по таскам, и по моделям."""
    write(session, [assistant("r1", model="opus", inp=10), assistant("r2", model="sonnet", inp=1)])
    aggregator = TokenAggregator()
    aggregator.add("agent-1", "T-06", TranscriptReader(session).read())

    assert aggregator.by_task()["T-06"].input == 11
    assert aggregator.by_model()["opus"].input == 10
    assert aggregator.by_model()["sonnet"].input == 1
    assert aggregator.models_of("agent-1") == ("opus", "sonnet")


def test_reader_skips_non_assistant_lines(session: Path) -> None:
    """Строки не-`assistant` игнорируются."""
    write(session, [user("привет"), json.dumps({"type": "system"}), assistant("r1", inp=5)])
    usages = TranscriptReader(session).read()

    assert len(usages) == 1
    assert usages[0].request_id == "r1"
    assert usages[0].input == 5
