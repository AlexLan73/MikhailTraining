"""T-01: модели данных, перечисления, исключения и общие контракты hw01.

Проверяем контракт, а не реализацию: неизменяемость Value Object, состав `Enum`
(защита от «дописал лишнее значение»), два вычисляемых свойства `MdFileResult`,
иерархию исключений и наличие extra `hw01` в `pyproject.toml`.
"""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

import pytest

from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.errors import (
    ConfigError,
    GitHubDiscoveryError,
    GitUnavailableError,
    MarkdownReadError,
    MdScanError,
    UnknownFieldError,
)
from core.mdscan.models.md_file_result import MdFileResult
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.md_task import MdTask
from core.mdscan.models.progress_snapshot import ProgressSnapshot
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.models.scan_summary import ScanSummary
from core.mdscan.runtime.null_notifier import NullNotifier

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo() -> RepoInfo:
    """Минимальный репозиторий для моделей, которым он нужен как поле."""
    return RepoInfo(root=Path("repo"))


def _link(status: CheckStatus) -> MdLink:
    """Ссылка с заданным статусом — остальные поля для теста безразличны."""
    return MdLink(target="a.md", origin=LinkOrigin.INLINE, line=1, status=status)


# --- 1. неизменяемость frozen-моделей -----------------------------------------------------------


@pytest.mark.parametrize(
    ("obj", "field_name", "value"),
    [
        pytest.param(RepoInfo(root=Path("r")), "root", Path("other"), id="RepoInfo.root"),
        pytest.param(RepoInfo(root=Path("r")), "remote_url", "git@x:y.git", id="RepoInfo.remote_url"),
        pytest.param(
            MdTask(repo=RepoInfo(root=Path("r")), md_file=Path("a.md")),
            "md_file",
            Path("b.md"),
            id="MdTask.md_file",
        ),
        pytest.param(
            ScanSummary(counters={}, duration_sec=1.0, exit_code=0),
            "exit_code",
            1,
            id="ScanSummary.exit_code",
        ),
    ],
)
def test_value_objects_are_frozen(obj: object, field_name: str, value: object) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, field_name, value)


# --- 2. MdLink изменяем, значения по умолчанию --------------------------------------------------


def test_md_link_is_mutable_and_has_defaults() -> None:
    link = MdLink(target="docs/a.md", origin=LinkOrigin.INLINE, line=7)

    assert link.kind is LinkKind.UNKNOWN
    assert link.status is CheckStatus.SKIPPED
    assert link.detail == ""
    assert link.http_code == 0

    # чекер пишет прямо в ссылку — копий носителя в конвейере нет (D15.1)
    link.kind = LinkKind.LOCAL
    link.status = CheckStatus.BROKEN
    link.detail = "нет файла"
    link.http_code = 404

    assert (link.kind, link.status, link.detail, link.http_code) == (
        LinkKind.LOCAL,
        CheckStatus.BROKEN,
        "нет файла",
        404,
    )


# --- 3. MdFileResult.ok -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param("", True, id="без ошибки"),
        pytest.param("битая кодировка", False, id="с ошибкой"),
    ],
)
def test_md_file_result_ok(repo: RepoInfo, error: str, expected: bool) -> None:
    result = MdFileResult(repo=repo, md_file=Path("a.md"), rel_path="a.md", error=error)

    assert result.ok is expected


def test_md_file_result_defaults(repo: RepoInfo) -> None:
    result = MdFileResult(repo=repo, md_file=Path("a.md"), rel_path="a.md")

    assert result.links == []
    assert result.error == ""
    assert result.seconds == pytest.approx(0.0)
    assert result.thread_name == ""


def test_md_file_result_links_are_not_shared(repo: RepoInfo) -> None:
    """`default_factory` — у каждого результата свой список, иначе данные смешаются."""
    first = MdFileResult(repo=repo, md_file=Path("a.md"), rel_path="a.md")
    second = MdFileResult(repo=repo, md_file=Path("b.md"), rel_path="b.md")

    first.links.append(_link(CheckStatus.OK))

    assert second.links == []


# --- 4. MdFileResult.broken_count ---------------------------------------------------------------


def test_broken_count_counts_broken_and_timeout(repo: RepoInfo) -> None:
    result = MdFileResult(
        repo=repo,
        md_file=Path("a.md"),
        rel_path="a.md",
        links=[
            _link(CheckStatus.OK),
            _link(CheckStatus.BROKEN),
            _link(CheckStatus.TIMEOUT),
            _link(CheckStatus.SKIPPED),
            _link(CheckStatus.BROKEN),
        ],
    )

    assert result.broken_count == 3


