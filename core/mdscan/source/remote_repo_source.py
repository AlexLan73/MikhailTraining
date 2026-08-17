"""Один удалённый репозиторий: клон `--depth 1`, дальше — как локальный."""

from __future__ import annotations

import logging
import shutil
import stat
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from ..errors import GitUnavailableError, MdScanError
from ..models.repo_info import RepoInfo
from .git_adapter import GitAdapter
from .local_path_source import LocalPathSource

logger = logging.getLogger("core.mdscan.source")


def _clone_name(url: str) -> str:
    """Имя каталога клона из адреса: `git@github.com:org/radar.git` → `org__radar`.

    🔧 р5: в имя входит и владелец — иначе `org1/repo` и `org2/repo` легли бы в один каталог
    и второй репозиторий был бы просканирован как первый.
    """
    trimmed = url.rstrip("/")
    if trimmed.endswith(".git"):
        trimmed = trimmed[: -len(".git")]
    # ssh-форма `git@host:org/repo` → после двоеточия; url-форма → после host
    path_part = trimmed.rsplit(":", 1)[-1] if "://" not in trimmed else trimmed.split("://", 1)[1].split("/", 1)[-1]
    parts = [part for part in path_part.split("/") if part]
    if not parts:
        return "repo"
    return "__".join(parts[-2:])


def _rmtree(path: Path) -> None:
    """`shutil.rmtree` с обработчиком read-only: `onexc` есть с 3.12, на 3.11 — `onerror`."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_drop_readonly)
    else:  # pragma: no cover — ветка для Python 3.11 (requires-python >= 3.11)
        shutil.rmtree(path, onerror=lambda fn, p, info: _drop_readonly(fn, p, info[1]))


def _drop_readonly(remove: Callable[[str], object], path: str, exc: BaseException) -> None:
    """Windows: объекты в `.git` только для чтения — снимаем флаг и повторяем удаление."""
    logger.debug("снимаю read-only и повторяю удаление: %s (%s)", path, exc)
    Path(path).chmod(stat.S_IWRITE)
    remove(path)


class RemoteRepoSource:
    """Клонирует репозиторий в `source.clone_dir` и отдаёт его как локальный."""

    def __init__(self, url: str, clone_dir: Path, depth: int, keep_clones: bool, git: GitAdapter) -> None:
        self._url = url
        self._clone_dir = Path(clone_dir)
        self._depth = depth
        self._keep_clones = keep_clones
        self._git = git
        self._clone_path: Path | None = None

    def repositories(self) -> Iterable[RepoInfo]:
        """Клон (или переиспользование существующего) → один `RepoInfo`."""
        target = self._clone_dir / _clone_name(self._url)
        try:
            path = self._reuse_or_clone(target)
        except GitUnavailableError:
            raise
        except MdScanError as exc:
            # 🔧 H-13: клон мог оборваться на середине — каталог запоминаем, иначе
            # `cleanup()` оставит мусор в `source.clone_dir` (частичный клон).
            self._clone_path = target if target.exists() else None
            logger.error("репозиторий пропущен: %s", exc, exc_info=True)
            return []
        self._clone_path = path
        return LocalPathSource(path, self._git).repositories()

    def cleanup(self) -> None:
        """Удалить клон при `keep_clones: false`; ошибка удаления не роняет прогон."""
        path = self._clone_path
        if path is None or not path.exists():
            return
        if self._keep_clones:
            logger.info("клон оставлен (keep_clones: true): %s", path)
            return
        try:
            _rmtree(path)
            logger.info("клон удалён: %s", path)
        except OSError as exc:
            logger.error("клон не удалён: %s (%s)", path, exc, exc_info=True)

    def _reuse_or_clone(self, target: Path) -> Path:
        """Каталог клона уже есть → берём его, иначе клонируем."""
        if target.exists():
            logger.info("клон уже существует, переиспользую: %s", target)
            return target.resolve()
        return self._git.clone(self._url, target, self._depth)
