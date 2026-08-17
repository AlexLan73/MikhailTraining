"""Правило 9 (последнее) цепочки: путь к файлу в дереве репозитория."""

from __future__ import annotations

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class LocalPathRule:
    """Всё, что не подошло раньше, считаем путём: `docs/a.md`, `../img/x.png`, `a.md#раздел`.

    Правило намеренно тотальное и стоит последним — это «дно» цепочки, а не
    ветка `else` внутри чужой функции (Open-Closed, D8.2). Если его убрать,
    такие ссылки станут `UNKNOWN` и попадут в отчёт отдельной строкой.
    """

    def matches(self, link: MdLink) -> bool:
        return bool(link.target)

    @property
    def kind(self) -> LinkKind:
        return LinkKind.LOCAL
