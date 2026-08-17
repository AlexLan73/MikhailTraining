"""Правило 7 цепочки: обычный внешний адрес `http(s)://`."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class HttpRule:
    """Всё, что не перехватил `GithubRule`, но ходит по http(s), — `URL`.

    Место в цепочке значимо: правило обязано стоять **после** `GithubRule`,
    иначе перехватит его случаи (D8.2).
    """

    _SCHEMES = ("http://", "https://")

    def matches(self, link: MdLink) -> bool:
        return link.target.lower().startswith(self._SCHEMES)

    @property
    def kind(self) -> LinkKind:
        return LinkKind.URL
