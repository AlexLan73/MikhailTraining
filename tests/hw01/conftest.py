"""Общие фикстуры тестов hw01.

Владелец файла — **T-02** (спека разработки §2.6): остальные таски его не правят,
свои фикстуры держат в собственных `test_*.py` или в `tests/hw01/support/<name>.py`.

Что здесь есть:

- опция `--rebuild-fixtures` — пересобрать эталонное дерево с нуля (часть 1, D1);
- фикстура `reference_tree` (scope=session) — набор A в `out/hw01/fixture_tree/`.

Каталог `out/` перечислен в `.gitignore`, поэтому дерево в репозиторий не попадает.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from homework.hw01_mdlinks.support.expectations import ReferenceTree
from homework.hw01_mdlinks.support.fixture_tree_builder import FixtureTreeBuilder

#: Корень репозитория: tests/hw01/conftest.py → tests/hw01 → tests → корень.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Каталог эталонного дерева (набор A).
REFERENCE_TREE_DIR: Path = REPO_ROOT / "out" / "hw01" / "fixture_tree"

_REBUILD_OPTION = "--rebuild-fixtures"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Добавляет ключ `--rebuild-fixtures` (ключ pytest, а не сканера)."""
    parser.addoption(
        _REBUILD_OPTION,
        action="store_true",
        default=False,
        help="пересобрать тестовые деревья hw01 с нуля (удалить out/hw01/fixture_tree)",
    )


@pytest.fixture(scope="session")
def reference_tree(request: pytest.FixtureRequest) -> ReferenceTree:
    """Набор A: эталонное дерево `.md` в `out/hw01/fixture_tree/` + его ожидания.

    Существующее дерево переиспользуется; `--rebuild-fixtures` пересоздаёт с нуля.
    Опция может отсутствовать, если `tests/hw01/conftest.py` не попал в начальные
    conftest'ы (запуск `pytest` без пути) — тогда просто переиспользуем дерево.
    """
    rebuild = bool(request.config.getoption(_REBUILD_OPTION, default=False))
    if rebuild and REFERENCE_TREE_DIR.exists():
        shutil.rmtree(REFERENCE_TREE_DIR)
    return FixtureTreeBuilder().reference(REFERENCE_TREE_DIR)
