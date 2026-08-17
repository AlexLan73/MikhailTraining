"""Value Object: расход токенов одного ответа модели (одна запись транскрипта)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Токены **одного** запроса к модели.

    Поля повторяют `message.usage` JSONL-транскрипта Claude Code:

    - ``input`` / ``output`` — обычные токены запроса и ответа;
    - ``cache_creation`` / ``cache_read`` — запись и чтение кэша промпта;
    - ``thinking`` — токены размышления (``output_tokens_details.thinking_tokens``),
      входят в ``output`` и отдельно к сумме **не** прибавляются.

    Ключ записи — ``request_id``: одна и та же пара «запрос-ответ» встречается в
    транскрипте несколькими строками (стриминг) с одинаковым ``usage``.
    """

    request_id: str
    model: str = ""
    timestamp: datetime | None = None
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0
    thinking: int = 0
