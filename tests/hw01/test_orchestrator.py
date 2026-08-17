"""T-13 — оркестратор и точка входа: сквозной прогон, коды возврата, гашение потоков.

Это единственный интеграционный набор hw01: здесь работают все модули сразу, на
настоящем дереве набора A (T-02). Сеть выключена (`http.enabled: false`), прогресс
выключен, лог и отчёт пишутся в `tmp_path` — в репозиторий тесты не пишут.

**Почему дерево копируется в `tmp_path`.** `LocalPathSource` определяет корень через
`GitAdapter.root_of` с `search_parent_directories=True` (правило ближайшего корня,
D5/D6.2). Эталонное дерево лежит в `out/hw01/fixture_tree`, то есть **внутри** рабочей
копии MikhailTraining, поэтому цель расширилась бы до всего репозитория, а сами файлы
дерева выпали бы из `git ls-files` (каталог `out/` в `.gitignore`). Копия в `tmp_path`
лежит вне git — так проверяется именно набор A и его ожидания.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Sequence
from pathlib import Path

import pytest

from core.mdscan.config.config_draft import ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.models.scan_summary import ScanSummary
from core.mdscan.reporting.markdown_report_builder import MarkdownReportBuilder
from core.mdscan.runtime import pipeline_runner
from core.mdscan.runtime.collecting_observer import CollectingObserver
from core.mdscan.runtime.scan_orchestrator import ScanOrchestrator
from homework.hw01_mdlinks.support.expectations import ReferenceTree

#: Имена потоков прогона: после `scan()` ни одного из них остаться не должно (инвариант 11).
OUR_THREAD_PREFIXES = ("parse-", "discover", "collector", "progress")

#: Строки отчёта, зависящие от времени: два прогона обязаны совпасть во всём остальном.
VOLATILE_MARKERS = ("старт", "длительность", "duration_sec", "throughput_files_per_sec")

#: Счётчики, которые меряют время прогона, а не его содержимое.
VOLATILE_COUNTERS = ("duration_sec", "throughput_files_per_sec")


@pytest.fixture(scope="session")
def scan_tree(reference_tree: ReferenceTree, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Копия эталонного дерева вне git — цель сквозных прогонов (см. докстринг модуля)."""
    destination = tmp_path_factory.mktemp("mdscan_tree") / "fixture_tree"
    shutil.copytree(reference_tree.root, destination)
    return destination


def make_config(
    target: Path,
    tmp_path: Path,
    overrides: dict[str, object] | None = None,
) -> ScanConfig:
    """Конфигурация прогона по дереву: без сети, без прогресса, вывод — в `tmp_path`."""
    draft = ConfigDraft.from_defaults()
    draft.assign("source.target", str(target), "c")
    draft.assign("source.targets_resolved", ((str(target), SourceKind.LOCAL),), "c")
    draft.assign("http.enabled", False, "c")
    draft.assign("progress.enabled", False, "c")
    draft.assign("logging.dir", str(tmp_path / "logs"), "c")
    draft.assign("report.dir", str(tmp_path / "reports"), "c")
    for path, value in (overrides or {}).items():
        draft.assign(path, value, "c")
    return ScanConfig.from_draft(draft)


def run_scan(target: Path, tmp_path: Path, overrides: dict[str, object] | None = None) -> ScanSummary:
    """Один прогон оркестратора на готовой конфигурации."""
    return ScanOrchestrator().scan(make_config(target, tmp_path, overrides))


