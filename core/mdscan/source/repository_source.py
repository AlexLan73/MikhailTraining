"""Контракт источника репозиториев: цель → поток `RepoInfo`.

Публичное API модуля `source` (правило 09: один файл-контракт на модуль).
Реализации: `LocalPathSource`, `RemoteRepoSource`, `GitHubOrgSource`; связывает их
`SourceFactory` по `source.targets_resolved` (вид цели определяет правило V5, T-05).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ..models.repo_info import RepoInfo


class RepositorySource(Protocol):
    """Один источник репозиториев (Strategy): раскрывает цель и убирает за собой."""

    def repositories(self) -> Iterable[RepoInfo]:
        """Репозитории цели; ошибка одного репозитория не роняет остальные."""
        ...

    def cleanup(self) -> None:
        """Удалить всё созданное источником (клоны при `keep_clones: false`).

        Зовётся оркестратором в `finally`; локальный источник — no-op.
        """
        ...
