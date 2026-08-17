"""T-09 — обход дерева и дедупликация: `NestedRepoFinder`, `MarkdownFileFinder`, `ProcessedRegistry`.

Реальный `git` не нужен: `GitFileLister` — заглушка (duck typing, без наследования
контракта), дерево строится в `tmp_path`. Номера тестов — из таска T-09.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

import pytest

from core.mdscan.discovery.markdown_file_finder import MarkdownFileFinder
from core.mdscan.discovery.nested_repo_finder import NestedRepoFinder
from core.mdscan.discovery.processed_registry import ProcessedRegistry
from core.mdscan.models.repo_info import RepoInfo

EXTENSIONS: tuple[str, ...] = (".md", ".markdown")


class StubLister:
    """Заглушка `GitFileLister`: отдаёт заранее заданный список и считает вызовы."""

    def __init__(self, files: Sequence[Path] | None = None, error: Exception | None = None) -> None:
        self._files = list(files or ())
        self._error = error
        self.calls: list[tuple[Path, tuple[str, ...]]] = []

    def listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]:
        self.calls.append((root, tuple(extensions)))
        if self._error is not None:
            raise self._error
        return list(self._files)


def _write(path: Path, text: str = "# заголовок\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Синтетика: главный репозиторий с вложенным в `vendor/nested`.

    ```
    project/.git/                       главный (.git — каталог)
    project/README.md
    project/docs/install.md
    project/docs/api.markdown
    project/vendor/notes.md             рядом с nested, но НЕ в нём
    project/vendor/nested/.git/         вложенный репозиторий
    project/vendor/nested/README.md
    project/vendor/nested/docs/x.md     каталог `docs` — как и у главного
    project/.git/hooks/note.md          внутри `.git` — не файл проекта
    ```
    """
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    _write(project / ".git" / "hooks" / "note.md")
    _write(project / "README.md")
    _write(project / "docs" / "install.md")
    _write(project / "docs" / "api.markdown")
    _write(project / "vendor" / "notes.md")
    (project / "vendor" / "nested" / ".git").mkdir(parents=True)
    _write(project / "vendor" / "nested" / "README.md")
    _write(project / "vendor" / "nested" / "docs" / "x.md")
    return project


def _finder(include_nested: bool, *, lister: StubLister | None = None) -> MarkdownFileFinder:
    return MarkdownFileFinder(
        lister or StubLister(),
        EXTENSIONS,
        respect_gitignore=False,
        include_nested=include_nested,
    )


def _tasks(finder: MarkdownFileFinder, repos: Sequence[tuple[RepoInfo, list[Path]]]) -> list[tuple[Path, Path]]:
    """Прогон «обход → реестр»: возвращает уникальные пары `(repo_root, md_file)`."""
    registry = ProcessedRegistry()
    tasks: list[tuple[Path, Path]] = []
    for repo, nested_roots in repos:
        for md_file in finder.find(repo, nested_roots):
            key = (repo.root, md_file)
            if registry.add_if_absent(key):
                tasks.append((repo.root.resolve(), md_file.resolve()))
    return tasks


# --- 1. Файл вложенного репозитория попадает в задачи ровно один раз ------------------


def test_nested_file_queued_once_when_included(tree: Path) -> None:
    nested_root = tree / "vendor" / "nested"
    nested_file = (nested_root / "docs" / "x.md").resolve()
    finder = _finder(include_nested=True)

    tasks = _tasks(
        finder,
        [
            (RepoInfo(root=tree), [nested_root]),
            (RepoInfo(root=nested_root, is_nested=True), []),
        ],
    )

    assert [task for task in tasks if task[1] == nested_file] == [(nested_root.resolve(), nested_file)]


def test_nested_file_absent_for_main_repo_when_excluded(tree: Path) -> None:
    nested_file = (tree / "vendor" / "nested" / "docs" / "x.md").resolve()
    finder = _finder(include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), []))

    assert nested_file not in found
    assert not any((tree / "vendor" / "nested").resolve() in path.parents for path in found)


# --- 2. Файл рядом с вложенным репозиторием не теряется --------------------------------


def test_sibling_of_nested_repo_not_lost(tree: Path) -> None:
    finder = _finder(include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), []))

    assert (tree / "vendor" / "notes.md").resolve() in found