def report_text(tmp_path: Path) -> str:
    """Текст единственного отчёта прогона из `tmp_path/reports`."""
    reports = sorted((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1, f"ожидался один отчёт, найдено: {reports}"
    return reports[0].read_text(encoding="utf-8")


def stable_lines(text: str) -> list[str]:
    """Строки отчёта без зависящих от времени — для сравнения двух прогонов."""
    return [line for line in text.splitlines() if not any(mark in line for mark in VOLATILE_MARKERS)]


def stable_counters(summary: ScanSummary) -> dict[str, float]:
    """Счётчики без временных: сравниваются два прогона, а не две загрузки машины."""
    return {name: value for name, value in summary.counters.items() if name not in VOLATILE_COUNTERS}


def our_threads() -> list[str]:
    """Живые потоки прогона (не считая главного и чужих)."""
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith(OUR_THREAD_PREFIXES)
    ]


# ── 1. сквозной прогон: числа совпадают с ожиданиями набора A ────────────────


def test_end_to_end_counters_match_expectations(
    scan_tree: Path, reference_tree: ReferenceTree, tmp_path: Path
) -> None:
    """Прогон на наборе A даёт ровно те файлы, ссылки и битые, что записаны в эталоне."""
    expected = reference_tree.expectations
    summary = run_scan(scan_tree, tmp_path)
    counters = summary.counters
    assert counters["md_files_total"] == pytest.approx(float(expected.files_total))
    assert counters["links_total"] == pytest.approx(float(expected.links_total))
    assert counters["broken_total"] == pytest.approx(float(expected.broken_total))
    assert counters["broken_total"] == pytest.approx(7.0)


def test_end_to_end_writes_log_and_report(scan_tree: Path, tmp_path: Path) -> None:
    """Лог и отчёт создаются парой: одна метка времени на прогон (D9)."""
    run_scan(scan_tree, tmp_path)
    logs = sorted((tmp_path / "logs").glob("*.log"))
    reports = sorted((tmp_path / "reports").glob("*.md"))
    assert len(logs) == 1 and len(reports) == 1
    assert logs[0].stem == reports[0].stem
    assert logs[0].stem.startswith("fixture_tree_")
    assert "# scope" in logs[0].read_text(encoding="utf-8")


# ── 2. детерминизм отчёта ────────────────────────────────────────────────────


def test_two_runs_produce_same_report(scan_tree: Path, tmp_path: Path) -> None:
    """Два прогона на одном дереве дают одинаковый отчёт — кроме времени (инвариант 9)."""
    first = run_scan(scan_tree, tmp_path / "run1")
    second = run_scan(scan_tree, tmp_path / "run2")
    assert stable_counters(first) == stable_counters(second)
    assert stable_lines(report_text(tmp_path / "run1")) == stable_lines(report_text(tmp_path / "run2"))


# ── 3. коды возврата ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fail_on_broken", "expected_code"),
    [(True, 1), (False, 0)],
    ids=["fail_on_broken=true→1", "fail_on_broken=false→0"],
)
def test_exit_code_follows_fail_on_broken(
    scan_tree: Path, tmp_path: Path, fail_on_broken: bool, expected_code: int
) -> None:
    """Битые ссылки дают код 1 только при `run.fail_on_broken` (часть 2 §1.4)."""
    summary = run_scan(scan_tree, tmp_path, {"run.fail_on_broken": fail_on_broken})
    assert summary.counters["broken_total"] > 0
    assert summary.exit_code == expected_code


# ── 4. ошибка записи отчёта ──────────────────────────────────────────────────


def test_report_write_failure_gives_code_three(scan_tree: Path, tmp_path: Path) -> None:
    """Отчёт некуда записать → код 3 и `CRITICAL` в логе; счётчики прогона не теряются.

    Запись `CRITICAL` проверяется по файлу лога, а не через `caplog`: логгер
    `core.mdscan` намеренно не пробрасывает записи корневому (`propagate = False`,
    T-04), поэтому перехватчик pytest их не видит.
    """
    (tmp_path / "reports").write_text("не каталог, а файл", encoding="utf-8")

    summary = run_scan(scan_tree, tmp_path)

    assert summary.exit_code == 3
    assert summary.counters["md_files_total"] > 0
    written = sorted((tmp_path / "logs").glob("*.log"))
    assert len(written) == 1
    log_text = written[0].read_text(encoding="utf-8")
    assert "CRITICAL" in log_text
    assert "отчёт не записан" in log_text


