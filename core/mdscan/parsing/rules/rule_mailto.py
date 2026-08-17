"""Правило 4 цепочки: почтовая ссылка `mailto:`."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class MailtoRule:
    """`mailto:alex@example.org` — считаем и логируем, не проверяем (`NullChecker`)."""

    _SCHEME = "mailto:"

    def matches(self, link: MdLink) -> bool:
        return link.target.lower().startswith(self._SCHEME)

    @property
    def kind(self) -> LinkKind:
        return LinkKind.MAILTO
