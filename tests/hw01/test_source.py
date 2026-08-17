"""T-08 — источники репозиториев: `GitAdapter`, три `RepositorySource`, `SourceFactory`.

Реальной сети здесь нет: GitHub раскрывается заглушками `run_gh` / `http_get`,
клонирование — двойником `GitAdapter`. Настоящий git используется только на
локальных репозиториях, созданных в `tmp_path`; нет бинарника git → тесты
помечаются `skip` (тест 5 из ТЗ).
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import stat
import subprocess
import threading
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft
from core.mdscan.config.scan_config import ScanConfig, SourceConfig
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.errors import GitHubDiscoveryError, GitUnavailableError, MdScanError
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.source.git_adapter import GitAdapter
from core.mdscan.source.github_org_source import GitHubOrgSource
from core.mdscan.source.local_path_source import LocalPathSource
from core.mdscan.source.remote_repo_source import RemoteRepoSource
from core.mdscan.source.source_factory import SourceFactory

SOURCE_LOGGER = "core.mdscan.source"

#: Потолок ожидания в тестах с потоками: `join`/`wait` без таймаута вешают набор.
WAIT_SEC = 5.0

#: Тест 5 ТЗ: без бинарника git локальные репозитории не создать — пропускаем.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git не найден в PATH — тесты на локальных репозиториях пропущены",
)


# --------------------------------------------------------------------------- вспомогательное


def _git(*args: str, cwd: Path) -> None:
    """Выполнить git с фиксированным автором (в CI глобального `user.name` может не быть)."""
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _init_repo(root: Path) -> Path:
    """Пустой репозиторий с одним коммитом."""
    root.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", ".", cwd=root)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git("add", "README.md", cwd=root)
    _git("commit", "-qm", "init", cwd=root)
    return root


def _source_config(**overrides: Any) -> SourceConfig:
    """Секция `source` из defaults с точечными переопределениями."""
    draft = ConfigDraft.from_defaults()
    for field, value in overrides.items():
        draft.assign(f"source.{field}", value, SOURCE_CMDLINE)
    return ScanConfig.from_draft(draft).source


class FakeGit:
    """Двойник `GitAdapter` (duck typing): клон создаёт каталог, в сеть не ходит."""

    def __init__(self) -> None:
        self.clone_calls: list[tuple[str, Path, int]] = []

    def root_of(self, path: Path) -> Path | None:
        return Path(path).resolve()

    def submodules(self, root: Path) -> list[Path]:
        return []

    def listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]:
        return []

    def remote_url(self, root: Path) -> str:
        return ""

    def clone(self, url: str, dst: Path, depth: int) -> Path:
        target = Path(dst)
        self.clone_calls.append((url, target, depth))
        (target / ".git").mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text("# clone\n", encoding="utf-8")
        return target.resolve()


def _gh_repo(name: str, *, fork: bool = False, archived: bool = False, visibility: str = "PUBLIC") -> dict[str, Any]:
    """Запись в формате `gh repo list --json name,url,sshUrl,isFork,isArchived,visibility`."""
    return {
        "name": name,
        "url": f"https://github.com/org/{name}",
        "sshUrl": f"git@github.com:org/{name}.git",
        "isFork": fork,
        "isArchived": archived,
        "visibility": visibility,
    }


def _api_repo(name: str) -> dict[str, Any]:
    """Запись в формате REST API `GET /orgs/{org}/repos`."""
    return {
        "name": name,
        "html_url": f"https://github.com/org/{name}",
        "ssh_url": f"git@github.com:org/{name}.git",
        "clone_url": f"https://github.com/org/{name}.git",
        "fork": False,
        "archived": False,
        "private": False,
        "visibility": "public",
    }


def _fail_gh(args: Sequence[str]) -> str:
    """Заглушка `run_gh`, которой в тесте быть не должно."""
    raise AssertionError(f"gh не должен вызываться: {list(args)}")


def _fail_http(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
    """Заглушка `http_get`, которой в тесте быть не должно."""
    raise AssertionError(f"REST API не должен вызываться: {url}")


# --------------------------------------------------------------------------- 1. каталог вне git


def test_directory_outside_git_gives_single_repo(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Тест 1: каталог вне git → один `RepoInfo` и предупреждение в логе."""
    plain = tmp_path / "plain"
    plain.mkdir()
    source = LocalPathSource(plain, GitAdapter())

    with caplog.at_level(logging.WARNING, logger=SOURCE_LOGGER):
        repos = list(source.repositories())

    assert len(repos) == 1
    assert repos[0].root == plain.resolve()
    assert repos[0].remote_url == "" and repos[0].web_url == ""
    assert repos[0].is_nested is False
    assert any("вне git" in record.message for record in caplog.records)
    source.cleanup()  # локальный источник ничего не удаляет и не падает


