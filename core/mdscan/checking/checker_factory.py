"""Выдача чекера по категории ссылки: экземпляры создаются один раз на прогон."""

from __future__ import annotations

import logging

from ..config.scan_config import ScanConfig
from ..enums.link_kind import LinkKind
from ..runtime.notifier import Notifier
from .anchor_checker import AnchorChecker
from .heading_source import HeadingSource
from .http_checker import HttpChecker
from .link_checker import LinkChecker
from .local_file_checker import LocalFileChecker
from .null_checker import NullChecker

_log = logging.getLogger("core.mdscan.checking")


class CheckerFactory:
    """Связывает конфигурацию прогона с реализациями `LinkChecker`.

    `for_kind` отдаёт **общие** объекты, а не новые: у `HttpChecker` семафор и
    кэш общие на прогон (инвариант 22), у `AnchorChecker` — кэш заголовков.
    Поэтому вся таблица собирается в конструкторе, а выбор — поиск по словарю
    (ветвления по категории запрещены, правило 09 п.7).

    Выключенная проверка — это не «нет чекера», а `NullChecker` (Null Object):
    `checks.local: false` → LOCAL, `checks.anchors: false` → ANCHOR и якорная
    часть `a.md#x`, `http.enabled: false` → URL и GITHUB.
    """

    def __init__(self, config: ScanConfig, headings: HeadingSource, notifier: Notifier) -> None:
        null = NullChecker()
        anchors = AnchorChecker(headings) if config.checks.anchors else None
        anchor_checker: LinkChecker = anchors if anchors is not None else null
        local: LinkChecker = LocalFileChecker(anchors) if config.checks.local else null
        http: LinkChecker = self._http_checker(config, notifier) if config.http.enabled else null
        self._null: LinkChecker = null
        self._table: dict[LinkKind, LinkChecker] = {
            LinkKind.LOCAL: local,
            LinkKind.ANCHOR: anchor_checker,
            LinkKind.GITHUB: http,
            LinkKind.URL: http,
            LinkKind.MAILTO: null,
            LinkKind.TEL: null,
            LinkKind.WIKILINK: null,
            LinkKind.FOOTNOTE_URL: null,
            LinkKind.UNKNOWN: null,
        }
        _log.info(
            "чекеры готовы: local=%s anchors=%s http=%s (таймаут %d мс, семафор %d)",
            config.checks.local,
            config.checks.anchors,
            config.http.enabled,
            config.http.timeout_ms,
            config.http.workers,
        )

    def for_kind(self, kind: LinkKind) -> LinkChecker:
        """Чекер для категории; категории вне таблицы получают `NullChecker`."""
        return self._table.get(kind, self._null)

    @staticmethod
    def _http_checker(config: ScanConfig, notifier: Notifier) -> LinkChecker:
        """Единственный `HttpChecker` прогона — со своими семафором и кэшем."""
        return HttpChecker(
            timeout_ms=config.http.timeout_ms,
            workers=config.http.workers,
            user_agent=config.http.user_agent,
            method=config.http.method,
            cache_enabled=config.http.cache,
            notifier=notifier,
        )
