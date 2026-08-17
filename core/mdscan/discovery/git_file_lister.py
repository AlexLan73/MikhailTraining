"""Контракт: откуда берётся список Markdown-файлов, известных git (🔧 ревью 5)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class GitFileLister(Protocol):
    """Источник списка `.md`, уважающий `.gitignore` (`scan.respect_gitignore`).

    Контрактом владеет **потребитель** — пакет `discovery` (DIP): так обход дерева
    не зависит от `source.*`. Реализация живёт в `source.GitAdapter` (T-08) и
    подходит **структурно** — импортировать `source.*` отсюда нельзя.
    В тестах вместо неё — простая заглушка, отдающая заранее подготовленный список.
    """

    def listed_md(self, root: Path, extensions: Sequence[str]) -> list[Path]:
        """Markdown-файлы репозитория `root` с расширениями `extensions`.

        Ожидаемая семантика реализации: `git ls-files --cached --others
        --exclude-standard` — то есть отслеживаемые **и** новые файлы, минус
        игнорируемое (`node_modules/`, `build/`, `.venv/`, …). Пути могут быть
        как абсолютными, так и относительными корню репозитория.
        """
        ...
