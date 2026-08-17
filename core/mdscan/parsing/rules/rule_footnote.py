"""Правило 2 цепочки: ссылка из определения сноски `[^1]: …`."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.models.md_link import MdLink


class FootnoteRule:
    """Цель внутри сноски: в v1 не проверяется, но считается и попадает в отчёт.

    Как и `WikilinkRule`, работает по `origin`: URL в сноске от обычного URL по
    строке-цели не отличить, поэтому правило обязано стоять раньше `HttpRule`.
    """

    def matches(self, link: MdLink) -> bool:
        return link.origin is LinkOrigin.FOOTNOTE

    @property
    def kind(self) -> LinkKind:
        return LinkKind.FOOTNOTE_URL
