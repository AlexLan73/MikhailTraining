"""Нагрузочный замер сканера hw01 — инструмент таска H-09, не тест.

Запуск (из корня репозитория):

```bash
python tests/hw01/support/bench_load.py --sizes 500,2000,5000 --repeat 3 --leak 5000 --log-run 5000
```

Деревья строит тот же `FixtureTreeBuilder`, что и ДЗ, поэтому они воспроизводимы
побайтово (сид 42). Конфигурация прогона совпадает с `bench_scan.py` (H-04):
сеть, прогресс, лог и консольная сводка выключены — меряем только сам конвейер.
Печать — только в `main()`.
"""

from __future__ import annotations

import argparse
import gc
import statistics
import sys
import threading
import time
import tracemalloc
from pathlib import Path

#: Корень репозитория: скрипт запускается напрямую, `core.*`/`homework.*` в `sys.path` не появятся сами.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.mdscan import ScanConfig, Scanner, ScanOrchestrator, ScanSummary  # noqa: E402
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft  # noqa: E402
from core.mdscan.enums.source_kind import SourceKind  # noqa: E402
from homework.hw01_mdlinks.support.fixture_tree_builder import FixtureTreeBuilder  # noqa: E402

#: Рабочий каталог замера — в `out/`, git его не трекает.
LOAD_DIR = ROOT / "out" / "hw01" / "load"
DEFAULT_SIZES: tuple[int, ...] = (500, 2000, 5000)
DEFAULT_WORKERS: tuple[int, ...] = (1, 10)
DEFAULT_SEED = 42
DEFAULT_REPEAT = 3
#: Шаг опроса `ScanOrchestrator.snapshot()` — 50 мс: пик очередей виден, а накладные ниже шума.
POLL_INTERVAL_SEC = 0.05
MIB = 1024.0 * 1024.0


