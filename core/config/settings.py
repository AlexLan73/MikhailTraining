"""Настройки проекта — неизменяемые Value Object'ы.

`ProjectPaths` — единственный источник истины про каталоги (правило 05: только Pathlib,
никаких абсолютных путей в коде: корень вычисляется от расположения файла).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_SEED = 42

# корень репозитория = на два уровня выше этого файла (core/config/settings.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProjectPaths:
    """Каталоги проекта. `data`/`out` не трекаются git'ом (см. .gitignore)."""

    root: Path = _REPO_ROOT
    data: Path = _REPO_ROOT / "data"
    out: Path = _REPO_ROOT / "out"

    def out_for(self, hw_id: str) -> Path:
        """Каталог артефактов одного ДЗ (`out/hw01/`), создаётся при обращении."""
        path = self.out / hw_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def data_for(self, name: str) -> Path:
        """Путь к датасету внутри `data/` (файл может ещё не существовать)."""
        return self.data / name


@dataclass(frozen=True)
class Settings:
    """Глобальные настройки прогона."""

    seed: int = DEFAULT_SEED
    paths: ProjectPaths = ProjectPaths()
    verbose: bool = True


def default_settings() -> Settings:
    """Настройки по умолчанию — точка входа для `run_hw.py`."""
    return Settings()