# --------------------------------------------------------------------------- 2. локальный репозиторий


@requires_git
def test_local_repository_root_detected(tmp_path: Path) -> None:
    """Тест 2: корень определяется по вложенному пути, `web_url` — из remote (D6.4)."""
    root = _init_repo(tmp_path / "project")
    (root / "docs").mkdir()
    _git("remote", "add", "origin", "git@github.com:org/project.git", cwd=root)

    repos = list(LocalPathSource(root / "docs", GitAdapter()).repositories())

    assert [info.root for info in repos] == [root.resolve()]
    assert repos[0].remote_url == "git@github.com:org/project.git"
    assert repos[0].web_url == "https://github.com/org/project"


# --------------------------------------------------------------------------- 3. submodule и вложенный клон


@requires_git
def test_submodule_file_and_nested_clone_are_recognised(tmp_path: Path) -> None:
    """Тест 3: `.git` как файл (submodule) и как каталог (клон) дают свои корни."""
    parent = _init_repo(tmp_path / "project")

    nested = _init_repo(parent / "vendor" / "nested")           # .git — каталог
    submodule = _init_repo(parent / "vendor" / "lib-a")         # станет .git-файлом
    modules = parent / ".git" / "modules"
    modules.mkdir(parents=True, exist_ok=True)
    shutil.move(str(submodule / ".git"), str(modules / "lib-a"))
    (submodule / ".git").write_text("gitdir: ../../.git/modules/lib-a\n", encoding="utf-8")
    _git("config", "core.worktree", "../../../vendor/lib-a", cwd=modules / "lib-a")
    (submodule / "doc").mkdir()

    adapter = GitAdapter()

    assert adapter.root_of(parent / "README.md") == parent.resolve()
    assert adapter.root_of(nested / "README.md") == nested.resolve()
    assert adapter.root_of(submodule / "doc") == submodule.resolve()


# --------------------------------------------------------------------------- 4. listed_md


@requires_git
def test_listed_md_keeps_untracked_and_skips_ignored(tmp_path: Path) -> None:
    """Тест 4: игнорируемое не возвращается, новый незакоммиченный `.md` — возвращается."""
    root = _init_repo(tmp_path / "project")
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("a\n", encoding="utf-8")
    (root / "docs" / "guide.markdown").write_text("g\n", encoding="utf-8")
    (root / "docs" / "note.txt").write_text("t\n", encoding="utf-8")
    (root / "ignored").mkdir()
    (root / "ignored" / "skip.md").write_text("s\n", encoding="utf-8")
    _git("add", ".gitignore", "docs/a.md", cwd=root)
    _git("commit", "-qm", "docs", cwd=root)
    (root / "docs" / "new.md").write_text("new\n", encoding="utf-8")  # untracked

    found = set(GitAdapter().listed_md(root, [".md", ".markdown"]))

    assert (root / "docs" / "a.md").resolve() in found
    assert (root / "docs" / "new.md").resolve() in found        # tracked + untracked (D7.4)
    assert (root / "README.md").resolve() in found
    assert (root / "docs" / "guide.markdown").resolve() in found
    assert (root / "ignored" / "skip.md").resolve() not in found
    assert (root / "docs" / "note.txt").resolve() not in found


