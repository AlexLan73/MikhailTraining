"""Сборка Markdown-отчёта о расходе токенов."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .models.token_totals import TokenTotals
from .token_aggregator import TokenAggregator

_LOG = logging.getLogger("core.tokenstat")
_HEAD = "| requests | in | out | cache_create | cache_read | thinking |"
_SEP = "|---:|---:|---:|---:|---:|---:|"


class TokenReportBuilder:
    """Отчёт: общий итог, таблица по агентам, свод «агенты» / «оркестрант»."""

    def __init__(self, orchestrator: str) -> None:
        self._orchestrator = orchestrator

    def build(
        self,
        aggregator: TokenAggregator,
        label: str,
        started_at: datetime | None,
        finished_at: datetime | None,
    ) -> str:
        """Текст отчёта в Markdown (детерминирован при одинаковых данных)."""
        agents = aggregator.by_agent()
        crew = TokenTotals()
        for name, totals in agents.items():
            if name != self._orchestrator:
                crew = crew + totals
        boss = agents.get(self._orchestrator, TokenTotals())
        lines = [
            f"# Токены прогона — {label or 'без метки'}",
            "",
            f"- старт: {self._moment(started_at)}",
            f"- финиш: {self._moment(finished_at)}",
            f"- запросов: {aggregator.total.requests}",
            f"- всего токенов: {aggregator.total.billable}",
            "",
            "## Итог",
            "",
            _HEAD,
            _SEP,
            self._row(aggregator.total),
            "",
            "## По агентам",
            "",
            "| агент | таск | модели | requests | in | out | cache_create | cache_read | thinking |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for name, totals in agents.items():
            models = ", ".join(aggregator.models_of(name)) or "-"
            task = aggregator.task_of(name) or "-"
            lines.append(f"| {name} | {task} | {models} | {self._cells(totals)} |")
        lines += [
            "",
            "## По таскам",  # H-11: `by_task` был, но в отчёт не попадал; H-12 нужна разбивка по TASK=
            "",
            "| таск | requests | in | out | cache_create | cache_read | thinking |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for task, totals in sorted(aggregator.by_task().items()):
            lines.append(f"| {task or '-'} | {self._cells(totals)} |")
        lines += [
            "",
            "## Свод",
            "",
            "| группа | requests | in | out | cache_create | cache_read | thinking |",
            "|---|---:|---:|---:|---:|---:|---:|",
            f"| агенты | {self._cells(crew)} |",
            f"| оркестрант | {self._cells(boss)} |",
            "",
        ]
        return "\n".join(lines)

    def write(self, text: str, directory: Path, when: datetime) -> Path:
        """Записать отчёт как ``tokens_<YYYY-MM-DD>_<HH-MM-SS>.md`` и вернуть путь."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"tokens_{when:%Y-%m-%d_%H-%M-%S}.md"
        path.write_text(text, encoding="utf-8")
        _LOG.info("отчёт по токенам записан: %s", path)
        return path

    def _row(self, totals: TokenTotals) -> str:
        return f"| {self._cells(totals)} |"

    def _cells(self, t: TokenTotals) -> str:
        return f"{t.requests} | {t.input} | {t.output} | {t.cache_creation} | {t.cache_read} | {t.thinking}"

    def _moment(self, when: datetime | None) -> str:
        return when.strftime("%Y-%m-%d %H:%M:%S") if when is not None else "-"
