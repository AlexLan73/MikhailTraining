"""Поиск `.md`-файлов одного репозитория с учётом правила ближайшего корня (D6.2)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from core.mdscan.discovery.git_file_lister import GitFileLister
from core.mdscan.discovery.nested_repo_finder import GIT_ENTRY, NestedRepoFinder
from core.mdscan.discovery.resolved_path_cache import ResolvedPathCache
from core.mdscan.models.repo_info import RepoInfo

logger = logging.getLogger("core.mdscan.discovery")


class MarkdownFileFinder:
    """Отдаёт файлы, принадлежащие **этому** репозиторию, и ничьи больше.

    Два источника кандидатов (D7.4):

    - `respect_gitignore=True` и репозиторий «в git» → `GitFileLister.listed_md`
      (`git ls-files --cached --others --exclude-standard`: отслеживаемые + новые,
      минус игнорируемое);
    - иначе → обход файловой системы `rglob` по `extensions` с пропуском `.git/`.

    **«В git»** здесь = существует `repo.root/.git` **или** заполнен `repo.remote_url`
    (клон, чей корень мы уже знаем). Фиксирую формулировку: другого способа узнать это
    без обращения к `source.*` у обхода нет.

    Затем работает правило ближайшего корня: файл, лежащий внутри вложенного
    репозитория, главному не отдаётся. Фильтр — **по префиксу пути**
    (`Path.is_relative_to` после резолва), не по имени каталога (D6.3).

    Резолв идёт через `ResolvedPathCache` — один вызов ОС на каталог, а не на файл
    (H-05, гипотеза G-D). Наружу отдаются **абсолютные** пути: на этом инварианте
    стоит `ProcessedRegistry`, который повторно их не резолвит.

    `include_nested` управляет **самостоятельным** поиском вложенных корней: при
    `False` (`scan.include_nested_repos: false`) и пустом `nested_roots` обход сам
    зовёт `NestedRepoFinder`, чтобы чужие файлы не достались главному репозиторию.
    Явно переданный `nested_roots` исключается **всегда**: раз оркестратор отдал эти
    корни, их файлы разбирает вложенный репозиторий как отдельный `RepoInfo`
    (инвариант 6: каждый `.md` попадает в задачи ровно один раз).
    """

    def __init__(
        self,
        lister: GitFileLister,
        extensions: Sequence[str],
        respect_gitignore: bool,
        include_nested: bool,
    ) -> None:
        self._lister = lister
        self._extensions: tuple[str, ...] = tuple(self._normalized(ext) for ext in extensions)
        self._respect_gitignore = bool(respect_gitignore)
        self._include_nested = bool(include_nested)
        self._nested_finder = NestedRepoFinder()
        self._paths = ResolvedPathCache()

    def find(self, repo: RepoInfo, nested_roots: list[Path]) -> Iterable[Path]:
        """Уникальные абсолютные пути `.md` этого репозитория, отсортированные.

        Порядок детерминирован (сортировка) — два прогона дают один и тот же отчёт
        (инвариант 9).
        """
        root = self._paths.directory(Path(repo.root))
        scope = self._paths.directory(Path(repo.scope)) if repo.scope is not None else None
        excluded = self._excluded_roots(scope or root, nested_roots)  # 🔧 р5: обход стадии 1 — только в scope
        files: list[Path] = []
        seen: set[Path] = set()
        for path in self._candidates(repo, root, scope):
            if path in seen:
                continue
            seen.add(path)
            if scope is not None and not path.is_relative_to(scope):
                continue  # 🔧 р5: цель — подкаталог репозитория, остальное не наше
            if any(path.is_relative_to(alien) for alien in excluded):
                logger.debug("файл вложенного репозитория пропущен: %s", path)
                continue
            logger.debug("файл найден: %s", path)
            files.append(path)
        files.sort()
        logger.info("репозиторий обработан: %s, файлов %d", root, len(files))
        return tuple(files)

    def _candidates(self, repo: RepoInfo, root: Path, scope: Path | None = None) -> list[Path]:
        """Кандидаты до фильтра: список git или обход файловой системы (в пределах `scope`)."""
        if self._respect_gitignore and self._under_git(repo, root):
            try:
                listed = self._lister.listed_md(root, self._extensions)
            except Exception as exc:  # noqa: BLE001 — сузить нельзя: реализация чужая
                logger.exception(
                    "git не отдал список файлов, перехожу на обход дерева: %s (%s)",
                    root,
                    type(exc).__name__,
                )
            else:
                return self._resolved(listed, root)
        return self._scan_tree(scope or root)

    def _under_git(self, repo: RepoInfo, root: Path) -> bool:
        """Репозиторий «в git»: есть `.git` или известен `remote_url` (см. докстринг класса)."""
        try:
            return (root / GIT_ENTRY).exists() or bool(repo.remote_url)
        except OSError as exc:
            logger.warning("`.git` не опрошен: %s (%s: %s)", root, type(exc).__name__, exc)
            return bool(repo.remote_url)

    def _resolved(self, listed: Sequence[Path], root: Path) -> list[Path]:
        """Пути от git → абсолютные, только с нашими расширениями."""
        files: list[Path] = []
        for raw in listed:
            path = Path(raw)
            absolute = self._paths.file(path if path.is_absolute() else root / path)
            if self._has_extension(absolute):
                files.append(absolute)
        return files

    def _scan_tree(self, root: Path) -> list[Path]:
        """Обход `rglob` по расширениям; всё, что лежит внутри `.git/`, пропускается."""
        files: list[Path] = []
        for ext in self._extensions:
            try:
                for path in root.rglob(f"*{ext}"):
                    if GIT_ENTRY in path.parts or not path.is_file():
                        continue
                    files.append(self._paths.file(path))
            except OSError as exc:
                logger.warning(
                    "обход дерева прерван: %s (%s: %s)", root, type(exc).__name__, exc
                )
        return files

    def _excluded_roots(self, root: Path, nested_roots: Sequence[Path] | None) -> tuple[Path, ...]:
        """Корни, чьи файлы главному не принадлежат (сам `root` из набора исключается)."""
        alien = {self._paths.directory(Path(nested)) for nested in (nested_roots or ())}
        if not alien and not self._include_nested:
            alien = set(self._nested_finder.find(root))
        alien.discard(root)
        return tuple(sorted(alien))

    def _has_extension(self, path: Path) -> bool:
        return path.suffix.lower() in self._extensions

    @staticmethod
    def _normalized(extension: str) -> str:
        """`md` и `.MD` → `.md`: конфиг пишет человек, регистр и точка — на его усмотрение."""
        text = extension.strip().lower()
        return text if text.startswith(".") else f".{text}"
