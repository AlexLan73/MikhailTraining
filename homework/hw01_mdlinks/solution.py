"""Метрики ДЗ hw01 — логика, специфичная только для этого задания (правило 06).

Математики здесь нет (правило 07): счётчики §9.1 приходят из `ScanSummary`, качество
§9.2 — из `core.metrics`, параллельность §9.3 — из двух прогонов набора B
(`workers.parse` = 1 и N). Класс лишь связывает готовое и отдаёт `dict[str, float]`.

Качество извлечения считается **отдельным** проходом по дереву: `Scanner.scan` отдаёт
наружу только `ScanSummary`, а `MdFileResult`-ы после прогона недоступны (см.
`ScanOrchestrator._shutdown`). Проход — тонкий слой поверх тех же классов
`core.mdscan.parsing`, что зовёт parse-worker.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.mdscan import ScanConfig, Scanner, ScanOrchestrator, ScanSummary
from core.mdscan.config.config_draft import SOURCE_CMDLINE, ConfigDraft
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.errors import MarkdownReadError
from core.mdscan.parsing.link_classifier import LinkClassifier
from core.mdscan.parsing.markdown_it_link_extractor import MarkdownItLinkExtractor
from core.mdscan.parsing.markdown_reader import MarkdownReader
from core.metrics import accuracy, f1_score
from homework.hw01_mdlinks.support.expectations import ReferenceTree

logger = logging.getLogger("homework.hw01")

#: Расширения, которые сканер считает Markdown (`scan.md_extensions` по умолчанию).
MD_SUFFIXES = frozenset({".md", ".markdown"})

#: Имя потока разбора в логе (`LogFormat.PATTERN`, поле 3) — по ним считается `workers_used`.
PARSE_THREAD = re.compile(r"^parse-\d+$")

#: Тройка эталона извлечения: путь файла от корня дерева, цель ссылки, категория.
Triple = tuple[str, str, LinkKind]


class Hw01Metrics:
    """Метрики hw01: операционные, качество извлечения, параллельность.

    Каждый прогон пишет лог и отчёт в свой подкаталог `out/hw01/<run_name>/`.
    """

    def __init__(self, out_dir: Path) -> None:
        self._out_dir = Path(out_dir)
        self._scanner: Scanner = ScanOrchestrator()

    def scan(self, target: Path, run_name: str, parse_workers: int) -> ScanSummary:
        """Один прогон сканера по каталогу `target`; наружу — счётчики §9.1."""
        summary = self._scanner.scan(self._config(target, run_name, parse_workers))
        logger.info(
            "прогон %s: файлов %.0f, ссылок %.0f, битых %.0f, за %.2f с, код %d",
            run_name, summary.counters.get("md_files_total", 0.0),
            summary.counters.get("links_total", 0.0), summary.counters.get("broken_total", 0.0),
            summary.duration_sec, summary.exit_code,
        )
        return summary

    def quality(self, tree: ReferenceTree) -> dict[str, float]:
        """Качество на наборе A (§9.2): `extract_f1` и `classify_accuracy`."""
        found = self._found_links(tree.root)
        expected = tree.expectations.links
        universe = sorted(found | expected, key=str)
        expected_kind = {(rel, target): kind for rel, target, kind in expected}
        found_kind = {(rel, target): kind for rel, target, kind in found}
        shared = sorted(set(expected_kind) & set(found_kind), key=str)
        if not shared:
            raise ValueError(f"в дереве {tree.root} не найдено ни одной ссылки эталона")
        logger.info("качество набора A: найдено %d ссылок, эталон %d", len(found), len(expected))
        return {
            "extract_f1": f1_score(
                [1 if item in expected else 0 for item in universe],
                [1 if item in found else 0 for item in universe],
            ),
            "classify_accuracy": accuracy(
                [expected_kind[key] for key in shared], [found_kind[key] for key in shared]
            ),
        }

    def parallel(self, gen_root: Path, workers: int) -> dict[str, float]:
        """Параллельность на наборе B (§9.3): один поток разбора против `workers`."""
        serial = self.scan(gen_root, "gen_serial", 1).duration_sec
        parallel = self.scan(gen_root, "gen_parallel", workers).duration_sec
        speedup = serial / parallel if parallel > 0 else 0.0
        used = self._workers_used(self._out_dir / "gen_parallel")
        return {
            "duration_serial_sec": serial,
            "duration_parallel_sec": parallel,
            "speedup": speedup,
            "parallel_efficiency": speedup / workers if workers > 0 else 0.0,
            "workers_used": used if used > 0 else float(workers),
        }

    # ── приватные хелперы ────────────────────────────────────────────────────

    def _config(self, target: Path, run_name: str, parse_workers: int) -> ScanConfig:
        """Конфигурация прогона: цель — каталог, сеть и прогресс выключены (§0.3).

        `scan.respect_gitignore: false` обязателен: деревья лежат в `out/`, который
        перечислен в `.gitignore`, и `git ls-files` их бы не отдал.
        """
        run_dir = self._out_dir / run_name
        draft = ConfigDraft.from_defaults()
        draft.assign("source.target", str(target), SOURCE_CMDLINE)
        draft.assign("source.targets_resolved", ((str(target), SourceKind.LOCAL),), SOURCE_CMDLINE)
        draft.assign("scan.respect_gitignore", False, SOURCE_CMDLINE)
        draft.assign("workers.parse", parse_workers, SOURCE_CMDLINE)
        draft.assign("http.enabled", False, SOURCE_CMDLINE)
        draft.assign("progress.enabled", False, SOURCE_CMDLINE)
        draft.assign("logging.dir", str(run_dir), SOURCE_CMDLINE)
        draft.assign("report.dir", str(run_dir), SOURCE_CMDLINE)
        draft.assign("run.fail_on_broken", False, SOURCE_CMDLINE)
        draft.assign("report.console", False, SOURCE_CMDLINE)  # сводку печатает run_hw.py, а не сканер
        return ScanConfig.from_draft(draft)

    @staticmethod
    def _found_links(root: Path) -> set[Triple]:
        """Ссылки дерева теми же классами, что и parse-worker: `(rel_path, target, kind)`."""
        reader = MarkdownReader()
        extractor = MarkdownItLinkExtractor()
        classifier = LinkClassifier.default()
        found: set[Triple] = set()
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MD_SUFFIXES:
                continue
            rel = path.relative_to(root).as_posix()
            try:
                text = reader.read(path)
            except MarkdownReadError as exc:
                logger.warning("файл не прочитан, пропущен: %s (%s)", rel, exc)
                continue
            found.update((rel, one.target, classifier.classify(one)) for one in extractor.extract(text))
        return found

    @staticmethod
    def _workers_used(run_dir: Path) -> float:
        """Сколько потоков разбора реально работало — по именам в свежем логе прогона."""
        logs = sorted(run_dir.glob("*.log"), key=lambda path: path.stat().st_mtime)
        if not logs:
            logger.warning("лог прогона не найден в %s — workers_used взят из конфигурации", run_dir)
            return 0.0
        names: set[str] = set()
        for line in logs[-1].read_text(encoding="utf-8", errors="replace").splitlines():
            fields = [field.strip() for field in line.split("|")]
            if len(fields) > 2 and PARSE_THREAD.match(fields[2]):
                names.add(fields[2])
        return float(len(names))
