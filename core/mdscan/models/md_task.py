"""Единица работы конвейера: «разобрать этот файл этого репозитория»."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.mdscan.models.repo_info import RepoInfo


@dataclass(frozen=True, slots=True)
class MdTask:
    """Command: кладётся в `TaskQueue`, читается воркерами — потому неизменяем."""

    repo: RepoInfo
    md_file: Path
