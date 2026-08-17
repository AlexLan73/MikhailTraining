"""Счётчик токенов прогона по транскрипту сессии Claude Code."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Final

from .models.token_totals import TokenTotals
from .token_aggregator import TokenAggregator
from .token_report_builder import TokenReportBuilder
from .transcript_reader import TranscriptReader

_LOG = logging.getLogger("core.tokenstat")

ORCHESTRATOR_AGENT: Final = "orchestrator"


class TranscriptTokenMeter:
    """Реализация :class:`TokenMeter` поверх JSONL-транскриптов.

    Окно прогона задаётся :meth:`start`: запоминается число строк главного файла и
    множество уже существующих ``subagents/agent-*.jsonl``. Учитываются строки главного
    файла **после** смещения и файлы агентов, появившиеся **после** старта. Таск агента
    берётся из ярлыка ``TASK=<id>`` в первом сообщении его файла, запасной путь — :meth:`mark`.
    """

    def __init__(self, session_file: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._session_file = session_file
        self._subagents_dir = session_file.parent / session_file.stem / "subagents"
        self._clock = clock
        self._builder = TokenReportBuilder(ORCHESTRATOR_AGENT)
        self._label = ""
        self._offset = 0
        self._known: frozenset[str] = frozenset()
        self._marks: dict[str, str] = {}
        self._started_at: datetime | None = None
        self._finished_at: datetime | None = None
        self._aggregator: TokenAggregator | None = None

    def start(self, label: str) -> None:
        """Открыть окно прогона под меткой ``label``."""
        self._label = label
        self._offset = TranscriptReader(self._session_file).line_count()
        self._known = frozenset(path.name for path in self._agent_files())
        self._started_at = self._clock()
        self._finished_at = None
        self._aggregator = None
        _LOG.info(
            "подсчёт токенов начат: метка=%s смещение=%d агентов до старта=%d",
            label,
            self._offset,
            len(self._known),
        )

    def start_from(self, label: str, offset: int, known_agents: Iterable[str] = ()) -> None:
        """Открыть окно по **сохранённой** точке отсчёта (другой процесс: скил записал смещение в файл).

        `offset` — число строк главного файла на момент старта, `known_agents` — имена
        файлов агентов, существовавших до старта. Нужен, потому что оркестрант считает
        токены не в том процессе, где вызывал :meth:`start`.
        """
        self._label = label
        self._offset = int(offset)
        self._known = frozenset(known_agents)
        self._started_at = self._clock()
        self._finished_at = None
        self._aggregator = None
        _LOG.info("подсчёт токенов от сохранённой точки: метка=%s смещение=%d", label, self._offset)

    def mark(self, agent: str, task: str) -> None:
        """Привязать агента к таску вручную; ярлык ``TASK=`` в файле важнее."""
        self._marks[agent] = task

    def stop(self) -> None:
        """Закрыть окно и посчитать итоги (повторный вызов безопасен)."""
        self._finished_at = self._clock()
        self._aggregator = self._collect()
        _LOG.info("подсчёт токенов завершён: %s", self._aggregator.total)

    @property
    def total(self) -> TokenTotals:
        """Суммарные токены окна."""
        return self._ready().total

    def by_agent(self) -> dict[str, TokenTotals]:
        """Итоги по агентам; главный транскрипт — под именем ``orchestrator``."""
        return self._ready().by_agent()

    def report(self) -> str:
        """Markdown-отчёт по окну прогона."""
        return self._builder.build(self._ready(), self._label, self._started_at, self._finished_at)

    def write(self, directory: Path) -> Path:
        """Записать отчёт файлом ``tokens_<YYYY-MM-DD>_<HH-MM-SS>.md`` в ``directory``."""
        when = self._finished_at or self._clock()
        return self._builder.write(self.report(), directory, when)

    def _ready(self) -> TokenAggregator:
        if self._aggregator is None:
            self._aggregator = self._collect()
        return self._aggregator

    def _collect(self) -> TokenAggregator:
        aggregator = TokenAggregator()
        main = TranscriptReader(self._session_file)
        aggregator.add(ORCHESTRATOR_AGENT, self._label or "-", main.read(self._offset))
        for path in self._agent_files():
            if path.name in self._known:
                _LOG.debug("файл агента существовал до старта, пропущен: %s", path.name)
                continue
            reader = TranscriptReader(path)
            agent = path.stem
            task = reader.task_label() or self._marks.get(agent, "") or "-"
            aggregator.add(agent, task, reader.read())
        return aggregator

    def _agent_files(self) -> list[Path]:
        if not self._subagents_dir.is_dir():
            return []
        return sorted(self._subagents_dir.glob("agent-*.jsonl"))
