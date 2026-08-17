"""H-08 — аварийные сценарии: прерывание, нет прав на запись, пустая цель, огромный файл, `429`.

Сеть здесь не нужна: HTTP выключен (`http.enabled: false`), GitHub раскрывается
заглушкой `http_get`, прерывание поднимается тем же исключением, каким его поднимает
обработчик SIGINT (`KeyboardInterrupt` в главном потоке).

Соответствие сценариям таска H-08:

| # | сценарий | тест |
|---|---|---|
| 1 | прерывание `Ctrl+C` | `test_interrupt_*`, `test_cancel_*`, `test_main_translates_interrupt_*` |
| 3 | GitHub `429` | `test_org_rate_limit_*` (полный прогон; разбор ответа — `test_source.py`) |
| 5 | нет прав на запись | `test_report_dir_not_a_directory_*`, `test_report_write_failure_*` |
| 6 | пустая цель | `test_empty_target_*` |
| 7 | огромный файл | `test_huge_markdown_file_*` |

Сценарии 2 (нет сети) и 4 (битый репозиторий) — ручные, см.
`MemoryBank/specs/hw01_h08_resilience_2026-08-17.md`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pytest

from core.mdscan.checking.checker_factory import CheckerFactory
from core.mdscan.config.config_draft import ConfigDraft
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.models.md_task import MdTask
from core.mdscan.models.repo_info import RepoInfo
from core.mdscan.models.scan_summary import ScanSummary
from core.mdscan.parsing.markdown_it_heading_source import MarkdownItHeadingSource
from core.mdscan.runtime import scan_orchestrator
from core.mdscan.runtime.null_notifier import NullNotifier
from core.mdscan.runtime.pipeline_runner import PipelineRunner
from core.mdscan.runtime.queues import TaskQueue
from core.mdscan.runtime.scan_orchestrator import INTERRUPTED_CODE, ScanOrchestrator
from core.mdscan.runtime.sentinels import END_DISCOVERY
from core.mdscan.source.git_adapter import GitAdapter
from core.mdscan.source.source_factory import SourceFactory

#: Потолок ожидания в тестах с потоками: `join` без таймаута вешает набор, а не падает.
WAIT_SEC = 30.0

#: Имена потоков прогона: после прерывания ни одного остаться не должно (инвариант 11).
OUR_THREAD_PREFIXES = ("parse-", "discover", "collector", "progress")

#: Размер «огромного» файла сценария 7 (ровно 10 МБ полезного текста).
HUGE_FILE_BYTES = 10 * 1024 * 1024

#: Время сброса лимита GitHub в заглушке `429` (epoch): проверяется в тексте ошибки.
RATE_LIMIT_RESET = 1_800_000_000


# ── вспомогательное ──────────────────────────────────────────────────────────


def _config(target: Path, tmp_path: Path, overrides: Mapping[str, object] | None = None) -> ScanConfig:
    """Конфигурация прогона: без сети, без прогресса и консоли, вывод — в `tmp_path`."""
    draft = ConfigDraft.from_defaults()
    draft.assign("source.target", str(target), "c")
    draft.assign("source.targets_resolved", ((str(target), SourceKind.LOCAL),), "c")
    draft.assign("http.enabled", False, "c")
    draft.assign("progress.enabled", False, "c")
    draft.assign("report.console", False, "c")
    draft.assign("logging.dir", str(tmp_path / "logs"), "c")
    draft.assign("report.dir", str(tmp_path / "reports"), "c")
    for field, value in (overrides or {}).items():
        draft.assign(field, value, "c")
    return ScanConfig.from_draft(draft)


def _tree(tmp_path: Path, name: str = "tree") -> Path:
    """Минимальная цель: один `.md` с живой и битой ссылкой."""
    root = tmp_path / name
    root.mkdir(parents=True)
    (root / "README.md").write_text(
        "# Раздел\n\n[сам файл](README.md)\n[нет файла](missing.md)\n", encoding="utf-8"
    )
    return root


def _log_text(tmp_path: Path) -> str:
    """Текст единственного лога прогона (перехватчик pytest его не видит: `propagate=False`)."""
    logs = sorted((tmp_path / "logs").glob("*.log"))
    assert len(logs) == 1, f"ожидался один лог, найдено: {logs}"
    return logs[0].read_text(encoding="utf-8")


def _reports(tmp_path: Path) -> list[Path]:
    """Файлы отчёта прогона (их может не быть — прерванный прогон отчёт не пишет)."""
    directory = tmp_path / "reports"
    return sorted(directory.glob("*.md")) if directory.is_dir() else []


def _our_threads() -> list[str]:
    """Живые потоки прогона (главный и чужие не считаются)."""
    return [
        thread.name for thread in threading.enumerate()
        if thread.name.startswith(OUR_THREAD_PREFIXES)
    ]


class _StubFactory:
    """Двойник `SourceFactory`: отдаёт заранее собранные источники, никуда не ходит."""

    def __init__(self, sources: Sequence[object]) -> None:
        self._sources = list(sources)

    def for_config(self, config: ScanConfig) -> list[object]:
        """Тот же контракт, что у настоящей фабрики: список источников по конфигурации."""
        return list(self._sources)


class _InterruptingSource:
    """Источник, который прерывается на обходе: так ведёт себя `Ctrl+C` в стадии 1."""

    def __init__(self, repos: Sequence[RepoInfo] = ()) -> None:
        self._repos = list(repos)
        self.cleaned = False

    def repositories(self) -> Iterable[RepoInfo]:
        """Отдать заготовленные репозитории и прерваться (`KeyboardInterrupt`)."""
        yield from self._repos
        raise KeyboardInterrupt

    def cleanup(self) -> None:
        """Уборка обязана случиться даже после прерывания (фаза 3)."""
        self.cleaned = True


def _use_sources(monkeypatch: pytest.MonkeyPatch, *sources: object) -> None:
    """Подменить фабрику источников оркестратора на заглушку с готовыми источниками."""
    monkeypatch.setattr(scan_orchestrator, "SourceFactory", lambda git: _StubFactory(sources))


def _pipeline(tmp_path: Path, workers: int) -> PipelineRunner:
    """Конвейер без запуска потоков — для проверки `cancel()` в изоляции."""
    config = _config(_tree(tmp_path), tmp_path, {"workers.parse": workers})
    notifier = NullNotifier()
    checkers = CheckerFactory(config, MarkdownItHeadingSource(config.parser.preset), notifier)
    return PipelineRunner(config, notifier, checkers)


def _task_queue(runner: PipelineRunner) -> TaskQueue:
    """Очередь задач конвейера: белый ящик — тест проверяет инвариант её баланса."""
    return runner._tasks  # noqa: SLF001 — иначе `cancel()` не проверить в изоляции


def _joined(target: TaskQueue) -> bool:
    """`queue.join()` с таймаутом: несбалансированный `task_done()` даёт `False`, не зависание."""
    done = threading.Event()

    def wait() -> None:
        target.join()
        done.set()

    watcher = threading.Thread(target=wait, name="join-watch", daemon=True)
    watcher.start()
    watcher.join(timeout=WAIT_SEC)
    return done.is_set()


# ── сценарий 5: нет прав на запись ───────────────────────────────────────────


@pytest.mark.parametrize(
    "nested",
    [False, True],
    ids=["report.dir=существующий файл", "report.dir=путь внутри файла"],
)
def test_report_dir_not_a_directory_gives_code_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], nested: bool
) -> None:
    """Сценарий 5: каталог отчёта недоступен → код 2 и понятный текст без трейсбека (V9)."""
    from core.mdscan.__main__ import main

    target = _tree(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("это файл, а не каталог", encoding="utf-8")
    report_dir = blocker / "reports" if nested else blocker
    monkeypatch.chdir(tmp_path)

    code = main([
        str(target),
        f"-report.dir:{report_dir}",
        f"-logging.dir:{tmp_path / 'logs'}",
        "-http.enabled:false",
        "-progress.enabled:false",
    ])

    captured = capsys.readouterr()
    assert code == 2
    assert "report.dir" in captured.err
    assert "Traceback" not in captured.err and "Traceback" not in captured.out
    assert _reports(tmp_path) == []


def test_report_write_failure_after_validation_gives_code_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сценарий 5 (🔧 р6): запись отчёта сорвалась **после** проверок → код 3 и `CRITICAL`.

    Каталог, проверенный V9/V10, может пропасть или потерять права уже во время
    прогона. Само удаление каталога воспроизвести нельзя — фаза 2 создаёт его заново
    (`report_file.parent.mkdir`), поэтому отказ ФС подставляется на запись файла.
    """
    target = _tree(tmp_path)
    original = Path.write_text

    def refuse_markdown(self: Path, *args: object, **kwargs: object) -> int:
        if self.suffix == ".md":
            raise PermissionError(13, "каталог отчёта пропал после валидации")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", refuse_markdown)

    summary = ScanOrchestrator().scan(_config(target, tmp_path))

    assert summary.exit_code == 3
    assert summary.counters["md_files_total"] == pytest.approx(1.0)  # счётчики не потеряны
    log = _log_text(tmp_path)
    assert "CRITICAL" in log
    assert "отчёт не записан" in log
    assert _reports(tmp_path) == []


