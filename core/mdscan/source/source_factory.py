"""Фабрика источников: `source.targets_resolved` → список `RepositorySource`.

Вид цели определяет **правило V5** цепочки валидации (T-05) и записывает его в
конфигурацию; фабрика ничего не детектит заново (часть 2, инвариант 23).
"""

from __future__ import annotations

import logging
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from ..config.scan_config import ScanConfig
from ..enums.source_kind import SourceKind
from .git_adapter import GitAdapter
from .github_org_source import GitHubOrgSource, HttpGet, RunGh
from .local_path_source import LocalPathSource
from .remote_repo_source import RemoteRepoSource
from .repository_source import RepositorySource

logger = logging.getLogger("core.mdscan.source")

#: Таймаут одного запроса к GitHub API (сек): раскрытие организации не должно висеть вечно.
_API_TIMEOUT_SEC = 10.0


def _run_gh(args: Sequence[str]) -> str:
    """Боевой запуск `gh`: stdout при коде 0, иначе исключение (ловит `GitHubOrgSource`)."""
    completed = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return completed.stdout


def _http_get(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
    """Боевой GET: код ответа возвращается и для 4xx/5xx (429 разбирает вызывающий)."""
    request = urllib.request.Request(url, headers=dict(headers), method="GET")  # noqa: S310 — только https-адрес API
    try:
        with urllib.request.urlopen(request, timeout=_API_TIMEOUT_SEC) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body, dict(response.headers)
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace"), dict(exc.headers)


class SourceFactory:
    """Factory Method: по виду цели создаёт нужную реализацию `RepositorySource`."""

    def __init__(self, git: GitAdapter, run_gh: RunGh | None = None, http_get: HttpGet | None = None) -> None:
        self._git = git
        self._run_gh: RunGh = run_gh or _run_gh
        self._http_get: HttpGet = http_get or _http_get

    def for_config(self, config: ScanConfig) -> list[RepositorySource]:
        """По источнику на каждую цель `source.targets_resolved` (список смешанный)."""
        builders: dict[SourceKind, Callable[[str, ScanConfig], RepositorySource]] = {
            SourceKind.LOCAL: self._local,
            SourceKind.REMOTE_REPO: self._remote,
            SourceKind.GITHUB_ORG: self._org,
        }
        sources: list[RepositorySource] = []
        for address, kind in config.source.targets_resolved:
            builder = builders.get(kind)
            if builder is None:
                logger.error("неизвестный вид цели %r (%s) — цель пропущена", kind, address)
                continue
            logger.info("источник %s для цели %s", kind.value, address)
            sources.append(builder(address, config))
        return sources

    def _local(self, address: str, config: ScanConfig) -> RepositorySource:
        """Локальный каталог."""
        return LocalPathSource(Path(address), self._git)

    def _remote(self, address: str, config: ScanConfig) -> RepositorySource:
        """Один удалённый репозиторий (клонируется в `source.clone_dir`)."""
        source = config.source
        return RemoteRepoSource(
            address,
            Path(source.clone_dir),
            source.clone_depth,
            source.keep_clones,
            self._git,
        )

    def _org(self, address: str, config: ScanConfig) -> RepositorySource:
        """Организация GitHub целиком; репозитории клонируются в `workers.discover` потоков.

        Пул обхода параллелит источники, а организация — один источник; чтобы
        `workers.discover` работал и внутри неё, то же число отдаётся источнику (H-13).
        """
        return GitHubOrgSource(
            address,
            config.source,
            self._run_gh,
            self._http_get,
            self._git,
            config.workers.discover,
        )
