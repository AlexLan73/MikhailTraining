"""Живые HTTP-исходы (этап 2, таск H-03): `OK` · `BROKEN` · `TIMEOUT` на реальной сети.

Эти тесты — **единственное** место в наборе, где разрешён выход в интернет (§3.2 dev/test-спеки).
Поэтому каждый помечен `@pytest.mark.network` (маркер зарегистрирован в `pyproject.toml`) и
**сам** уходит в `skip`, если не выставлена переменная окружения `MDSCAN_NETWORK=1`:

```bash
pytest tests/hw01 -q                             # живые тесты — skipped, интернет не нужен
MDSCAN_NETWORK=1 pytest -m network tests/hw01 -q # гоняем по живым адресам
```

Закрывают требования T6 (проверка внешних ссылок), T11 (таймаут) и T12 (404 · DNS · timeout
различимы) раздела 0 спеки архитектуры — на живой сети, а не на `127.0.0.1`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.mdscan.checking.checker_factory import CheckerFactory
from core.mdscan.checking.http_checker import HttpChecker
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.models.md_link import MdLink

#: Быстрый и стабильный адрес: страница-заглушка IANA, живёт годами.
_LIVE_URL = "https://example.com/"
#: Страницы нет, но домен жив и отвечает — ожидается `BROKEN` с кодом 404.
_MISSING_URL = "https://github.com/AlexLan73/no-such-repo-xyz-h03"
#: Зона `.invalid` зарезервирована RFC 2606: DNS обязан не разрешать её никогда.
_UNKNOWN_HOST_URL = "https://no-such-domain-mdscan-h03-2026.invalid/"


class _SilentNotifier:
    """Заглушка `Notifier` (duck typing): зона 2 в тестах не нужна."""

    def show(self, text: str) -> None:
        """Строку прогресса молча выбрасываем."""


def _require_network() -> None:
    """Без `MDSCAN_NETWORK=1` тест пропускается — основной набор не ходит в интернет."""
    if not os.environ.get("MDSCAN_NETWORK"):
        pytest.skip("MDSCAN_NETWORK=1 не выставлен")


def _checker(timeout_ms: int = 5000) -> HttpChecker:
    """`HttpChecker` с боевыми умолчаниями и заданным таймаутом."""
    return HttpChecker(
        timeout_ms=timeout_ms,
        workers=1,
        user_agent="mdscan/0.1",
        method="head_then_get",
        cache_enabled=True,
        notifier=_SilentNotifier(),
    )


def _link(target: str, kind: LinkKind) -> MdLink:
    """Ссылка в состоянии «извлечена и классифицирована», статус ещё не проверен."""
    return MdLink(target=target, origin=LinkOrigin.INLINE, line=1, kind=kind)


@pytest.mark.network
def test_live_site_answers_ok(tmp_path: Path) -> None:
    """T6: живой быстрый адрес → `OK` и код 2xx/3xx в `http_code`."""
    _require_network()
    link = _link(_LIVE_URL, LinkKind.URL)
    _checker().check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.OK
    assert 200 <= link.http_code < 400


@pytest.mark.network
def test_missing_page_is_broken_with_code(tmp_path: Path) -> None:
    """T7/T12: страницы нет на живом домене → `BROKEN` с кодом 404; GitHub идёт в `HttpChecker`."""
    _require_network()
    draft = ConfigDraft.from_defaults()
    draft.assign("http.timeout_ms", 5000, SOURCE_CMDLINE)
    factory = CheckerFactory(ScanConfig.from_draft(draft), _StubHeadings(), _SilentNotifier())
    link = _link(_MISSING_URL, LinkKind.GITHUB)
    factory.for_kind(LinkKind.GITHUB).check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.BROKEN
    assert link.http_code == 404
    assert "404" in link.detail


@pytest.mark.network
def test_unknown_domain_is_broken_without_code(tmp_path: Path) -> None:
    """T12: домена не существует (ошибка DNS) → `BROKEN`, кода нет, причина в `detail`.

    Именно `BROKEN`, а не `TIMEOUT`: сервер не «молчит», его вообще нет — путать эти
    исходы нельзя, иначе непонятно, поднимать таймаут или чинить ссылку.
    """
    _require_network()
    link = _link(_UNKNOWN_HOST_URL, LinkKind.URL)
    _checker().check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.BROKEN
    assert link.http_code == 0
    assert link.detail


@pytest.mark.network
def test_tiny_timeout_gives_timeout_not_broken(tmp_path: Path) -> None:
    """T11: живой адрес при `http.timeout_ms: 1` → `TIMEOUT`, а не `BROKEN`; прогон не виснет."""
    _require_network()
    link = _link(_LIVE_URL, LinkKind.URL)
    _checker(timeout_ms=1).check(link, tmp_path / "doc.md")
    assert link.status is CheckStatus.TIMEOUT
    assert link.http_code == 0
    assert "мс" in link.detail


class _StubHeadings:
    """Заглушка `HeadingSource`: фабрике она нужна для якорей, а тут якорей нет."""

    def headings(self, text: str) -> tuple[str, ...]:
        """Заголовков не отдаём — HTTP-ветка их не спрашивает."""
        return ()