# --- 3. Каталог с совпадающим именем не выкидывается по имени ---------------------------


def test_same_named_directory_kept(tree: Path) -> None:
    """`docs` есть и у главного, и у вложенного: фильтр по префиксу, не по имени (D6.3)."""
    finder = _finder(include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), [tree / "vendor" / "nested"]))

    assert (tree / "docs" / "install.md").resolve() in found
    assert (tree / "docs" / "api.markdown").resolve() in found
    assert (tree / "vendor" / "nested" / "docs" / "x.md").resolve() not in found


# --- 4. Повторная подача того же репозитория не создаёт вторых задач ---------------------


def test_repeated_repository_gives_no_second_tasks(tree: Path) -> None:
    finder = _finder(include_nested=False)
    repo = RepoInfo(root=tree)

    once = _tasks(finder, [(repo, [])])
    twice = _tasks(finder, [(repo, []), (RepoInfo(root=tree / "docs" / ".."), [])])

    assert once
    assert len(twice) == len(once)


# --- 5. Symlink на просканированную папку не даёт дублей --------------------------------


def test_symlink_to_scanned_directory_gives_no_duplicates(tree: Path) -> None:
    link = tree / "docs_link"
    try:
        link.symlink_to(tree / "docs", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # Windows без прав на симлинки
        pytest.skip(f"симлинки недоступны: {type(exc).__name__}: {exc}")

    registry = ProcessedRegistry()
    direct = tree / "docs" / "install.md"
    through_link = link / "install.md"

    assert registry.add_if_absent((tree, direct)) is True
    assert registry.add_if_absent((tree, through_link)) is False

    found = list(_finder(include_nested=False).find(RepoInfo(root=tree), []))
    assert len(found) == len(set(found))


# --- 6. Оба расширения находятся, `.git/` пропускается -----------------------------------


def test_both_extensions_found_and_git_directory_skipped(tree: Path) -> None:
    finder = _finder(include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), []))

    assert (tree / "docs" / "install.md").resolve() in found
    assert (tree / "docs" / "api.markdown").resolve() in found
    assert (tree / ".git" / "hooks" / "note.md").resolve() not in found
    assert found == sorted(found), "порядок обхода должен быть детерминированным"


# --- 7. Реестр потокобезопасен ------------------------------------------------------------


def test_registry_is_thread_safe(tmp_path: Path) -> None:
    registry = ProcessedRegistry()
    repo_root = tmp_path / "repo"
    keys = [(repo_root, repo_root / f"f{i}.md") for i in range(1000)]
    accepted: list[list[bool]] = []
    lock = threading.Lock()

    def worker() -> None:
        mine = [registry.add_if_absent(key) for key in keys]
        with lock:
            accepted.append(mine)

    threads = [threading.Thread(target=worker, name=f"discover-{i}") for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)

    assert sum(sum(mine) for mine in accepted) == 1000


# --- NestedRepoFinder ---------------------------------------------------------------------


def test_nested_finder_returns_only_repositories_below_root(tree: Path) -> None:
    assert NestedRepoFinder().find(tree) == [(tree / "vendor" / "nested").resolve()]


def test_nested_finder_accepts_git_file_submodule(tmp_path: Path) -> None:
    """`.git` submodule — файл `gitdir: …`, а не каталог."""
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    module = project / "vendor" / "lib-a"
    module.mkdir(parents=True)
    (module / ".git").write_text("gitdir: ../../.git/modules/lib-a\n", encoding="utf-8")

    assert NestedRepoFinder().find(project) == [module.resolve()]


def test_nested_finder_does_not_descend_into_found_repository(tmp_path: Path) -> None:
    """Вложенные вложенного — его дело: обход внутрь найденного корня не идёт."""
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    inner = project / "vendor" / "lib-a"
    (inner / ".git").mkdir(parents=True)
    (inner / "third" / ".git").mkdir(parents=True)

    assert NestedRepoFinder().find(project) == [inner.resolve()]


# --- MarkdownFileFinder: источник кандидатов ----------------------------------------------