# --------------------------------------------------------------------------- 5. нет бинарника git


def test_clone_without_git_binary_raises_git_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Тест 5: отсутствие git (`GitCommandNotFound`) → `GitUnavailableError`, а не GitPython-ошибка."""
    from git.exc import GitCommandNotFound  # локальный импорт: только для эмуляции отсутствия git

    def _no_git(*args: object, **kwargs: object) -> None:
        raise GitCommandNotFound("git", "не найден")

    monkeypatch.setattr("git.Repo.clone_from", _no_git)

    with pytest.raises(GitUnavailableError, match="git"):
        GitAdapter().clone("git@github.com:org/repo.git", tmp_path / "clone", 1)


# --------------------------------------------------------------------------- 6. gh: список и фильтры


@pytest.mark.parametrize(
    ("config_overrides", "expected"),
    [
        pytest.param({}, ["alpha", "beta"], id="по умолчанию: без форков и архивов"),
        pytest.param({"include_forks": True}, ["alpha", "beta", "forked"], id="include_forks"),
        pytest.param({"include_archived": True}, ["alpha", "beta", "old"], id="include_archived"),
        pytest.param({"visibility": "private"}, ["beta"], id="visibility=private"),
        pytest.param({"visibility": "public"}, ["alpha"], id="visibility=public"),
    ],
)
def test_gh_discovery_applies_filters(
    tmp_path: Path, config_overrides: dict[str, Any], expected: list[str]
) -> None:
    """Тест 6: `gh` отдаёт список, фильтры visibility/forks/archived применяются."""
    payload = [
        _gh_repo("alpha"),
        _gh_repo("beta", visibility="PRIVATE"),
        _gh_repo("forked", fork=True),
        _gh_repo("old", archived=True),
    ]
    calls: list[Sequence[str]] = []

    def run_gh(args: Sequence[str]) -> str:
        calls.append(list(args))
        return json.dumps(payload)

    fake_git = FakeGit()
    config = _source_config(clone_dir=str(tmp_path / "clones"), **config_overrides)
    source = GitHubOrgSource("https://github.com/org", config, run_gh, _fail_http, fake_git)

    repos = list(source.repositories())

    assert [Path(info.root).name for info in repos] == [f"org__{name}" for name in expected]
    assert [info.web_url for info in repos] == [f"https://github.com/org/{name}" for name in expected]
    assert calls and calls[0][:3] == ["repo", "list", "org"]
    assert "--limit" in calls[0]
    assert len(fake_git.clone_calls) == len(expected)


# --------------------------------------------------------------------------- 7. REST API


def test_api_discovery_reads_all_pages(tmp_path: Path) -> None:
    """Тест 7: пагинация идёт до конца (3 страницы по `page_size`)."""
    pages = {
        1: [_api_repo("r1"), _api_repo("r2")],
        2: [_api_repo("r3"), _api_repo("r4")],
        3: [_api_repo("r5")],
    }
    requested: list[str] = []

    def http_get(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
        requested.append(url)
        page = int(url.rsplit("page=", 1)[1])
        response_headers = {"X-RateLimit-Remaining": "58"}
        if page < len(pages):
            response_headers["Link"] = f'<...page={page + 1}>; rel="next"'
        return 200, json.dumps(pages[page]), response_headers

    config = _source_config(discovery="api", page_size=2, clone_dir=str(tmp_path / "clones"))
    source = GitHubOrgSource("https://github.com/org", config, _fail_gh, http_get, FakeGit())

    repos = list(source.repositories())

    assert len(requested) == 3
    assert all("per_page=2" in url for url in requested)
    assert [Path(info.root).name for info in repos] == [f"org__r{i}" for i in range(1, 6)]


def test_api_rate_limit_reports_reset_time(tmp_path: Path) -> None:
    """Тест 7: 429 → `GitHubDiscoveryError` со временем сброса лимита."""
    reset_at = 1_800_000_000
    expected = datetime.fromtimestamp(reset_at, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    def http_get(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
        return 429, "{}", {"X-RateLimit-Reset": str(reset_at), "X-RateLimit-Remaining": "0"}

    config = _source_config(discovery="api", clone_dir=str(tmp_path / "clones"))
    source = GitHubOrgSource("https://github.com/org", config, _fail_gh, http_get, FakeGit())

    with pytest.raises(GitHubDiscoveryError, match="rate limit") as failure:
        list(source.repositories())

    assert expected in str(failure.value)


def test_strict_gh_mode_does_not_fall_back_to_api(tmp_path: Path) -> None:
    """Тест 7: `discovery: gh` без `gh` → ошибка, а не тихий переход на API."""

    def missing_gh(args: Sequence[str]) -> str:
        raise FileNotFoundError("gh not found")

    config = _source_config(discovery="gh", clone_dir=str(tmp_path / "clones"))
    source = GitHubOrgSource("https://github.com/org", config, missing_gh, _fail_http, FakeGit())

    with pytest.raises(GitHubDiscoveryError, match="gh repo list"):
        list(source.repositories())


def test_auto_mode_falls_back_to_api(tmp_path: Path) -> None:
    """Тест 7 (продолжение): `discovery: auto` при неудаче `gh` уходит в REST API."""

    def missing_gh(args: Sequence[str]) -> str:
        raise FileNotFoundError("gh not found")

    def http_get(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
        return 200, json.dumps([_api_repo("r1")]), {}

    config = _source_config(discovery="auto", clone_dir=str(tmp_path / "clones"))
    source = GitHubOrgSource("https://github.com/org", config, missing_gh, http_get, FakeGit())

    assert [Path(info.root).name for info in source.repositories()] == ["org__r1"]


# --------------------------------------------------------------------------- 8. клон и cleanup


def test_clone_uses_configured_depth(tmp_path: Path) -> None:
    """Тест 8: клонирование идёт с глубиной из конфигурации (`clone_depth: 1`)."""
    fake_git = FakeGit()
    source = RemoteRepoSource(
        "git@github.com:org/radar.git", tmp_path / "clones", 1, keep_clones=True, git=fake_git
    )

    repos = list(source.repositories())

    assert fake_git.clone_calls == [("git@github.com:org/radar.git", tmp_path / "clones" / "org__radar", 1)]
    assert [Path(info.root).name for info in repos] == ["org__radar"]


@pytest.mark.parametrize(
    ("keep_clones", "exists_after"),
    [pytest.param(False, False, id="keep_clones=false → удалён"), pytest.param(True, True, id="keep_clones=true → остался")],
)
def test_cleanup_respects_keep_clones(tmp_path: Path, keep_clones: bool, exists_after: bool) -> None:
    """Тест 8: `cleanup()` удаляет клон только при `keep_clones: false`."""
    fake_git = FakeGit()
    source = RemoteRepoSource(
        "https://github.com/org/radar.git", tmp_path / "clones", 1, keep_clones, fake_git
    )
    list(source.repositories())
    clone_path = tmp_path / "clones" / "org__radar"
    readonly = clone_path / ".git" / "objects.pack"
    readonly.write_text("packed\n", encoding="utf-8")
    readonly.chmod(stat.S_IREAD)  # Windows: read-only внутри .git не должен ломать удаление

    source.cleanup()

    assert clone_path.exists() is exists_after


def test_org_cleanup_removes_all_children(tmp_path: Path) -> None:
    """Тест 8: `cleanup()` организации проходит по всем дочерним клонам."""

    def run_gh(args: Sequence[str]) -> str:
        return json.dumps([_gh_repo("alpha"), _gh_repo("beta")])

    clones = tmp_path / "clones"
    config = _source_config(clone_dir=str(clones), keep_clones=False)
    source = GitHubOrgSource("https://github.com/org", config, run_gh, _fail_http, FakeGit())
    list(source.repositories())
    assert (clones / "org__alpha").exists() and (clones / "org__beta").exists()

    source.cleanup()

    assert not (clones / "org__alpha").exists()
    assert not (clones / "org__beta").exists()


# --------------------------------------------------------------------------- 9. фабрика


def test_factory_creates_source_per_resolved_target(tmp_path: Path) -> None:
    """Тест 9: три вида целей из `targets_resolved` → три источника нужных классов."""
    draft = ConfigDraft.from_defaults()
    draft.assign(
        "source.targets_resolved",
        [
            (str(tmp_path), SourceKind.LOCAL),
            ("git@github.com:org/radar.git", SourceKind.REMOTE_REPO),
            ("https://github.com/org", SourceKind.GITHUB_ORG),
        ],
        SOURCE_CMDLINE,
    )
    config = ScanConfig.from_draft(draft)

    sources = SourceFactory(FakeGit(), _fail_gh, _fail_http).for_config(config)

    assert [type(source) for source in sources] == [LocalPathSource, RemoteRepoSource, GitHubOrgSource]


def test_factory_returns_empty_list_without_targets() -> None:
    """Тест 9: целей нет → источников нет (пустой список, без исключений)."""
    config = ScanConfig.from_draft(ConfigDraft.from_defaults())

    assert SourceFactory(FakeGit(), _fail_gh, _fail_http).for_config(config) == []


# ------------------------------------------------------- 10. параллельное клонирование (H-13)


class BlockingGit(FakeGit):
    """`FakeGit`, у которого `clone` ждёт разрешения; считает пиковую одновременность.

    Позволяет увидеть, сколько клонов реально идёт в один момент, не полагаясь на `sleep`.
    """

    def __init__(self, gates: dict[str, threading.Event] | None = None) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._gates = gates or {}
        self._default_gate = threading.Event()
        self.started = threading.Semaphore(0)
        self.active = 0
        self.peak = 0

    def release_all(self) -> None:
        """Разрешить все ожидающие (и будущие) клоны."""
        self._default_gate.set()
        for gate in self._gates.values():
            gate.set()

    def clone(self, url: str, dst: Path, depth: int) -> Path:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        self.started.release()
        gate = self._gates.get(Path(dst).name, self._default_gate)
        assert gate.wait(timeout=WAIT_SEC), f"клон {dst} не был разрешён за {WAIT_SEC} с"
        with self._lock:
            self.active -= 1
        return super().clone(url, dst, depth)


def _org_with(git: Any, names: Sequence[str], clone_workers: int, tmp_path: Path) -> GitHubOrgSource:
    """Источник-организация с заданным числом потоков клонирования."""

    def run_gh(args: Sequence[str]) -> str:
        return json.dumps([_gh_repo(name) for name in names])

    config = _source_config(clone_dir=str(tmp_path / "clones"), keep_clones=False)
    return GitHubOrgSource("https://github.com/org", config, run_gh, _fail_http, git, clone_workers)


def _consume(source: GitHubOrgSource, sink: list[RepoInfo] | queue.Queue[RepoInfo]) -> threading.Thread:
    """Потреблять `repositories()` в отдельном потоке (генератор ленивый — он блокирует)."""

    def worker() -> None:
        for info in source.repositories():
            sink.put(info) if isinstance(sink, queue.Queue) else sink.append(info)

    thread = threading.Thread(target=worker, name="consumer", daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize(
    ("clone_workers", "expected_peak"),
    [
        pytest.param(3, 3, id="clone_workers=3 → три клона одновременно"),
        pytest.param(1, 1, id="clone_workers=1 → строго по одному"),
    ],
)
def test_org_clones_repositories_in_parallel(
    tmp_path: Path, clone_workers: int, expected_peak: int
) -> None:
    """H-13: число одновременных клонов равно `clone_workers`, не единице."""
    names = ["alpha", "beta", "gamma"]
    git = BlockingGit()
    source = _org_with(git, names, clone_workers, tmp_path)
    collected: list[RepoInfo] = []
    consumer = _consume(source, collected)

    for _ in range(expected_peak):
        assert git.started.acquire(timeout=WAIT_SEC), "клон не стартовал"
    assert git.peak == expected_peak
    # больше разрешённого числа потоков стартовать не должно
    assert git.started.acquire(timeout=0.2) is False

    git.release_all()
    consumer.join(timeout=WAIT_SEC)

    assert not consumer.is_alive()
    assert git.peak == expected_peak
    assert sorted(Path(info.root).name for info in collected) == [f"org__{name}" for name in names]


def test_org_yields_repository_before_the_rest_are_cloned(tmp_path: Path) -> None:
    """H-13: результат отдаётся по мере готовности — стадия 2 не ждёт последний клон."""
    gates = {f"org__{name}": threading.Event() for name in ("alpha", "beta", "gamma")}
    git = BlockingGit(gates)
    source = _org_with(git, ["alpha", "beta", "gamma"], 3, tmp_path)
    delivered: queue.Queue[RepoInfo] = queue.Queue()
    consumer = _consume(source, delivered)

    gates["org__beta"].set()  # разрешаем только один клон из трёх
    first = delivered.get(timeout=WAIT_SEC)

    assert Path(first.root).name == "org__beta"
    assert delivered.empty()

    git.release_all()
    consumer.join(timeout=WAIT_SEC)
    assert not consumer.is_alive()
    assert delivered.qsize() == 2


def test_org_skips_repository_whose_clone_failed(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """H-13: падение одного клона логируется с трейсом, остальные репозитории отданы."""

    class FailingGit(FakeGit):
        def clone(self, url: str, dst: Path, depth: int) -> Path:
            if Path(dst).name == "org__beta":
                raise RuntimeError("клон сорвался")
            return super().clone(url, dst, depth)

    source = _org_with(FailingGit(), ["alpha", "beta", "gamma"], 3, tmp_path)

    with caplog.at_level(logging.ERROR, logger=SOURCE_LOGGER):
        collected = list(source.repositories())

    assert sorted(Path(info.root).name for info in collected) == ["org__alpha", "org__gamma"]
    failures = [record for record in caplog.records if record.exc_info is not None]
    assert failures and any("beta" in record.getMessage() for record in failures)


def test_org_cleanup_removes_parallel_and_partial_clones(tmp_path: Path) -> None:
    """H-13: `cleanup()` убирает и полные клоны, и каталог оборвавшегося клона."""

    class HalfWrittenGit(FakeGit):
        def clone(self, url: str, dst: Path, depth: int) -> Path:
            target = Path(dst)
            if target.name == "org__beta":
                (target / ".git").mkdir(parents=True, exist_ok=True)  # клон начался…
                raise MdScanError("не удалось склонировать org/beta")  # …и оборвался
            return super().clone(url, dst, depth)

    clones = tmp_path / "clones"
    source = _org_with(HalfWrittenGit(), ["alpha", "beta", "gamma"], 3, tmp_path)

    list(source.repositories())
    assert (clones / "org__beta").exists(), "частичный клон должен остаться до cleanup"

    source.cleanup()

    assert not list(clones.iterdir())


def test_listed_md_raises_on_broken_repo_instead_of_empty_list(tmp_path: Path) -> None:
    """H-08 (Д-H08-2): битый `.git` → исключение (finder откатится на обход), а не пустой список."""
    import pytest
    from git.exc import GitError

    from core.mdscan.source.git_adapter import GitAdapter

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: /nowhere/at/all", encoding="utf-8")
    (broken / "a.md").write_text("# a", encoding="utf-8")
    with pytest.raises((GitError, OSError)):
        GitAdapter().listed_md(broken, (".md",))
