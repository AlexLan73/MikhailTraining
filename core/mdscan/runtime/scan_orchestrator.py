"""Оркестратор прогона: фазы 0…3 и связывание всех модулей (Facade + Controller).

Это Composition Root прогона (правило 09 п. 5): единственное место, где конкретные
классы встречаются друг с другом. Порядок — часть 2, D1/D6 и часть 1, D4:

```text
фаза 1  логгер → прогресс → чекеры → конвейер → обход → завершение по сентинелам
фаза 2  отчёт в файл → таблица в stdout → итоги в лог
фаза 3  finally: прогресс погашен, клоны удалены, лог дописан
```

Ошибка записи отчёта **не** выпускается наружу исключением: она превращается в
`ScanSummary(exit_code=3)` с записью `CRITICAL` (зафиксированный выбор из двух,
разрешённых ТЗ) — счётчики прогона при этом сохраняются и доходят до ДЗ (T-14).

Класс же реализует `ProgressSource` (T-11): срез счётчиков берётся у конвейера,
поэтому поток прогресса не знает ни про очереди, ни про статистику.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from ..checking.checker_factory import CheckerFactory
from ..config.scan_config import ScanConfig
from ..log_setup.log_naming import LogNaming
from ..log_setup.logging_setup import LoggingSetup
from ..models.md_file_result import MdFileResult
from ..models.progress_snapshot import ProgressSnapshot
from ..models.scan_summary import ScanSummary
from ..parsing.markdown_it_heading_source import MarkdownItHeadingSource
from ..reporting.markdown_report_builder import MarkdownReportBuilder
from ..reporting.renderer_factory import RendererFactory
from ..source.git_adapter import GitAdapter
from ..source.repository_source import RepositorySource
from ..source.source_factory import SourceFactory
from .notifier import Notifier
from .null_notifier import NullNotifier
from .pipeline_runner import PipelineRunner
from .progress_factory import ProgressFactory
from .progress_reporter import ProgressReporter

logger = logging.getLogger("core.mdscan.runtime.orchestrator")

#: Код внутренней ошибки (часть 2 §1.4): git недоступен, отчёт не записан, сбой прогона.
INTERNAL_ERROR_CODE = 3

#: Пустой срез: прогресс может спросить счётчики до старта конвейера.
_NO_PROGRESS = ProgressSnapshot(
    repos_total=0, repos_done=0, md_found=0, parsed=0,
    task_qsize=0, result_qsize=0, links=0, broken=0,
)


class ScanOrchestrator:
    """Реализация `Scanner`: один вызов `scan()` — один полный прогон."""

    def __init__(self) -> None:
        self._pipeline: PipelineRunner | None = None

    def snapshot(self) -> ProgressSnapshot:
        """`ProgressSource` (T-11): счётчики конвейера; до старта — нули."""
        pipeline = self._pipeline
        return _NO_PROGRESS if pipeline is None else pipeline.snapshot()

    def scan(self, config: ScanConfig) -> ScanSummary:
        """Прогон целиком; наружу выходит только `ScanSummary` (исключений нет)."""
        started_at = datetime.now()
        clock = time.perf_counter()
        scope = self._scope(config)
        report_file = Path(config.report.dir) / LogNaming().build(scope, started_at, "md")
        setup = LoggingSetup()
        setup.start(self._log_file(config, scope, started_at), config.logging.level,
                    self._header(config, scope, started_at, report_file))
        reporter = ProgressFactory().create(config, self, sys.stderr)
        notifier: Notifier = reporter if reporter is not None else NullNotifier()
        sources: list[RepositorySource] = []
        try:
            pipeline = self._pipeline = PipelineRunner(config, notifier, self._checkers(config, notifier))
            pipeline.start()
            if reporter is not None:
                reporter.start()
            sources = SourceFactory(GitAdapter()).for_config(config)
            pipeline.run(sources)
            summary = pipeline.stats.summary(time.perf_counter() - clock, config.run.fail_on_broken)
            return self._publish(config, started_at, report_file, pipeline.results, summary)
        except Exception as exc:  # noqa: BLE001 — прогон не бросает наружу, а возвращает код 3
            logger.critical("прогон прерван: %s: %s", type(exc).__name__, exc, exc_info=True)
            return ScanSummary(counters={}, duration_sec=time.perf_counter() - clock,
                               exit_code=INTERNAL_ERROR_CODE)
        finally:
            self._shutdown(reporter, sources, setup)

    def _publish(self, config: ScanConfig, started_at: datetime, report_file: Path,
                 results: Sequence[MdFileResult], summary: ScanSummary) -> ScanSummary:
        """Фаза 2: файл отчёта, таблица в stdout, итоги в лог (инвариант 25)."""
        try:
            text = MarkdownReportBuilder(config, started_at).build(results, summary)
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — отчёт не записан = внутренняя ошибка (код 3)
            logger.critical("отчёт не записан: %s (%s: %s)", report_file, type(exc).__name__, exc,
                            exc_info=True)
            return ScanSummary(counters=summary.counters, duration_sec=summary.duration_sec,
                               exit_code=INTERNAL_ERROR_CODE)
        logger.info("отчёт записан: %s", report_file)
        if config.report.console:  # 🔧 р5: выключатель консольной сводки
            RendererFactory().create().render(results, summary)
        counters = summary.counters
        logger.info(
            "итоги: файлов %.0f, ссылок %.0f, битых %.0f, за %.2f с, код %d",
            counters.get("md_files_total", 0.0), counters.get("links_total", 0.0),
            counters.get("broken_total", 0.0), summary.duration_sec, summary.exit_code,
        )
        return summary

    def _shutdown(self, reporter: ProgressReporter | None, sources: Sequence[RepositorySource],
                  setup: LoggingSetup) -> None:
        """Фаза 3: гасим прогресс, убираем клоны, дописываем лог — что бы ни случилось."""
        self._pipeline = None
        try:
            if reporter is not None:
                reporter.stop()
            for source in sources:
                self._cleanup(source)
        finally:
            setup.stop()

    @staticmethod
    def _cleanup(source: RepositorySource) -> None:
        """Уборка одного источника: её сбой не должен помешать уборке остальных."""
        try:
            source.cleanup()
        except Exception as exc:  # noqa: BLE001 — уборка «best effort» (правило 11)
            logger.error("источник не убран: %s: %s", type(exc).__name__, exc, exc_info=True)

    @staticmethod
    def _checkers(config: ScanConfig, notifier: Notifier) -> CheckerFactory:
        """Единственная на прогон фабрика чекеров (общие семафор и кэши, инвариант 22)."""
        return CheckerFactory(config, MarkdownItHeadingSource(config.parser.preset), notifier)

    @staticmethod
    def _log_file(config: ScanConfig, scope: str, started_at: datetime) -> Path | None:
        """Путь лога прогона; `logging.enabled: false` → `None` (файл не создаётся)."""
        if not config.logging.enabled:
            return None
        return Path(config.logging.dir) / LogNaming().build(scope, started_at, "log")

    @staticmethod
    def _scope(config: ScanConfig) -> str:
        """Имя прогона (D9): каталог, репозиторий или организация; цели из yaml → `yaml`."""
        address = config.source.target.strip()
        tail = address.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return tail.removesuffix(".git") or "yaml"

    @staticmethod
    def _header(config: ScanConfig, scope: str, started_at: datetime,
                report_file: Path) -> Mapping[str, str]:
        """Шапка файла лога (D9): по ней видно, что именно и как сканировалось."""
        targets = ", ".join(address for address, _ in config.source.targets_resolved)
        return {
            "scope": f"{scope} ({config.source.kind})",
            "started": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "input": targets or config.source.target or "-",
            "workers": (f"discover={config.workers.discover} parse={config.workers.parse} "
                        f"http={config.http.workers}"),
            "checks": (f"local={config.checks.local} anchors={config.checks.anchors} "
                       f"http={config.http.enabled} nested={config.scan.include_nested_repos}"),
            "report": str(report_file),
        }
