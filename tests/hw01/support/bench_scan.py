"""Замер скорости прогона сканера hw01 — инструмент таска H-04, не тест.

Запуск (из корня репозитория):

```bash
python tests/hw01/support/bench_scan.py --workers 1 --repeat 5 --layers
python tests/hw01/support/bench_scan.py --workers 10 --repeat 5 --profile
```

Набор B строится тем же `FixtureTreeBuilder`, что и в ДЗ, поэтому дерево
воспроизводимо побайтово (500 файлов, сид 42). Печать — только в `main()`.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import statistics
import sys
import time
from pathlib import Path

#: Корень репозитория: скрипт запускается напрямую (`python tests/hw01/support/bench_scan.py`),
#: поэтому `core.*` и `homework.*` в `sys.path` сами не появятся. Каталог самого скрипта там уже есть —
#: соседний `bench_layers` импортируется как модуль верхнего уровня (в `tests/` нет `__init__.py`,
#: и путь `tests.hw01.support.*` был бы для `mypy` вторым именем того же файла).
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_layers import LayerBench  # noqa: E402

from core.mdscan import ScanConfig, Scanner, ScanOrchestrator, ScanSummary  # noqa: E402
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft  # noqa: E402
from core.mdscan.enums.source_kind import SourceKind  # noqa: E402
from homework.hw01_mdlinks.support.fixture_tree_builder import FixtureTreeBuilder  # noqa: E402

#: Рабочий каталог замера — в `out/`, git его не трекает.
BENCH_DIR = ROOT / "out" / "hw01" / "bench"
DEFAULT_FILES = 500
DEFAULT_SEED = 42
DEFAULT_TOP = 15

#: Что считаем в профиле поимённо (спека этапа 2, §2.1 и гипотеза G4).
PROFILE_MARKS: tuple[tuple[str, str, str], ...] = (
    ("nt._getfinalpathname", "~", "_getfinalpathname"),
    ("logging.debug", "logging", "debug"),
)


class ScanBench:
    """Прогоны набора B с одинаковой конфигурацией: медиана, слои, профиль."""

    def __init__(self, files: int = DEFAULT_FILES, seed: int = DEFAULT_SEED) -> None:
        self._tree = FixtureTreeBuilder().generated(BENCH_DIR / "gen", files, seed)
        self._out_dir = BENCH_DIR / "out"
        self._scanner: Scanner = ScanOrchestrator()

    @property
    def tree(self) -> Path:
        """Каталог набора B."""
        return self._tree

    def config(self, workers: int) -> ScanConfig:
        """Конфигурация замера: сеть, прогресс, лог и консоль выключены.

        `scan.respect_gitignore: false` обязателен — дерево лежит в `out/`,
        который перечислен в `.gitignore`, и `git ls-files` его бы не отдал.
        """
        draft = ConfigDraft.from_defaults()
        draft.assign("source.target", str(self._tree), SOURCE_CMDLINE)
        draft.assign(
            "source.targets_resolved", ((str(self._tree), SourceKind.LOCAL),), SOURCE_CMDLINE
        )
        draft.assign("scan.respect_gitignore", False, SOURCE_CMDLINE)
        draft.assign("workers.parse", workers, SOURCE_CMDLINE)
        draft.assign("http.enabled", False, SOURCE_CMDLINE)
        draft.assign("progress.enabled", False, SOURCE_CMDLINE)
        draft.assign("logging.enabled", False, SOURCE_CMDLINE)
        draft.assign("logging.dir", str(self._out_dir), SOURCE_CMDLINE)
        draft.assign("report.dir", str(self._out_dir), SOURCE_CMDLINE)
        draft.assign("report.console", False, SOURCE_CMDLINE)
        draft.assign("run.fail_on_broken", False, SOURCE_CMDLINE)
        return ScanConfig.from_draft(draft)

    def once(self, workers: int) -> tuple[float, ScanSummary]:
        """Один прогон: секунды по `perf_counter` и его итоги."""
        config = self.config(workers)
        started = time.perf_counter()
        summary = self._scanner.scan(config)
        return time.perf_counter() - started, summary

    def measure(self, workers: int, repeat: int) -> dict[str, float]:
        """Прогрев + `repeat` прогонов; наружу — медиана, минимум, максимум."""
        self.once(workers)  # прогрев: первый проход греет кэш файловой системы
        samples = [self.once(workers) for _ in range(repeat)]
        times = [seconds for seconds, _ in samples]
        summary = samples[-1][1]
        return {
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "files": summary.counters.get("md_files_total", 0.0),
            "links": summary.counters.get("links_total", 0.0),
        }

    def layers(self, workers: int, full: float) -> dict[str, float]:
        """Разложение по слоям; `full` — медиана полного прогона из `measure`.

        Накладные (потоки, очереди, `join`, старт/стоп логгера) считаются остатком:
        полный прогон − обход − «полезная нагрузка» (спека этапа 2, §2.2).
        """
        parts = LayerBench(self._tree, self.config(workers)).measure()
        parts["full"] = full
        parts["overhead"] = full - parts["discover"] - parts["payload"]
        return parts

    def profile(self, workers: int, top: int = DEFAULT_TOP) -> tuple[str, dict[str, int]]:
        """cProfile одного прогона: таблица по `tottime` и счётчики из `PROFILE_MARKS`."""
        profiler = cProfile.Profile()
        profiler.enable()
        self._scanner.scan(self.config(workers))
        profiler.disable()
        buffer = io.StringIO()
        stats = pstats.Stats(profiler, stream=buffer).sort_stats("tottime")
        stats.print_stats(top)
        return buffer.getvalue(), self._counts(stats)

    @staticmethod
    def _counts(stats: pstats.Stats) -> dict[str, int]:
        """Сколько раз вызваны интересующие функции (по всем записям профиля)."""
        found = {label: 0 for label, _, _ in PROFILE_MARKS}
        for (module, _, function), record in stats.stats.items():  # type: ignore[attr-defined]
            for label, module_mark, function_mark in PROFILE_MARKS:
                if function_mark in function and module_mark in str(module):
                    found[label] += int(record[1])
        return found


def main() -> None:
    """Разбор аргументов и печать результатов — единственный слой вывода скрипта."""
    parser = argparse.ArgumentParser(description="Замер прогона набора B (hw01, таск H-04)")
    parser.add_argument("--workers", type=int, default=1, help="workers.parse (по умолчанию 1)")
    parser.add_argument("--repeat", type=int, default=5, help="число прогонов, берётся медиана")
    parser.add_argument("--files", type=int, default=DEFAULT_FILES, help="размер набора B")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="сид генератора дерева")
    parser.add_argument("--layers", action="store_true", help="разложение по слоям без потоков")
    parser.add_argument("--profile", action="store_true", help="cProfile по tottime, топ-15")
    args = parser.parse_args()

    bench = ScanBench(args.files, args.seed)
    print(f"дерево: {bench.tree.relative_to(ROOT).as_posix()} · workers.parse={args.workers}")
    result = bench.measure(args.workers, args.repeat)
    print(
        f"время: медиана {result['median']:.3f} с "
        f"(min {result['min']:.3f} / max {result['max']:.3f}, прогонов {args.repeat}) · "
        f"файлов {result['files']:.0f}, ссылок {result['links']:.0f}"
    )
    if args.layers:
        parts = bench.layers(args.workers, result["median"])
        print("слои (последовательно, без потоков):")
        for name in ("discover", "read", "extract", "classify", "check_cold", "check_warm",
                     "payload", "full", "overhead"):
            print(f"  {name:<12} {parts[name]:.3f} с")
    if args.profile:
        table, counts = bench.profile(args.workers)
        print(table)
        for label, calls in counts.items():
            print(f"вызовов {label}: {calls}")


if __name__ == "__main__":
    main()