# ── сценарий 6: пустая цель ──────────────────────────────────────────────────


def test_empty_target_gives_zero_counters_and_report(tmp_path: Path) -> None:
    """Сценарий 6: каталог без `.md` → код 0, нулевые счётчики, отчёт на месте, ошибок нет."""
    target = tmp_path / "empty"
    (target / "docs").mkdir(parents=True)
    (target / "notes.txt").write_text("не markdown\n", encoding="utf-8")

    summary = ScanOrchestrator().scan(_config(target, tmp_path))

    assert summary.exit_code == 0
    for counter in ("md_files_total", "links_total", "broken_total", "files_ok", "files_failed"):
        assert summary.counters[counter] == pytest.approx(0.0), counter
    assert len(_reports(tmp_path)) == 1
    log = _log_text(tmp_path)
    assert "ERROR" not in log and "CRITICAL" not in log
    assert _our_threads() == []


# ── сценарий 7: огромный файл ────────────────────────────────────────────────


def test_huge_markdown_file_is_scanned_and_timed(tmp_path: Path) -> None:
    """Сценарий 7: `.md` на 10 МБ разбирается целиком, без ошибок, время попадает в отчёт."""
    target = tmp_path / "huge"
    target.mkdir()
    huge = target / "huge.md"
    _write_huge(huge, HUGE_FILE_BYTES)
    assert huge.stat().st_size >= HUGE_FILE_BYTES

    started = time.perf_counter()
    summary = ScanOrchestrator().scan(_config(target, tmp_path))
    elapsed = time.perf_counter() - started

    assert summary.exit_code == 0
    assert summary.counters["md_files_total"] == pytest.approx(1.0)
    assert summary.counters["files_failed"] == pytest.approx(0.0)
    assert summary.counters["links_total"] > 100
    assert summary.counters["duration_sec"] > 0.0
    assert summary.counters["duration_sec"] <= elapsed
    report = _reports(tmp_path)
    assert len(report) == 1
    assert "длительность, с" in report[0].read_text(encoding="utf-8")


