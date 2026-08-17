"""Правило 5 цепочки: телефонная ссылка `tel:`."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class TelRule:
    """`tel:+78120000000` — считаем и логируем, не проверяем (`NullChecker`)."""

    _SCHEME = "tel:"

    def matches(self, link: MdLink) -> bool:
        return link.target.lower().startswith(self._SCHEME)

    @property
    def kind(self) -> LinkKind:
        return LinkKind.TEL