@pytest.mark.parametrize(
    "status",
    [pytest.param(CheckStatus.OK, id="OK"), pytest.param(CheckStatus.SKIPPED, id="SKIPPED")],
)
def test_broken_count_ignores_working_statuses(repo: RepoInfo, status: CheckStatus) -> None:
    result = MdFileResult(
        repo=repo,
        md_file=Path("a.md"),
        rel_path="a.md",
        links=[_link(status), _link(status)],
    )

    assert result.broken_count == 0


def test_broken_count_without_links(repo: RepoInfo) -> None:
    assert MdFileResult(repo=repo, md_file=Path("a.md"), rel_path="a.md").broken_count == 0


# --- 5. состав Enum -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("enum_cls", "names"),
    [
        pytest.param(
            LinkKind,
            [
                "LOCAL",
                "ANCHOR",
                "GITHUB",
                "URL",
                "MAILTO",
                "TEL",
                "WIKILINK",
                "FOOTNOTE_URL",
                "UNKNOWN",
            ],
            id="LinkKind",
        ),
        pytest.param(CheckStatus, ["OK", "BROKEN", "TIMEOUT", "SKIPPED"], id="CheckStatus"),
        pytest.param(
            LinkOrigin,
            ["INLINE", "REFERENCE", "AUTOLINK", "WIKILINK", "FOOTNOTE"],
            id="LinkOrigin",
        ),
        pytest.param(SourceKind, ["LOCAL", "REMOTE_REPO", "GITHUB_ORG"], id="SourceKind"),
    ],
)
def test_enum_members_are_exactly_as_specified(enum_cls: type, names: list[str]) -> None:
    assert [member.name for member in enum_cls] == names


def test_source_kind_has_no_yaml_member() -> None:
    """`yaml` — ветка CLI (T-05), а не вид источника: в enum его быть не должно."""
    assert "YAML" not in {member.name for member in SourceKind}


# --- 6. NullNotifier и ProgressSnapshot ---------------------------------------------------------


def test_null_notifier_does_nothing_and_returns_none() -> None:
    assert NullNotifier().show("x") is None


def test_progress_snapshot_is_frozen() -> None:
    snap = ProgressSnapshot(
        repos_total=1,
        repos_done=0,
        md_found=10,
        parsed=3,
        task_qsize=7,
        result_qsize=1,
        links=40,
        broken=2,
    )

    assert snap.md_found == 10
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.parsed = 4


# --- 7. extra hw01 в pyproject.toml -------------------------------------------------------------


def test_pyproject_has_hw01_extra_with_required_dependencies() -> None:
    """`pip install -e .[hw01]` ставит 4 обязательные + linkify/rich (🔧 р5, решение Alex); pip не запускается."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    extras = pyproject["project"]["optional-dependencies"]
    assert "hw01" in extras

    packages = {item.split(">")[0].split("=")[0].strip().lower() for item in extras["hw01"]}
    assert {"markdown-it-py", "mdit-py-plugins", "gitpython", "pyyaml"} <= packages
    assert packages <= {"markdown-it-py", "mdit-py-plugins", "gitpython", "pyyaml", "linkify-it-py", "rich"}


# --- 8. иерархия исключений ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_cls",
    [
        pytest.param(ConfigError, id="ConfigError"),
        pytest.param(UnknownFieldError, id="UnknownFieldError"),
        pytest.param(MarkdownReadError, id="MarkdownReadError"),
        pytest.param(GitUnavailableError, id="GitUnavailableError"),
        pytest.param(GitHubDiscoveryError, id="GitHubDiscoveryError"),
    ],
)
def test_all_errors_inherit_mdscan_error(exc_cls: type[Exception]) -> None:
    assert issubclass(exc_cls, MdScanError)


def test_unknown_field_error_is_config_error() -> None:
    """Код возврата 2 назначается по `ConfigError` — `UnknownFieldError` обязан в него попадать."""
    assert issubclass(UnknownFieldError, ConfigError)

    with pytest.raises(ConfigError, match="похожие поля"):
        raise UnknownFieldError("неизвестное поле workers.parze; похожие поля: workers.parse")


def test_mdscan_error_is_plain_exception() -> None:
    assert issubclass(MdScanError, Exception)
