"""Правило 3 цепочки: якорь `#раздел` внутри своего файла."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class AnchorRule:
    """`#install` — самый узкий случай по цели, поэтому идёт раньше путей.

    Цель с путём (`a.md#раздел`) сюда не попадает: она начинается не с `#`
    и достаётся `LocalPathRule` — якорь в ней проверит `AnchorChecker` (T-07).
    """

    def matches(self, link: MdLink) -> bool:
        return link.target.startswith("#")

    @property
    def kind(self) -> LinkKind:
        return LinkKind.ANCHOR