def _write_huge(path: Path, size: int) -> None:
    """Файл не меньше `size` байт: разделы, абзацы и по две ссылки на раздел."""
    filler = "лорем ипсум долор сит амет " * 40 + "\n\n"
    parts = ["# Огромный файл\n\n"]
    grown = len(parts[0].encode("utf-8"))
    index = 0
    while grown < size:
        index += 1
        chunk = (
            f"## Раздел {index}\n\n- [сам файл](huge.md)\n- [якорь](#раздел-{index})\n\n"
            + filler * 10
        )
        parts.append(chunk)
        grown += len(chunk.encode("utf-8"))
    path.write_text("".join(parts), encoding="utf-8")


# ── сценарий 3: GitHub 429 ───────────────────────────────────────────────────


def test_org_rate_limit_gives_code_three_with_reset_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сценарий 3: `429` на раскрытии организации → код 3, время сброса в логе, отчёта нет.

    Проверяется весь прогон, а не только источник: молчаливый пустой отчёт с кодом 0
    был бы худшим исходом — человек решил бы, что в организации нет `.md`.
    """
    def refuse_gh(args: Sequence[str]) -> str:
        raise AssertionError("при discovery=api `gh` вызываться не должен")

    def rate_limited(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
        return 429, "{}", {
            "X-RateLimit-Reset": str(RATE_LIMIT_RESET),
            "X-RateLimit-Remaining": "0",
        }

    monkeypatch.setattr(
        scan_orchestrator,
        "SourceFactory",
        lambda git: SourceFactory(git, run_gh=refuse_gh, http_get=rate_limited),
    )
    config = _config(_tree(tmp_path), tmp_path, {
        "source.target": "https://github.com/org",
        "source.targets_resolved": (("https://github.com/org", SourceKind.GITHUB_ORG),),
        "source.discovery": "api",
        "source.clone_dir": str(tmp_path / "clones"),
    })

    summary = ScanOrchestrator().scan(config)

    assert summary.exit_code == 3
    log = _log_text(tmp_path)
    assert "CRITICAL" in log
    assert "rate limit" in log
    assert "сброс в" in log  # человеку видно, когда лимит откроется
    assert _reports(tmp_path) == []
    assert _our_threads() == []


def test_org_rate_limit_message_names_the_organization(tmp_path: Path) -> None:
    """Сценарий 3: тот же `429` на уровне источника — сообщение адресное (дополнение к T-08)."""
    from core.mdscan.errors import GitHubDiscoveryError
    from core.mdscan.source.github_org_source import GitHubOrgSource

    def rate_limited(url: str, headers: Mapping[str, str]) -> tuple[int, str, Mapping[str, str]]:
        return 429, "{}", {"X-RateLimit-Reset": str(RATE_LIMIT_RESET), "X-RateLimit-Remaining": "0"}

    config = _config(_tree(tmp_path), tmp_path, {
        "source.discovery": "api",
        "source.clone_dir": str(tmp_path / "clones"),
    })
    source = GitHubOrgSource(
        "https://github.com/dsp-gpu", config.source, lambda args: "", rate_limited, GitAdapter()
    )

    with pytest.raises(GitHubDiscoveryError, match="dsp-gpu") as failure:
        list(source.repositories())

    assert "source.repositories" in str(failure.value)  # подсказка, как обойти лимит


# ── сценарий 1: прерывание пользователем ─────────────────────────────────────


def test_interrupt_on_discovery_gives_interrupted_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сценарий 1: `KeyboardInterrupt` в главном потоке → код 130, потоки погашены, отчёта нет."""
    target = _tree(tmp_path)
    source = _InterruptingSource([RepoInfo(root=target)])
    _use_sources(monkeypatch, source)

    started = time.perf_counter()
    summary = ScanOrchestrator().scan(_config(target, tmp_path))
    elapsed = time.perf_counter() - started

    assert summary.exit_code == INTERRUPTED_CODE
    assert elapsed < WAIT_SEC  # прерывание не превращается в зависание
    assert _our_threads() == []  # инвариант 11 держится и на прерывании
    assert _reports(tmp_path) == []  # отчёт по неполным данным не пишется
    assert source.cleaned  # фаза 3 (уборка клонов) выполнена
    log = _log_text(tmp_path)
    assert "прерван" in log
    assert "CRITICAL" in log


