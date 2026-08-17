"""T-14 — ДЗ hw01 и его метрики: регистрация, набор ключей, пороги, детерминизм.

Номера тестов соответствуют списку таска T-14
(`MemoryBank/tasks/TASK_hw01_modules_T01-T15.md`).

Прогон целиком идёт в `tmp_path`: `ProjectPaths` подменяется, поэтому деревья, логи и
отчёты пишутся во временный каталог, а не в `out/` репозитория. Набор B уменьшен
(`gen_files`), чтобы два прогона задания укладывались в секунды: числа качества и
счётчики от размера набора B не зависят.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.config import ProjectPaths, Settings, default_settings
from homework.hw01_mdlinks import Hw01MdLinks
from homework.registry import all_tasks, get_task

#: Пороги качества на наборе A (часть 2, §9.2).
EXTRACT_F1_THRESHOLD = 0.95
CLASSIFY_ACCURACY_THRESHOLD = 0.98

#: Набор B в тестах: 200 файлов заменяются на 30 — замер `speedup` здесь не проверяется.
GEN_FILES_IN_TEST = 30

#: Операционные метрики §9.1 — их обязан вернуть `solve()`.
OPERATIONAL_KEYS = (
    "repos_total", "repos_nested", "md_files_total", "files_ok", "files_failed",
    "links_total", "links_local", "links_github", "links_url", "links_anchor",
    "links_mailto", "links_tel", "links_wikilink", "links_footnote", "links_unknown",
    "broken_local", "broken_anchor", "broken_http", "timeout_http", "broken_total",
    "broken_ratio", "error_rate", "duration_sec", "throughput_files_per_sec",
)

#: Метрики качества (§9.2), параллельности (§9.3) и код возврата прогона.
DERIVED_KEYS = (
    "extract_f1", "classify_accuracy", "duration_serial_sec", "duration_parallel_sec",
    "speedup", "parallel_efficiency", "workers_used", "exit_code",
)

#: Метрики, меряющие время, а не содержимое: два прогона по ним совпадать не обязаны.
VOLATILE_KEYS = frozenset({
    "duration_sec", "throughput_files_per_sec", "duration_serial_sec",
    "duration_parallel_sec", "speedup", "parallel_efficiency",
})


def make_task() -> Hw01MdLinks:
    """Задание с уменьшенным набором B (атрибут класса переопределён на экземпляре)."""
    task = Hw01MdLinks()
    task.gen_files = GEN_FILES_IN_TEST
    return task


def settings_for(root: Path) -> Settings:
    """Настройки, у которых `out/` и `data/` лежат во временном каталоге теста."""
    paths = ProjectPaths(root=root, data=root / "data", out=root / "out")
    return replace(default_settings(), paths=paths)


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, float], dict[str, float]]:
    """Два прогона `solve()` подряд с одним сидом и одним каталогом артефактов."""
    task = make_task()
    ctx = task.build_context(settings_for(tmp_path_factory.mktemp("hw01_task")))
    return task.solve(ctx), task.solve(ctx)


@pytest.fixture(scope="module")
def metrics(runs: tuple[dict[str, float], dict[str, float]]) -> dict[str, float]:
    """Метрики первого прогона."""
    return runs[0]


# ── 1. задание зарегистрировано ──────────────────────────────────────────────


def test_task_registered_with_unique_id() -> None:
    """`hw01` есть в реестре, класс тот самый, идентификаторы уникальны."""
    task = get_task("hw01")

    assert isinstance(task, Hw01MdLinks)
    assert task.title
    ids = [one.hw_id for one in all_tasks()]  # all_tasks сам падает на дублях
    assert ids.count("hw01") == 1


# ── 2. состав метрик ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", OPERATIONAL_KEYS + DERIVED_KEYS)
def test_solve_returns_required_metric(metrics: dict[str, float], key: str) -> None:
    """Каждый ключ §9.1–9.3 присутствует и является числом с плавающей точкой."""
    assert key in metrics
    assert isinstance(metrics[key], float)


def test_solve_returns_only_floats(metrics: dict[str, float]) -> None:
    """`solve()` возвращает `dict[str, float]` — без строк и вложенных структур."""
    assert all(isinstance(name, str) and isinstance(value, float) for name, value in metrics.items())


# ── 3. качество на наборе A выше порогов ─────────────────────────────────────


def test_quality_metrics_pass_thresholds(metrics: dict[str, float]) -> None:
    """Извлечение `f1 ≥ 0.95`, классификация `accuracy ≥ 0.98` (§9.2)."""
    assert metrics["extract_f1"] >= EXTRACT_F1_THRESHOLD
    assert metrics["classify_accuracy"] >= CLASSIFY_ACCURACY_THRESHOLD


def test_reference_run_matches_expectations(metrics: dict[str, float]) -> None:
    """Прогон набора A даёт эталонные 28 файлов и ровно 7 битых ссылок."""
    assert metrics["md_files_total"] == pytest.approx(28.0)
    assert metrics["broken_total"] == pytest.approx(7.0)
    assert metrics["exit_code"] == pytest.approx(0.0)  # run.fail_on_broken = false


def test_all_parse_workers_took_part(metrics: dict[str, float]) -> None:
    """В параллельном прогоне набора B работали все потоки разбора (§9.3)."""
    assert metrics["workers_used"] == pytest.approx(float(Hw01MdLinks.parse_workers))


# ── 4. детерминизм: тот же сид — те же числа ─────────────────────────────────


def test_repeated_run_gives_same_metrics(
    runs: tuple[dict[str, float], dict[str, float]]
) -> None:
    """Повторный прогон с тем же сидом совпадает во всём, кроме измерений времени."""
    first, second = runs
    stable_first = {name: value for name, value in first.items() if name not in VOLATILE_KEYS}
    stable_second = {name: value for name, value in second.items() if name not in VOLATILE_KEYS}

    assert stable_first == stable_second