# ── 5. прогресс не влияет на результат ───────────────────────────────────────


def test_progress_flag_does_not_change_report(scan_tree: Path, tmp_path: Path) -> None:
    """Прогон с включённым и выключенным прогрессом даёт один и тот же отчёт (DoD T-11)."""
    without = run_scan(scan_tree, tmp_path / "off", {"progress.enabled": False})
    with_progress = run_scan(scan_tree, tmp_path / "on", {"progress.enabled": True})
    assert stable_counters(without) == stable_counters(with_progress)
    assert stable_lines(report_text(tmp_path / "off")) == stable_lines(report_text(tmp_path / "on"))


# ── 6. потоки завершены ──────────────────────────────────────────────────────


def test_no_threads_left_after_scan(scan_tree: Path, tmp_path: Path) -> None:
    """После `scan()` наших потоков в `threading.enumerate()` нет (инвариант 11)."""
    assert our_threads() == []
    run_scan(scan_tree, tmp_path)
    assert our_threads() == []


# ── 7. отчёт строится после collector.join() ─────────────────────────────────


def test_report_built_after_collector_join(
    scan_tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Отчёт собирается строго после выхода сборщика (инвариант 25, D1)."""
    order: list[str] = []

    class RecordingCollector(CollectingObserver):
        """Подставной сборщик: фиксирует момент собственного `join()`."""

        def join(self, timeout: float | None = None) -> None:
            super().join(timeout)
            if not self.is_alive():
                order.append("collector.join")

    original_build = MarkdownReportBuilder.build

    def recording_build(self: MarkdownReportBuilder, results: Sequence[object], summary: object) -> str:
        order.append("report.build")
        return original_build(self, results, summary)  # type: ignore[arg-type]

    monkeypatch.setattr(pipeline_runner, "CollectingObserver", RecordingCollector)
    monkeypatch.setattr(MarkdownReportBuilder, "build", recording_build)

    run_scan(scan_tree, tmp_path)
    assert order == ["collector.join", "report.build"]


# ── 8. точка входа: цель `yaml` со списком каталогов ─────────────────────────


def test_main_yaml_scans_every_configured_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`python -m core.mdscan yaml` со списком из двух каталогов сканирует оба."""
    from core.mdscan.__main__ import main

    roots = []
    for name in ("alpha", "beta"):
        root = tmp_path / name
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "page.md").write_text("# Раздел\n\n[себя](page.md)\n", encoding="utf-8")
        roots.append(root)
    _write_yaml(tmp_path, roots)
    monkeypatch.chdir(tmp_path)

    code = main(["yaml"])

    assert code == 0
    text = report_text(tmp_path)
    assert all(root.name in text for root in roots)
    assert text.count("docs/page.md") >= len(roots)


# ── 9. точка входа: без аргументов ───────────────────────────────────────────


def test_main_without_arguments_prints_config_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Без аргументов печатается конфигурация, код 0, лог и отчёт не создаются (D19)."""
    monkeypatch.chdir(tmp_path)
    from core.mdscan.__main__ import main

    code = main([])

    captured = capsys.readouterr()
    assert code == 0
    assert "КОНФИГУРАЦИЯ" in captured.out
    assert "workers.parse" in captured.out
    assert (tmp_path / "mdscan.yaml").exists()  # холодный старт — это норма (D19)
    assert list(tmp_path.rglob("*.log")) == []
    assert list(tmp_path.rglob("*.md")) == []


def _write_yaml(directory: Path, roots: Sequence[Path]) -> None:
    """Минимальный `mdscan.yaml`: список целей и каталоги вывода внутри `tmp_path`."""
    yaml = pytest.importorskip("yaml", reason="PyYAML нужен для чтения mdscan.yaml")
    payload = {
        "source": {"repositories": [str(root) for root in roots]},
        "http": {"enabled": False},
        "progress": {"enabled": False},
        "logging": {"dir": str(directory / "logs")},
        "report": {"dir": str(directory / "reports")},
    }
    (directory / "mdscan.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
