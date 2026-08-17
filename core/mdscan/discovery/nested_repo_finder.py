"""Поиск вложенных git-репозиториев внутри дерева (часть 1, D6.2)."""

from __future__ import annotations

import logging
from pathlib import Path

#: Логгер пакета обхода (правило 11): шаги конвейера — `DEBUG`/`INFO`, проблемы — `WARNING`.
logger = logging.getLogger("core.mdscan.discovery")

#: Признак корня git-репозитория: каталог (обычный клон) **или** файл (submodule/worktree).
GIT_ENTRY = ".git"


class NestedRepoFinder:
    """Ищет каталоги с собственным `.git` **ниже** заданного корня.

    Нужен для правила ближайшего корня (D6.2): файл принадлежит ближайшему вверх
    git-корню, поэтому главный репозиторий обязан исключить найденные поддеревья.

    Работает **только по файловой системе**, без вызовов git: `.git` — это либо
    каталог (клон внутри рабочей папки), либо файл `gitdir: …` (submodule/worktree).
    """

    def find(self, root: Path) -> list[Path]:
        """Список корней вложенных репозиториев (абсолютные, `resolve()`, отсортированы).

        Сам `root` в результат не входит, даже если он git-репозиторий. Внутрь
        найденного вложенного репозитория обход не спускается — его собственные
        вложенные репозитории найдёт он сам, когда станет корнем обхода.
        Каталог `.git` любого уровня не обходится. Симлинки на каталоги
        пропускаются: иначе циклическая ссылка зациклила бы обход.
        """
        base = Path(root).resolve()
        found: list[Path] = []
        stack: list[Path] = [base]
        while stack:
            for child in self._subdirectories(stack.pop()):
                if self._is_repo_root(child):
                    logger.debug("вложенный репозиторий: %s", child)
                    found.append(child)
                    continue
                stack.append(child)
        found.sort()
        return found

    def _subdirectories(self, directory: Path) -> list[Path]:
        """Подкаталоги (без `.git` и без симлинков); нечитаемый каталог → `WARNING`."""
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            logger.warning(
                "каталог не прочитан, пропущен: %s (%s: %s)", directory, type(exc).__name__, exc
            )
            return []
        return [entry for entry in entries if entry.name != GIT_ENTRY and self._is_plain_dir(entry)]

    def _is_plain_dir(self, path: Path) -> bool:
        """`True` — обычный каталог (не симлинк). Ошибка доступа → `False` + `WARNING`."""
        try:
            return path.is_dir() and not path.is_symlink()
        except OSError as exc:
            logger.warning("путь не опрошен: %s (%s: %s)", path, type(exc).__name__, exc)
            return False

    def _is_repo_root(self, directory: Path) -> bool:
        """`True`, если внутри есть `.git` — каталог или файл (submodule)."""
        try:
            return (directory / GIT_ENTRY).exists()
        except OSError as exc:
            logger.warning("`.git` не опрошен: %s (%s: %s)", directory, type(exc).__name__, exc)
            return False
