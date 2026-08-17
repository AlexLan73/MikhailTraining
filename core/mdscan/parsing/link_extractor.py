"""Публичный контракт извлечения ссылок из текста Markdown.

Владелец контракта — пакет `parsing` (T-06); потребитель — `MarkdownWorker` (T-10),
который зависит от этого `Protocol`, а не от конкретного `MarkdownItLinkExtractor`
(DIP, правило 09 п.5).
"""

from __future__ import annotations

from typing import Protocol

from core.mdscan.models.md_link import MdLink


class LinkExtractor(Protocol):
    """Стратегия извлечения: текст файла → ссылки в порядке появления.

    Реализация обязана:

    - заполнить `target`, `origin` и `line` каждой ссылки;
    - оставить `kind` равным `LinkKind.UNKNOWN` — категорию ставит `LinkClassifier`;
    - **не** возвращать ссылки из fenced- и inline-code (инвариант 10 части 2).
    """

    def extract(self, text: str) -> tuple[MdLink, ...]: ...