def test_git_lister_used_when_gitignore_respected(tree: Path) -> None:
    listed = [tree / "README.md", Path("docs/install.md"), tree / "docs" / "notes.txt"]
    lister = StubLister(listed)
    finder = MarkdownFileFinder(lister, EXTENSIONS, respect_gitignore=True, include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), []))

    assert lister.calls == [(tree.resolve(), EXTENSIONS)]
    assert found == sorted({(tree / "README.md").resolve(), (tree / "docs" / "install.md").resolve()})


def test_tree_walk_used_when_repository_outside_git(tmp_path: Path) -> None:
    """Каталог вне git → обход дерева, `GitFileLister` не зовётся (D5)."""
    plain = tmp_path / "plain"
    _write(plain / "a.md")
    lister = StubLister([plain / "never.md"])
    finder = MarkdownFileFinder(lister, EXTENSIONS, respect_gitignore=True, include_nested=False)

    found = list(finder.find(RepoInfo(root=plain), []))

    assert lister.calls == []
    assert found == [(plain / "a.md").resolve()]


def test_tree_walk_used_when_git_lister_fails(tree: Path) -> None:
    """Исключение чужой реализации не роняет обход: `ERROR` в лог и обход дерева (правило 11)."""
    lister = StubLister(error=RuntimeError("git сломался"))
    finder = MarkdownFileFinder(lister, EXTENSIONS, respect_gitignore=True, include_nested=False)

    found = list(finder.find(RepoInfo(root=tree), []))

    assert lister.calls
    assert (tree / "README.md").resolve() in found


def test_extensions_normalized(tree: Path) -> None:
    """`md` без точки и в верхнем регистре — тоже расширение."""
    lister = StubLister([tree / "README.md"])
    finder = MarkdownFileFinder(lister, ("MD",), respect_gitignore=True, include_nested=False)

    assert list(finder.find(RepoInfo(root=tree), [])) == [(tree / "README.md").resolve()]


def test_scope_limits_files_to_target_subdirectory(tmp_path: Path) -> None:
    """🔧 р5: цель — подкаталог репозитория (`RepoInfo.scope`) → файлы только из него, root не меняется."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "other").mkdir()
    (root / "docs" / "a.md").write_text("# a", encoding="utf-8")
    (root / "other" / "b.md").write_text("# b", encoding="utf-8")
    (root / "README.md").write_text("# r", encoding="utf-8")
    finder = MarkdownFileFinder(
        lister=StubLister(), extensions=(".md",), respect_gitignore=False, include_nested=False
    )
    repo = RepoInfo(root=root, scope=root / "docs")
    found = [p.relative_to(root.resolve()).as_posix() for p in finder.find(repo, [])]
    assert found == ["docs/a.md"]


# --- H-05 (G-D): резолв пути — один вызов ОС на каталог, а не на файл ---------------------


class _ResolveCounter:
    """Считает вызовы `Path.resolve` — `resolve()` идёт в ОС и на 500 файлах стоит 0.06 с."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls = 0
        original = Path.resolve

        def counted(path: Path, strict: bool = False) -> Path:
            self.calls += 1
            return original(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", counted)


def test_registry_does_not_resolve_every_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Инвариант реестра: пути приходят абсолютные, резолвится только каталог (H-05, G-D)."""
    repo_root = (tmp_path / "repo").resolve()
    files = [repo_root / "docs" / f"f{number}.md" for number in range(200)]
    registry = ProcessedRegistry()
    counter = _ResolveCounter(monkeypatch)

    accepted = [registry.add_if_absent((repo_root, md_file)) for md_file in files]

    assert all(accepted), "все 200 файлов новые — дублей нет"
    assert counter.calls == 2, f"ожидались 2 резолва (корень + каталог docs), было {counter.calls}"


def test_finder_resolves_directories_not_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Обход резолвит каталоги, а не файлы: 50 файлов в двух каталогах → единицы вызовов ОС."""
    root = tmp_path / "repo"
    for number in range(50):
        _write(root / ("docs" if number % 2 else "notes") / f"f{number}.md")
    finder = _finder(include_nested=False)
    counter = _ResolveCounter(monkeypatch)

    found = list(finder.find(RepoInfo(root=root), []))

    assert len(found) == 50, len(found)
    assert counter.calls <= 5, f"каталогов три, резолвов {counter.calls} — резолв ушёл на файлы"
