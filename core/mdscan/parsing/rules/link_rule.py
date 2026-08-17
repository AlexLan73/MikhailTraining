"""Контракт одного звена цепочки классификации ссылок (Chain of Responsibility, D8.3)."""

from __future__ import annotations

from typing import Protocol

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class LinkRule(Protocol):
    """Одно правило = один случай = один файл.

    Правило получает **`MdLink`**, а не голую строку-цель: `[[wiki]]` и сноску
    по цели не отличить — нужен `link.origin` (решение Alex, D8.1).
    """

    def matches(self, link: MdLink) -> bool:
        """`True`, если ссылка относится к случаю этого правила."""
        ...

    @property
    def kind(self) -> LinkKind:
        """Категория, которую правило присваивает подошедшей ссылке."""
        ...
