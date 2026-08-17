"""Замер `speedup` с включённой HTTP-проверкой — инструмент таска H-07, не тест.

Запуск (из корня репозитория):

```bash
python tests/hw01/support/bench_http.py --workers 1,5,10 --repeat 3
```

Почему отдельный инструмент, а не `bench_scan.py`: там набор B без внешних
ссылок и цель — CPU-профиль. Здесь наоборот — вся работа воркера уходит в
ожидание ответа, и меряется именно то, ради чего в конвейере потоки
(спека этапа 2, §2.3 и §2.5).

Дерево: `files` файлов, в каждом `urls` **уникальных** адресов локального
сервера (`/a<i>`, `/b<i>`) — уникальность обязательна, иначе кэш `HttpChecker`
(один адрес = один запрос за прогон) свёл бы замер к нескольким запросам.
Порт у сервера случайный, поэтому дерево пересобирается на каждом запуске.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

#: Корень репозитория: скрипт запускается напрямую, `core.*` в `sys.path` сам не появится.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_http_server import DEFAULT_DELAY_MS, DelayHttpServer  # noqa: E402

from core.mdscan import ScanConfig, Scanner, ScanOrchestrator, ScanSummary  # noqa: E402
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft  # noqa: E402
from core.mdscan.enums.source_kind import SourceKind  # noqa: E402

#: Рабочий каталог замера — в `out/`, git его не трекает.
BENCH_DIR = ROOT / "out" / "hw01" / "bench" / "http"
DEFAULT_FILES = 300
DEFAULT_URLS = 2
DEFAULT_REPEAT = 3
#: Префиксы уникальных адресов: файл `i` ссылается на `/a<i>`, `/b<i>`, …
URL_PREFIXES = "abcdefgh"


class HttpBench:
    """Прогоны сканера по дереву с внешними ссылками на локальный сервер."""

    def __init__(
        self,
        base_url: str,
        files: int = DEFAULT_FILES,
        urls: int = DEFAULT_URLS,
        http_workers: int = 10,
    ) -> None:
        self._files = files
        self._urls = urls
        self._http_workers = http_workers
        self._tree = self._build(base_url)
        self._out_dir = BENCH_DIR / "out"
        self._scanner: Scanner = ScanOrchestrator()

    @property
    def tree(self) -> Path:
        """Каталог дерева замера."""
        return self._tree

    @property
    def requests_expected(self) -> int:
        """Сколько сетевых запросов должен сделать один прогон."""
        return self._files * self._urls

    def config(self, workers: int) -> ScanConfig:
        """Конфигурация: HTTP включён, прогресс/лог/консоль выключены."""
        draft = ConfigDraft.from_defaults()
        draft.assign("source.target", str(self._tree), SOURCE_CMDLINE)
        draft.assign(
            "source.targets_resolved", ((str(self._tree), SourceKind.LOCAL),), SOURCE_CMDLINE
        )
        draft.assign("scan.respect_gitignore", False, SOURCE_CMDLINE)
        draft.assign("workers.parse", workers, SOURCE_CMDLINE)
        draft.assign("http.enabled", True, SOURCE_CMDLINE)
        draft.assign("http.workers", self._http_workers, SOURCE_CMDLINE)
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
        """`repeat` прогонов; наружу — медиана, минимум, максимум, счётчики.

        Прогрева нет намеренно: время здесь определяют ответы сервера, а не кэш
        файловой системы, и лишний прогон стоит десятки секунд.
        """
        samples = [self.once(workers) for _ in range(repeat)]
        times = [seconds for seconds, _ in samples]
        summary = samples[-1][1]
        return {
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "files": summary.counters.get("md_files_total", 0.0),
            "links": summary.counters.get("links_total", 0.0),
            "broken": summary.counters.get("broken_total", 0.0),
        }

    # ── приватные хелперы ────────────────────────────────────────────────────

    def _build(self, base_url: str) -> Path:
        """Собрать дерево: `files` файлов по `urls` уникальных адресов в каждом."""
        if self._urls > len(URL_PREFIXES):
            raise ValueError(f"urls должно быть ≤ {len(URL_PREFIXES)}, получено {self._urls}")
        root = BENCH_DIR / "gen"
        root.mkdir(parents=True, exist_ok=True)
        for path in root.glob("*.md"):
            path.unlink()
        for index in range(self._files):
            (root / f"f{index:04d}.md").write_text(
                self._text(base_url, index), encoding="utf-8"
            )
        return root

    def _text(self, base_url: str, index: int) -> str:
        """Содержимое одного файла: заголовок и `urls` внешних ссылок."""
        links = "\n".join(
            f"- [{prefix}{index}]({base_url}/{prefix}{index})"
            for prefix in URL_PREFIXES[: self._urls]
        )
        return f"# file {index}\n\n{links}\n"


def main() -> None:
    """Разбор аргументов, прогоны и печать таблицы — единственный слой вывода."""
    parser = argparse.ArgumentParser(description="Замер speedup с HTTP (hw01, таск H-07)")
    parser.add_argument("--workers", default="1,5,10", help="список workers.parse через запятую")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help="прогонов на точку")
    parser.add_argument("--files", type=int, default=DEFAULT_FILES, help="файлов в дереве")
    parser.add_argument("--urls", type=int, default=DEFAULT_URLS, help="уникальных URL на файл")
    parser.add_argument("--delay-ms", type=int, default=DEFAULT_DELAY_MS, help="задержка ответа")
    parser.add_argument("--http-workers", type=int, default=10, help="семафор http.workers")
    args = parser.parse_args()

    server = DelayHttpServer(args.delay_ms)
    server.start()
    try:
        bench = HttpBench(server.base_url, args.files, args.urls, args.http_workers)
        print(
            f"дерево: {bench.tree.relative_to(ROOT).as_posix()} · "
            f"{args.files} файлов × {args.urls} URL = {bench.requests_expected} запросов · "
            f"задержка {args.delay_ms} мс · http.workers={args.http_workers}"
        )
        rows: dict[int, dict[str, float]] = {}
        for workers in (int(item) for item in args.workers.split(",")):
            server.reset()
            rows[workers] = bench.measure(workers, args.repeat)
            result = rows[workers]
            print(
                f"workers.parse={workers:<3} медиана {result['median']:7.3f} с "
                f"(min {result['min']:.3f} / max {result['max']:.3f}, прогонов {args.repeat}) · "
                f"ссылок {result['links']:.0f}, битых {result['broken']:.0f} · "
                f"запросов на сервере {server.hits} (пик {server.peak_concurrency})"
            )
        base = rows[min(rows)]["median"]
        print("speedup к 1 потоку:")
        for workers, result in rows.items():
            print(f"  {workers:<3} ×{base / result['median']:.2f}")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
