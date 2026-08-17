"""Правило 8 цепочки: `file:///…` — локальный файл, записанный как URI."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class FileUrlRule:
    """`file:///tmp/report.html` → `LOCAL` (требование условия ДЗ).

    Схему `file:` штатный `markdown-it` в HTML не пропускает, поэтому экстрактор
    отключает его `validateLink` — иначе такая ссылка терялась бы ещё до цепочки.
    """

    _SCHEME = "file://"

    def matches(self, link: MdLink) -> bool:
        return link.target.lower().startswith(self._SCHEME)

    @property
    def kind(self) -> LinkKind:
        return LinkKind.LOCAL