def test_interrupt_keeps_counters_of_parsed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Прерывание не теряет уже посчитанное: файл, разобранный до `Ctrl+C`, есть в счётчиках."""
    target = _tree(tmp_path)
    _use_sources(monkeypatch, _InterruptingSource([RepoInfo(root=target)]))

    summary = ScanOrchestrator().scan(_config(target, tmp_path, {"workers.parse": 1}))

    assert summary.exit_code == INTERRUPTED_CODE
    assert summary.counters["md_files_total"] == pytest.approx(1.0)
    assert summary.counters["links_total"] >= 0.0


def test_cancel_drops_pending_tasks_and_keeps_sentinels(tmp_path: Path) -> None:
    """`cancel()` снимает задачи, сохраняет сентинелы и не ломает баланс `task_done()`.

    Съеденный сентинел оставил бы parse-worker навсегда на `get()` (инвариант 19),
    а лишний `task_done()` — сорвал бы `TaskQueue.join()` (инвариант 5).
    """
    runner = _pipeline(tmp_path, workers=3)
    tasks = _task_queue(runner)
    repo = RepoInfo(root=tmp_path)
    for number in range(5):
        tasks.put(MdTask(repo=repo, md_file=tmp_path / f"note_{number}.md"))
    for _ in range(3):
        tasks.put(END_DISCOVERY)

    dropped = runner.cancel()

    assert dropped == 5
    assert runner.interrupted
    remaining = [tasks.get_nowait() for _ in range(tasks.qsize())]
    assert remaining == [END_DISCOVERY] * 3  # каждому воркеру остался свой сентинел
    for _ in remaining:
        tasks.task_done()
    assert _joined(tasks), "task_done() не сбалансирован: join() не вернулся"


def test_cancel_on_empty_queue_drops_nothing(tmp_path: Path) -> None:
    """`cancel()` на пустой очереди безопасен: 0 отброшенных, `join()` возвращается."""
    runner = _pipeline(tmp_path, workers=2)

    assert runner.cancel() == 0
    assert _joined(_task_queue(runner))


def test_main_translates_interrupt_into_code_130_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Ctrl+C` в фазе 0/1 доходит до `main()` как код 130 и одна строка, а не трейсбек."""
    from core.mdscan.__main__ import main

    def interrupt(self: ScanOrchestrator, config: ScanConfig) -> ScanSummary:
        raise KeyboardInterrupt

    monkeypatch.setattr(ScanOrchestrator, "scan", interrupt)
    target = _tree(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = main([
        str(target),
        f"-logging.dir:{tmp_path / 'logs'}",
        f"-report.dir:{tmp_path / 'reports'}",
        "-http.enabled:false",
        "-progress.enabled:false",
    ])

    captured = capsys.readouterr()
    assert code == INTERRUPTED_CODE
    assert "Ctrl+C" in captured.err
    assert "Traceback" not in captured.err
