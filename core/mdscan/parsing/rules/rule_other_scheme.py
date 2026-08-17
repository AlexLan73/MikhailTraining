"""Правило 8b цепочки: чужая URI-схема (`data:`, `javascript:`, `ftp:` …) — не путь и не HTTP.

Найдено боевым прогоном (H-01/H-02, ревью 6): встроенная картинка `data:image/png;base64,…`
доходила до тотального `LocalPathRule`, становилась `LOCAL`, давала ложный `BROKEN` и строку отчёта
на 1.8 МБ. Такие цели относим к `UNKNOWN` → `NullChecker` → `SKIPPED`: проверять их нечем.
"""

from __future__ import annotations

import re

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink


class OtherSchemeRule:
    r"""`<схема>:…` с буквенной схемой длиннее одной буквы (чтобы не спутать с `C:\path`) → `UNKNOWN`.

    Стоит **после** `mailto`/`tel`/`github`/`http`/`file` (у них свои правила) и **до** `LocalPathRule`.
    """

    _SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]+:")

    def matches(self, link: MdLink) -> bool:
        # http/file/mailto/tel перехвачены правилами выше; сюда доходят `data:`, `javascript:`, `ftp://`, `ssh://`…
        return self._SCHEME.match(link.target.strip()) is not None

    @property
    def kind(self) -> LinkKind:
        return LinkKind.UNKNOWN
