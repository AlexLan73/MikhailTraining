"""Правило 1 цепочки: вики-ссылка `[[Страница]]`."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.models.md_link import MdLink


class WikilinkRule:
    """`[[Внутренняя страница]]` — распознаётся только по синтаксису.

    Стоит первой в цепочке: цель `project-notes` неотличима от относительного
    пути, поэтому после `LocalPathRule` правило не сработало бы никогда.
    """

    def matches(self, link: MdLink) -> bool:
        return link.origin is LinkOrigin.WIKILINK

    @property
    def kind(self) -> LinkKind:
        return LinkKind.WIKILINK
