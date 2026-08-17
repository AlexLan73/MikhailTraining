"""Null Object для `LinkChecker`: категория не проверяется или проверка выключена."""

from __future__ import annotations

import logging
from pathlib import Path

from ..enums.check_status import CheckStatus
from ..models.md_link import MdLink

_log = logging.getLogger("core.mdscan.checking")


class NullChecker:
    """Ничего не проверяет — только помечает ссылку как `SKIPPED`.

    Нужен, чтобы в конвейере не появилось `if checker is not None` и ветвлений
    по конфигу: выключенная проверка — это не отсутствие чекера, а другой чекер
    (правило 09, Null Object). Сюда попадают `mailto` / `tel` / `wikilink` /
    `footnote_url` / `unknown`, а также любая категория при `http.enabled: false`
    и `checks.local|anchors: false`.
    """

    def check(self, link: MdLink, md_file: Path) -> None:
        """Проставить `SKIPPED`; сетевых и дисковых обращений не делает."""
        link.status = CheckStatus.SKIPPED
        _log.debug("ссылка не проверяется: %s (%s)", link.target, link.kind.value)
