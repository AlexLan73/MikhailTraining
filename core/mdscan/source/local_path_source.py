"""Локальный каталог как источник репозиториев."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

from ..models.repo_info import RepoInfo
from .git_adapter import GitAdapter

logger = logging.getLogger("core.mdscan.source")

#: `git@host:org/repo(.git)` — SSH-форма адреса, для отчёта нужна web-форма (D6.4).
_SCP_LIKE = re.compile(r"^(?:ssh://)?(?:[^@/]+@)?([^:/]+)[:/](.+?)(?:\.git)?/?$")
#: `https://user:token@host/org/repo` — учётные данные в отчёт не попадают.
_CREDENTIALS = re.compile(r"//[^/@]+@")


def _web_url(remote_url: str) -> str:
    """Адрес репозитория для отчёта: `git@github.com:org/repo.git` → `https://github.com/org/repo`."""
    if not remote_url:
        return ""
    if remote_url.startswith(("http://", "https://")):
        clean = _CREDENTIALS.sub("//", remote_url).rstrip("/")
        return clean[: -len(".git")] if clean.endswith(".git") else clean
    match = _SCP_LIKE.match(remote_url)
    return f"https://{match.group(1)}/{match.group(2)}" if match else ""


class LocalPathSource:
    """Один каталог → один `RepoInfo`; вложенные репозитории ищет T-09, не источник."""

    def __init__(self, path: Path, git: GitAdapter) -> None:
        self._path = Path(path)
        self._git = git

    def repositories(self) -> Iterable[RepoInfo]:
        """Один репозиторий; каталог вне git → работаем как с папкой + `WARNING` (D5)."""
        root = self._git.root_of(self._path)
        if root is None:
            logger.warning(
                "каталог вне git, обходим как обычную папку (not-a-repo): %s", self._path
            )
            return [RepoInfo(root=self._path.resolve())]
        remote = self._git.remote_url(root)
        target = self._path.resolve()
        scope = target if target != Path(root).resolve() else None  # 🔧 р5: подкаталог репозитория
        info = RepoInfo(root=root, remote_url=remote, web_url=_web_url(remote), scope=scope)
        logger.info("репозиторий: %s (web=%s)", info.root, info.web_url or "-")
        return [info]

    def cleanup(self) -> None:
        """Локальный источник ничего не создавал — удалять нечего (Null-поведение)."""
        logger.debug("cleanup локального источника %s: ничего не создано", self._path)
