"""Синтаксис, которым ссылка записана в Markdown.

Нужен правилам классификации: `[[wiki]]` и `[^1]` отличаются от обычной ссылки
только происхождением — по цели их не распознать.
"""

from __future__ import annotations

from enum import Enum


class LinkOrigin(Enum):
    """Откуда парсер взял ссылку."""

    INLINE = "inline"        # [текст](цель)
    REFERENCE = "reference"  # [текст][id] + [id]: цель
    AUTOLINK = "autolink"    # <https://…>
    WIKILINK = "wikilink"    # [[цель]]
    FOOTNOTE = "footnote"    # [^1] с URL в определении сноски
