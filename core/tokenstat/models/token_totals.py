"""Value Object: суммы токенов по группе записей."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenTotals:
    """Суммы полей :class:`TokenUsage` плюс число учтённых запросов.

    Складывается через ``+``: ``TokenTotals() + TokenTotals(...)`` — это позволяет
    копить итоги по агенту, задаче и модели одним и тем же способом.
    """

    requests: int = 0
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0
    thinking: int = 0

    def __add__(self, other: TokenTotals) -> TokenTotals:
        """Поэлементная сумма двух итогов."""
        if not isinstance(other, TokenTotals):
            return NotImplemented
        return TokenTotals(
            requests=self.requests + other.requests,
            input=self.input + other.input,
            output=self.output + other.output,
            cache_creation=self.cache_creation + other.cache_creation,
            cache_read=self.cache_read + other.cache_read,
            thinking=self.thinking + other.thinking,
        )

    @property
    def billable(self) -> int:
        """Все токены, прошедшие через модель: вход + выход + кэш.

        ``thinking`` не прибавляется — он уже входит в ``output``.
        """
        return self.input + self.output + self.cache_creation + self.cache_read
