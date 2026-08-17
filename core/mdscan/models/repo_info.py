"""Репозиторий, к которому относится разбираемый файл."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepoInfo:
    """Value Object: пересекает границы потоков, поэтому неизменяем.

    `remote_url` — адрес git (для клонирования), `web_url` — адрес для отчёта
    (трио «корневой / репозиторий / файл», D6.4): это разные вещи и путать их нельзя.
    """

    root: Path
    remote_url: str = ""
    web_url: str = ""
    is_nested: bool = False
    #: 🔧 р5: цель — подкаталог репозитория: файлы берутся только из него (root остаётся git-корнем,
    #: чтобы rel_path/web_url считались от корня). None = весь репозиторий.
    scope: Path | None = None
