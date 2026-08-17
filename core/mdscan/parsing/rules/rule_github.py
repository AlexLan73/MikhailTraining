"""Правило 6 цепочки: адрес на GitHub. **Строго до `HttpRule`** (D8.2)."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink

logger = logging.getLogger("core.mdscan.parsing")


class GithubRule:
    """`https://github.com/org/repo`, `git@github.com:org/repo.git` и родня.

    Категория отдельная от `URL` не ради проверки (её делает тот же `HttpChecker`),
    а ради отчёта: GitHub-ссылки — своя секция (D8.1). Если правило переставить
    после `HttpRule`, все они молча станут `URL` — на это есть отдельный тест.

    Сверяем **хост**, а не подстроку: `https://notgithub.com/x` — не GitHub.
    """

    _HOSTS = frozenset(
        {"github.com", "www.github.com", "gist.github.com", "raw.githubusercontent.com"}
    )
    _SSH_PREFIXES = ("git@github.com:", "ssh://git@github.com/")
    _WEB_SCHEMES = ("http://", "https://")

    def matches(self, link: MdLink) -> bool:
        target = link.target.strip()
        lowered = target.lower()
        if lowered.startswith(self._SSH_PREFIXES):
            return True
        if not lowered.startswith(self._WEB_SCHEMES):
            return False
        return self._host(target) in self._HOSTS

    @property
    def kind(self) -> LinkKind:
        return LinkKind.GITHUB

    @staticmethod
    def _host(target: str) -> str:
        """Хост адреса в нижнем регистре; неразбираемый адрес → пустая строка."""
        try:
            return (urlsplit(target).hostname or "").lower()
        except ValueError:
            logger.debug("адрес не разбирается как URL: %s", target)
            return ""
