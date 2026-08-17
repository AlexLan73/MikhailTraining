"""Обёртка над GitPython — единственное место пакета, знающее про git.

Структурно реализует `discovery.GitFileLister` (владелец — T-09): метод
`listed_md(root, extensions)` совпадает по имени и сигнатуре; `discovery.*`
отсюда **не импортируется** (модули одной волны, спека разработки §2.5).
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# GitPython при импорте ищет бинарник git и без него падает `ImportError`.
# «quiet» откладывает проверку до первого вызова — тогда мы получаем
# `GitCommandNotFound` и превращаем его в понятный `GitUnavailableError`.
os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

import git  # noqa: E402  — только после GIT_PYTHON_REFRESH
from git.exc import (  # noqa: E402
    GitCommandNotFound,
    GitError,
    InvalidGitRepositoryError,
    NoSuchPathError,
)

from ..errors import GitUnavailableError, MdScanError

logger = logging.getLogger("core.mdscan.source")

#: Учётные данные внутри URL (`https://user:token@host/…`) — в лог не попадают.
_CREDENTIALS = re.compile(r"//[^/@]+@")

_NO_GIT = "в системе нет бинарника git (PATH); работать с репозиториями нечем"


def _masked(url: str) -> str:
    """URL без учётных данных: токен в лог писать нельзя."""
    return _CREDENTIALS.sub("//***@", url)


class GitAdapter:
    """Тонкий фасад над GitPython: корень, submodule'ы, список `.md`, remote, клон."""

    def root_of(self, path: Path) -> Path | None:
        """Ближайший вверх git-корень; путь вне git → `None` (это не ошибка)."""
        try:
            work_tree = git.Repo(path, search_parent_directories=True).working_tree_dir
        except GitCommandNotFound as exc:
            raise GitUnavailableError(_NO_GIT) from exc
        except (InvalidGitRepositoryError, NoSuchPathError):
            logger.debug("вне git: %s", path)
            return None
        if work_tree is None:
            logger.debug("bare-репозиторий без рабочего дерева: %s", path)
            return None
        return Path(str(work_tree)).resolve()

    def submodules(self, root: Path) -> list[Path]:
        """Абсолютные пути submodule'ов репозитория; нечитаемый `.gitmodules` → пусто."""
        try:
            repo = git.Repo(root)
            return [Path(str(sub.abspath)).resolve() for sub in repo.submodules]
        except GitCommandNotFound as exc:
            raise GitUnavailableError(_NO_GIT) from exc
        except (GitError, OSError, ValueError) as exc:
            logger.warning("submodule'ы не прочитаны для %s: %s", root, exc)
            return []

    def listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]:
        """Markdown-файлы репозитория по `git ls-files --cached --others --exclude-standard`.

        Отдаёт tracked **и** новые (untracked) файлы, минус игнорируемое `.gitignore`
        (инвариант 17, D7.4). Пути абсолютные и `resolve()`-нутые.
        """
        suffixes = tuple(ext.lower() for ext in extensions)
        try:
            listing = git.Repo(root).git.ls_files(
                "--cached", "--others", "--exclude-standard", "-z"
            )
        except GitCommandNotFound as exc:
            raise GitUnavailableError(_NO_GIT) from exc
        except (GitError, OSError) as exc:
            # H-08 (Д-H08-2): не глотать — пустой список неотличим от «нет .md»; `MarkdownFileFinder`
            # ловит исключение сам и откатывается на обход дерева (`rglob`), файлы не теряются.
            logger.warning("git ls-files не выполнен для %s (%s: %s) — обход дерева", root, type(exc).__name__, exc)
            raise
        base = Path(root).resolve()
        return [
            (base / rel).resolve()
            for rel in str(listing).split("\0")
            if rel and rel.lower().endswith(suffixes)
        ]

    def remote_url(self, root: Path) -> str:
        """Адрес `origin` (или первого remote); remote'ов нет → пустая строка."""
        try:
            remotes = {remote.name: remote for remote in git.Repo(root).remotes}
        except GitCommandNotFound as exc:
            raise GitUnavailableError(_NO_GIT) from exc
        except (GitError, OSError) as exc:
            logger.warning("remote не прочитан для %s: %s", root, exc)
            return ""
        chosen = remotes.get("origin") or next(iter(remotes.values()), None)
        return "" if chosen is None else str(chosen.url)

    def clone(self, url: str, dst: Path, depth: int) -> Path:
        """Склонировать репозиторий в `dst` (`--depth <depth>`, 0 → полный клон)."""
        target = Path(dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        logger.info("клонирую %s → %s (depth=%s)", _masked(url), target, depth)
        options: dict[str, Any] = {"depth": depth} if depth > 0 else {}
        try:
            git.Repo.clone_from(url, str(target), **options)
        except GitCommandNotFound as exc:
            raise GitUnavailableError(_NO_GIT) from exc
        except (GitError, OSError) as exc:
            raise MdScanError(f"не удалось склонировать {_masked(url)}: {exc}") from exc
        return target.resolve()