class LoadBench:
    """Прогоны деревьев разного размера: время, пиковая память, пик очередей, размер отчёта.

    Один и тот же `ScanOrchestrator` переиспользуется между прогонами (как в `bench_scan.py`):
    так видно, копится ли что-то в процессе от прогона к прогону (проверка утечки).
    """

    def __init__(self, seed: int = DEFAULT_SEED) -> None:
        self._seed = seed
        self._scanner: Scanner = ScanOrchestrator()
        self._progress = self._scanner  # тот же объект как `ProgressSource` (T-11)
        self._peak_tasks = 0
        self._peak_results = 0

    def tree(self, files: int) -> Path:
        """Дерево на `files` файлов; повторный вызов переиспользует уже собранное."""
        return FixtureTreeBuilder().generated(LOAD_DIR / f"gen_{files}", files, self._seed)

    def config(self, files: int, workers: int, *, log_level: str = "") -> ScanConfig:
        """Конфигурация замера. `log_level` непустой → лог включён (отдельный прогон)."""
        draft = ConfigDraft.from_defaults()
        tree = self.tree(files)
        out_dir = LOAD_DIR / f"out_{files}"
        draft.assign("source.target", str(tree), SOURCE_CMDLINE)
        draft.assign("source.targets_resolved", ((str(tree), SourceKind.LOCAL),), SOURCE_CMDLINE)
        draft.assign("scan.respect_gitignore", False, SOURCE_CMDLINE)
        draft.assign("workers.parse", workers, SOURCE_CMDLINE)
        draft.assign("http.enabled", False, SOURCE_CMDLINE)
        draft.assign("progress.enabled", False, SOURCE_CMDLINE)
        draft.assign("logging.enabled", bool(log_level), SOURCE_CMDLINE)
        draft.assign("logging.level", log_level or "INFO", SOURCE_CMDLINE)
        draft.assign("logging.dir", str(out_dir), SOURCE_CMDLINE)
        draft.assign("report.dir", str(out_dir), SOURCE_CMDLINE)
        draft.assign("report.console", False, SOURCE_CMDLINE)
        draft.assign("run.fail_on_broken", False, SOURCE_CMDLINE)
        return ScanConfig.from_draft(draft)

    def once(self, config: ScanConfig) -> tuple[float, ScanSummary]:
        """Один прогон с опросом очередей в фоне: секунды и итоги."""
        stop = threading.Event()
        poller = threading.Thread(target=self._poll, args=(stop,), name="qsize-poll", daemon=True)
        poller.start()
        started = time.perf_counter()
        try:
            summary = self._scanner.scan(config)
        finally:
            stop.set()
            poller.join(timeout=1.0)
        return time.perf_counter() - started, summary

    def measure(self, files: int, workers: int, repeat: int) -> dict[str, float]:
        """Прогрев + `repeat` прогонов; наружу — медиана, пик очередей, размер отчёта."""
        config = self.config(files, workers)
        self.once(config)  # прогрев: греет кэш файловой системы
        self._peak_tasks = self._peak_results = 0
        samples = [self.once(config) for _ in range(repeat)]
        times = [seconds for seconds, _ in samples]
        summary = samples[-1][1]
        median = statistics.median(times)
        return {
            "median": median,
            "min": min(times),
            "max": max(times),
            "files": summary.counters.get("md_files_total", 0.0),
            "links": summary.counters.get("links_total", 0.0),
            "files_per_sec": summary.counters.get("md_files_total", 0.0) / median if median else 0.0,
            "peak_tasks": float(self._peak_tasks),
            "peak_results": float(self._peak_results),
            "report_kib": self._newest(files, ".md").stat().st_size / 1024.0,
            "peak_mib": self.peak_memory(files, workers),
        }

    def peak_memory(self, files: int, workers: int) -> float:
        """Пиковая память одного прогона в МиБ (`tracemalloc`, отдельный прогон — он медленнее)."""
        config = self.config(files, workers)
        gc.collect()
        tracemalloc.start()
        try:
            self.once(config)
            return tracemalloc.get_traced_memory()[1] / MIB
        finally:
            tracemalloc.stop()

    def leak_probe(self, files: int, workers: int, times: int) -> list[tuple[float, float]]:
        """`times` прогонов подряд в одном процессе: (остаток, пик) в МиБ после каждого.

        Растущий «остаток» = что-то держится ссылками между прогонами, то есть утечка.
        """
        config = self.config(files, workers)
        gc.collect()
        tracemalloc.start()
        try:
            marks: list[tuple[float, float]] = []
            for _ in range(times):
                tracemalloc.reset_peak()
                self.once(config)
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                marks.append((current / MIB, peak / MIB))
            return marks
        finally:
            tracemalloc.stop()

    def log_run(self, files: int, workers: int, level: str) -> dict[str, float]:
        """Прогон с включённым логом: время, число строк и размер файла лога."""
        seconds, summary = self.once(self.config(files, workers, log_level=level))
        log_file = self._newest(files, ".log")
        lines = sum(1 for _ in log_file.open(encoding="utf-8", errors="replace"))
        return {
            "seconds": seconds,
            "lines": float(lines),
            "log_kib": log_file.stat().st_size / 1024.0,
            "files": summary.counters.get("md_files_total", 0.0),
        }

    def _poll(self, stop: threading.Event) -> None:
        """Фоновый опрос `ProgressSource`: копит максимумы `task_qsize` и `result_qsize`."""
        while not stop.is_set():
            snapshot = self._progress.snapshot()
            self._peak_tasks = max(self._peak_tasks, snapshot.task_qsize)
            self._peak_results = max(self._peak_results, snapshot.result_qsize)
            stop.wait(POLL_INTERVAL_SEC)

    @staticmethod
    def _newest(files: int, suffix: str) -> Path:
        """Самый свежий файл с расширением `suffix` в каталоге вывода дерева `files`."""
        candidates = sorted((LOAD_DIR / f"out_{files}").glob(f"*{suffix}"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError(f"нет файлов *{suffix} в out_{files}")
        return candidates[-1]


def main() -> None:
    """Разбор аргументов и печать результатов — единственный слой вывода скрипта."""
    parser = argparse.ArgumentParser(description="Нагрузочный замер сканера (hw01, таск H-09)")
    parser.add_argument("--sizes", default=",".join(str(n) for n in DEFAULT_SIZES), help="размеры деревьев")
    parser.add_argument("--workers", default=",".join(str(n) for n in DEFAULT_WORKERS), help="workers.parse")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help="прогонов на точку, берётся медиана")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="сид генератора деревьев")
    parser.add_argument("--leak", type=int, default=0, help="проверка утечки: размер дерева (0 — не делать)")
    parser.add_argument("--leak-times", type=int, default=3, help="сколько прогонов подряд в проверке утечки")
    parser.add_argument("--log-run", type=int, default=0, help="прогон с логом: размер дерева (0 — не делать)")
    parser.add_argument("--log-level", default="INFO", help="уровень лога для --log-run")
    args = parser.parse_args()

    sizes = [int(item) for item in args.sizes.split(",") if item]
    workers_list = [int(item) for item in args.workers.split(",") if item]
    bench = LoadBench(args.seed)
    print(f"деревья: out/hw01/load/gen_<N> · сид {args.seed} · прогонов на точку {args.repeat}")
    print(
        f"{'файлов':>7} {'потоков':>8} {'медиана,с':>10} {'файлов/с':>9} {'память,МиБ':>11} "
        f"{'пик tasks':>10} {'пик results':>12} {'отчёт,КиБ':>10} {'ссылок':>7}"
    )
    for files in sizes:
        for workers in workers_list:
            row = bench.measure(files, workers, args.repeat)
            print(
                f"{row['files']:>7.0f} {workers:>8d} {row['median']:>10.3f} {row['files_per_sec']:>9.0f} "
                f"{row['peak_mib']:>11.1f} {row['peak_tasks']:>10.0f} {row['peak_results']:>12.0f} "
                f"{row['report_kib']:>10.1f} {row['links']:>7.0f}"
            )
    if args.leak:
        print(f"утечка: {args.leak_times} прогонов подряд по {args.leak} файлов (остаток / пик, МиБ)")
        for number, (current, peak) in enumerate(bench.leak_probe(args.leak, workers_list[-1], args.leak_times), 1):
            print(f"  прогон {number}: остаток {current:.1f} · пик {peak:.1f}")
    if args.log_run:
        row = bench.log_run(args.log_run, workers_list[-1], args.log_level)
        print(
            f"лог {args.log_level} на {row['files']:.0f} файлов: строк {row['lines']:.0f}, "
            f"{row['log_kib']:.0f} КиБ, прогон {row['seconds']:.3f} с"
        )


if __name__ == "__main__":
    main()
