"""Поиск вложенных git-репозиториев внутри дерева (часть 1, D6.2)."""

from __future__ import annotations

import logging
import os
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
        """Список корней вложенных репозиториев (абсолютные, резолвленные, отсортированы).

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
            current = stack.pop()
            children, has_git = self._listed(current)
            if has_git and current != base:
                logger.debug("вложенный репозиторий: %s", current)
                found.append(current)
                continue
            stack.extend(children)
        found.sort()
        return found

    def _listed(self, directory: Path) -> tuple[list[Path], bool]:
        """Подкаталоги (без `.git` и без симлинков) и признак «здесь есть `.git`».

        Одно обращение к ОС на каталог (H-05): `os.scandir` отдаёт тип записи вместе со
        списком, поэтому проверка «каталог и не симлинк» лишних вызовов не стоит, а наличие
        `.git` видно из того же листинга — отдельный `exists()` на каждый подкаталог не нужен.
        Нечитаемый каталог → `WARNING` и пропуск (правило 11).
        """
        children: list[Path] = []
        has_git = False
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.name == GIT_ENTRY:
                        has_git = True
                    elif self._is_plain_dir(entry):
                        children.append(Path(entry.path))
        except OSError as exc:
            logger.warning(
                "каталог не прочитан, пропущен: %s (%s: %s)", directory, type(exc).__name__, exc
            )
        return children, has_git

    @staticmethod
    def _is_plain_dir(entry: os.DirEntry[str]) -> bool:
        """`True` — обычный каталог (не симлинк). Ошибка доступа → `False` + `WARNING`."""
        try:
            return entry.is_dir(follow_symlinks=False)
        except OSError as exc:
            logger.warning("путь не опрошен: %s (%s: %s)", entry.path, type(exc).__name__, exc)
            return False
