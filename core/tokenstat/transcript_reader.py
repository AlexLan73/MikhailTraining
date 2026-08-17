"""Чтение JSONL-транскрипта Claude Code: строки → записи :class:`TokenUsage`."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .models.token_usage import TokenUsage

_LOG = logging.getLogger("core.tokenstat")
_TASK_LABEL = re.compile(r"\s*TASK\s*=\s*(\S+)")


class TranscriptReader:
    """Один файл транскрипта (сессии или субагента).

    Учитываются только строки ``type == "assistant"``. Один ``requestId``
    встречается в нескольких строках (стриминг) с одинаковым ``usage`` — запись
    берётся **один раз**, побеждает последняя строка.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        """Файл транскрипта."""
        return self._path

    def line_count(self) -> int:
        """Число строк в файле — метка смещения для окна прогона."""
        return sum(1 for _ in self._lines())

    def read(self, offset: int = 0) -> tuple[TokenUsage, ...]:
        """Записи после строки ``offset`` (1-based), по одной на ``requestId``."""
        found: dict[str, TokenUsage] = {}
        for number, line in enumerate(self._lines(), start=1):
            if number <= offset:
                continue
            record = self._record(line, number)
            if record is None or record.get("type") != "assistant":
                continue
            usage = self._usage(record)
            if usage is not None:
                found[usage.request_id] = usage
        return tuple(found.values())

    def task_label(self) -> str:
        """Ярлык ``TASK=<id>`` из первого сообщения файла; нет ярлыка → пустая строка."""
        for line in self._lines():
            record = self._record(line, 1)
            if record is None:
                return ""
            match = _TASK_LABEL.match(self._text(record))
            return match.group(1) if match else ""
        return ""

    def _lines(self) -> Iterator[str]:
        try:
            with self._path.open(encoding="utf-8", errors="replace") as handle:
                yield from handle
        except OSError as exc:
            _LOG.error("транскрипт не прочитан: %s (%s)", self._path, exc, exc_info=True)

    def _record(self, line: str, number: int) -> dict[str, Any] | None:
        text = line.strip()
        if not text:
            return None
        try:
            record = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            _LOG.warning("битая строка JSONL пропущена: %s:%d (%s)", self._path.name, number, exc)
            return None
        if not isinstance(record, dict):
            _LOG.warning("строка JSONL не объект, пропущена: %s:%d", self._path.name, number)
            return None
        return record

    def _usage(self, record: Mapping[str, Any]) -> TokenUsage | None:
        message = record.get("message")
        message = message if isinstance(message, Mapping) else {}
        usage = message.get("usage")
        usage = usage if isinstance(usage, Mapping) else {}
        request_id = str(record.get("requestId") or message.get("id") or "")
        if not request_id or not usage:
            return None
        details = usage.get("output_tokens_details")
        details = details if isinstance(details, Mapping) else {}
        return TokenUsage(
            request_id=request_id,
            model=str(message.get("model") or ""),
            timestamp=self._moment(record.get("timestamp")),
            input=self._number(usage, "input_tokens"),
            output=self._number(usage, "output_tokens"),
            cache_creation=self._number(usage, "cache_creation_input_tokens"),
            cache_read=self._number(usage, "cache_read_input_tokens"),
            thinking=self._number(details, "thinking_tokens"),
        )

    def _text(self, record: Mapping[str, Any]) -> str:
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [str(b.get("text", "")) for b in content if isinstance(b, Mapping)]
            return "\n".join(parts)
        return ""

    def _number(self, source: Mapping[str, Any], key: str) -> int:
        try:
            return int(source.get(key) or 0)
        except (TypeError, ValueError):
            _LOG.warning("нечисловое поле %s в %s", key, self._path.name)
            return 0

    def _moment(self, raw: Any) -> datetime | None:
        if not isinstance(raw, str) or not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            _LOG.warning("непонятная метка времени %r в %s", raw, self._path.name)
            return None
