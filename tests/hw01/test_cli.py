"""Тесты T-05 — CLI: разбор аргументов и цепочка валидации V1…V10.

Номера тестов соответствуют пунктам «Тесты» таска T-05
(`MemoryBank/tasks/TASK_hw01_modules_T01-T15.md`); закон CLI — часть 2 §1.1, порядок
правил — §1.3, коды возврата — §1.4.

Все тесты работают в `tmp_path` (`monkeypatch.chdir`): относительные `logging.dir` и
`report.dir` из значений по умолчанию создаются внутри временного каталога, репозиторий
тесты не трогают. Сеть не нужна: URL только классифицируются, никто по ним не ходит.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from core.mdscan.cli.argument_parser import ArgumentParser
from core.mdscan.cli.validation.chain import ValidationChain
from core.mdscan.cli.validation.rule_arg_count import ArgCountRule
from core.mdscan.cli.validation.rule_first_arg_is_target import FirstArgIsTargetRule
from core.mdscan.cli.validation.rule_git_repository import GitRepositoryRule
from core.mdscan.cli.validation.rule_output_dir import OutputDirRule
from core.mdscan.cli.validation.rule_override_syntax import OverrideSyntaxRule
from core.mdscan.cli.validation.rule_path_normalization import PathNormalizationRule
from core.mdscan.cli.validation.rule_path_readable import PathReadableRule
from core.mdscan.cli.validation.rule_target_kind import TargetKindRule
from core.mdscan.cli.validation.rule_write_permission import WritePermissionRule
from core.mdscan.cli.validation.validation_context import ValidationContext
from core.mdscan.cli.validation.validation_result import ValidationResult
from core.mdscan.config.config_draft import ConfigDraft
from core.mdscan.config.config_printer import ConfigPrinter
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.enums.source_kind import SourceKind

_CLI_LOGGER = "core.mdscan.cli"


def _context(argv: Sequence[str]) -> ValidationContext:
    """Контекст цепочки: разобранный `argv` + черновик из значений по умолчанию."""
    return ValidationContext(
        args=ArgumentParser().parse(list(argv)), draft=ConfigDraft.from_defaults()
    )


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Каталог запуска — временный: `out/hw01` создаётся внутри него, а не в репозитории."""
    monkeypatch.chdir(tmp_path)
    return tmp_path.resolve()


@pytest.fixture
def chain() -> ValidationChain:
    return ValidationChain.default()


# --- 1. Без аргументов -------------------------------------------------------------------


def test_1_no_arguments_request_config_print(workdir: Path, chain: ValidationChain) -> None:
    """Аргументов нет → справка и код 0; конфигурация печатается `ConfigPrinter`."""
    ctx = _context([])

    result = chain.run(ctx)

    assert ctx.args.help_requested is True
    assert ctx.args.target is None
    assert result == ValidationResult(ok=True, exit_code=0, message="")
    text = ConfigPrinter().render(ScanConfig.from_draft(ctx.draft), ctx.draft.sources)
    assert "ИСПОЛЬЗОВАНИЕ:" in text


# --- 2. Справка --------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["-h", "--help", "-?"], ids=["dash-h", "long", "question"])
def test_2_help_token_equals_no_arguments(
    workdir: Path, chain: ValidationChain, token: str
) -> None:
    """`-h` / `--help` / `-?` первым аргументом = запуск без аргументов (исключение Alex)."""
    ctx = _context([token])

    result = chain.run(ctx)

    assert ctx.args.help_requested is True
    assert ctx.args.target is None
    assert result.ok is True
    assert result.exit_code == 0


def test_2_help_still_applies_overrides(workdir: Path, chain: ValidationChain) -> None:
    """`-h -workers.parse:8` → печатается конфигурация с уже применённым значением (V3)."""
    ctx = _context(["-h", "-workers.parse:8"])

    assert chain.run(ctx).ok is True
    assert ctx.draft.value_at("workers.parse") == 8
    assert ctx.draft.sources["workers.parse"] == "c"


# --- 3. Четыре ветки цели ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        pytest.param("git@github.com:dsp-gpu/radar.git", SourceKind.REMOTE_REPO, id="ssh-repo"),
        pytest.param(
            "https://github.com/dsp-gpu/radar.git", SourceKind.REMOTE_REPO, id="https-repo"
        ),
        pytest.param("https://github.com/dsp-gpu", SourceKind.GITHUB_ORG, id="github-org"),
    ],
)
def test_3_url_targets_classified(
    workdir: Path, chain: ValidationChain, address: str, expected: SourceKind
) -> None:
    """URL репозитория и URL организации различаются (ветки 2 и 3 закона CLI)."""
    ctx = _context([address])

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == ((address, expected),)
    assert ctx.draft.value_at("source.target") == address


def test_3_local_directory_target(workdir: Path, chain: ValidationChain) -> None:
    """Существующий каталог → ветка `local`, адрес абсолютный."""
    ctx = _context([str(workdir)])

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == ((str(workdir), SourceKind.LOCAL),)


def test_3_yaml_target_taken_from_config(workdir: Path, chain: ValidationChain) -> None:
    """Слово `yaml` → цель берётся из `source.target` конфигурации."""
    ctx = _context(["yaml"])
    ctx.draft.assign("source.target", str(workdir), "y")

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == ((str(workdir), SourceKind.LOCAL),)


def test_3_ambiguous_yaml_directory_resolved_by_kind(
    workdir: Path, chain: ValidationChain
) -> None:
    """Каталог с именем `yaml` сканируется через явный `-source.kind:local` (часть 2 §1.1.1)."""
    (workdir / "yaml").mkdir()
    ctx = _context(["yaml", "-source.kind:local"])

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == ((str(workdir / "yaml"), SourceKind.LOCAL),)


# --- 4, 5. Позиционные аргументы ---------------------------------------------------------


def test_4_first_argument_override_is_error(workdir: Path, chain: ValidationChain) -> None:
    """`-workers.parse:8` первым аргументом → код 2 с указанием, что ожидалась цель."""
    result = chain.run(_context(["-workers.parse:8"]))

    assert result.ok is False
    assert result.exit_code == 2
    assert "первым аргументом должна быть цель" in result.message


def test_5_second_positional_is_error(workdir: Path, chain: ValidationChain) -> None:
    """Второй позиционный → код 2 с подсказкой про `-logging.dir:`."""
    result = chain.run(_context([str(workdir), "out/logs"]))

    assert result.ok is False
    assert result.exit_code == 2
    assert "-logging.dir" in result.message


# --- 6. Каждое правило V1…V10 отдельно ---------------------------------------------------


def test_v1_arg_count_rejects_extra_positional(workdir: Path) -> None:
    """V1: всё после цели обязано начинаться с `-`."""
    result = ArgCountRule().validate(_context([str(workdir), "лишнее"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "лишний аргумент" in result.message


def test_v2_first_arg_must_be_target(workdir: Path) -> None:
    """V2: первый аргумент — цель, а не ключ конфигурации."""
    result = FirstArgIsTargetRule().validate(_context(["-logging.level:DEBUG"]))

    assert (result.ok, result.exit_code) == (False, 2)


def test_v3_unknown_field_rejected(workdir: Path) -> None:
    """V3: опечатка в имени поля → код 2 с подсказкой «похожие поля»."""
    result = OverrideSyntaxRule().validate(_context([str(workdir), "-workers.parsse:8"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "похожие поля" in result.message


def test_v3_bad_type_rejected(workdir: Path) -> None:
    """V3: значение не приводится к типу поля → код 2 (не падение с трейсом)."""
    result = OverrideSyntaxRule().validate(_context([str(workdir), "-workers.parse:много"]))

    assert (result.ok, result.exit_code) == (False, 2)


def test_v4_url_target_is_not_a_path(workdir: Path) -> None:
    """V4: URL путём не считается — нормализация к нему не применяется."""
    ctx = _context(["https://github.com/dsp-gpu"])

    assert PathNormalizationRule().validate(ctx).ok is True
    assert ctx.target_path is None


def test_v5_unknown_target_rejected(workdir: Path, chain: ValidationChain) -> None:
    """V5: ни каталог, ни URL → код 2 (пункт 3 закона CLI)."""
    result = chain.run(_context(["ни-путь-ни-урл"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "не удалось определить вид цели" in result.message


def test_v5_explicit_kind_skips_detection(workdir: Path) -> None:
    """V5: `source.kind` не `auto` → вид берётся как указано, без детекции."""
    missing = workdir / "нет-такого-каталога"
    ctx = _context([str(missing), "-source.kind:local"])
    OverrideSyntaxRule().validate(ctx)
    PathNormalizationRule().validate(ctx)

    assert TargetKindRule().validate(ctx).ok is True
    assert ctx.resolved_targets == ((str(missing), SourceKind.LOCAL),)


def test_v6_missing_directory_rejected(workdir: Path, chain: ValidationChain) -> None:
    """V6: несуществующая локальная цель (вид навязан) → код 2."""
    result = chain.run(_context([str(workdir / "нет-такого"), "-source.kind:local"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "не является каталогом" in result.message


def test_v6_git_directory_target_moves_to_parent(workdir: Path, chain: ValidationChain) -> None:
    """V6: цель указывает на `.git` → поднимаемся к каталогу репозитория."""
    repo = workdir / "repo"
    (repo / ".git").mkdir(parents=True)

    ctx = _context([str(repo / ".git")])

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == ((str(repo), SourceKind.LOCAL),)
    assert ctx.draft.value_at("source.target") == str(repo)


def test_v7_unreadable_target_rejected(workdir: Path) -> None:
    """V7: нет права на чтение → код 2 (проверка доступа подменена, права ФС не трогаем)."""
    ctx = _context([str(workdir)])
    PathNormalizationRule().validate(ctx)
    TargetKindRule().validate(ctx)

    result = PathReadableRule(is_readable=lambda path: False).validate(ctx)

    assert (result.ok, result.exit_code) == (False, 2)
    assert str(workdir) in result.message


def test_v7_readable_target_passes(workdir: Path) -> None:
    """V7: обычный каталог читается — правило пропускает."""
    ctx = _context([str(workdir)])
    PathNormalizationRule().validate(ctx)
    TargetKindRule().validate(ctx)

    assert PathReadableRule().validate(ctx).ok is True


def test_v8_target_outside_git_warns(workdir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """V8: цель вне git — предупреждение, но не ошибка (D5)."""
    if any((parent / ".git").exists() for parent in [workdir, *workdir.parents]):
        pytest.skip("во временном каталоге уже есть git-репозиторий выше по дереву")
    ctx = _context([str(workdir)])
    PathNormalizationRule().validate(ctx)
    TargetKindRule().validate(ctx)

    with caplog.at_level(logging.WARNING, logger=_CLI_LOGGER):
        result = GitRepositoryRule().validate(ctx)

    assert result == ValidationResult(ok=True, exit_code=0, message="")
    assert any("вне git-репозитория" in record.message for record in caplog.records)


def test_v8_target_inside_git_is_silent(
    workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """V8: цель внутри репозитория — предупреждения нет."""
    repo = workdir / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "docs").mkdir()
    ctx = _context([str(repo / "docs")])
    PathNormalizationRule().validate(ctx)
    TargetKindRule().validate(ctx)

    with caplog.at_level(logging.WARNING, logger=_CLI_LOGGER):
        assert GitRepositoryRule().validate(ctx).ok is True

    assert [record for record in caplog.records if record.levelno >= logging.WARNING] == []


def test_v9_file_instead_of_directory_rejected(workdir: Path, chain: ValidationChain) -> None:
    """V9: `logging.dir` занят файлом → код 2."""
    (workdir / "занято").write_text("", encoding="utf-8")

    result = chain.run(_context([str(workdir), "-logging.dir:занято"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "не является каталогом" in result.message


def test_v10_write_failure_rejected(workdir: Path) -> None:
    """V10: пробная запись не удалась → код 2 (пробник подменён, права ФС не трогаем)."""
    ctx = _context([str(workdir)])

    def refuse(directory: Path) -> None:
        raise PermissionError(f"нет доступа: {directory}")

    OutputDirRule().validate(ctx)
    result = WritePermissionRule(probe=refuse).validate(ctx)

    assert (result.ok, result.exit_code) == (False, 2)
    assert "нет права на запись" in result.message


def test_v10_probe_file_is_removed(workdir: Path, chain: ValidationChain) -> None:
    """V10: после пробной записи в каталоге не остаётся служебных файлов."""
    assert chain.run(_context([str(workdir)])).ok is True

    created = workdir / "out" / "hw01"
    assert created.is_dir()
    assert list(created.iterdir()) == []


# --- 7. Нормализация пути ----------------------------------------------------------------


def test_7_relative_path_with_spaces_and_cyrillic(workdir: Path, chain: ValidationChain) -> None:
    """V4: относительный путь с пробелами и кириллицей → абсолютный."""
    target = workdir / "мои заметки"
    target.mkdir()

    ctx = _context(["мои заметки"])

    assert chain.run(ctx).ok is True
    assert ctx.target_path == target
    assert ctx.resolved_targets == ((str(target), SourceKind.LOCAL),)


def test_7_user_home_prefix_expanded(workdir: Path) -> None:
    """V4: `~` разворачивается в домашний каталог, а не остаётся строкой."""
    ctx = _context(["~"])

    assert PathNormalizationRule().validate(ctx).ok is True
    assert ctx.target_path == Path.home().resolve()


# --- 8. Порядок ключей -------------------------------------------------------------------


def test_8_override_order_does_not_matter(workdir: Path, chain: ValidationChain) -> None:
    """Порядок `-поле:значение` на результат не влияет (закон CLI, пункт 4)."""
    straight = _context([str(workdir), "-workers.parse:8", "-http.timeout_ms:5000"])
    reversed_order = _context([str(workdir), "-http.timeout_ms:5000", "-workers.parse:8"])

    assert chain.run(straight).ok is True
    assert chain.run(reversed_order).ok is True
    assert straight.draft.data == reversed_order.draft.data
    assert straight.draft.sources == reversed_order.draft.sources


# --- 9. V3 раньше V9 ---------------------------------------------------------------------


def test_9_output_dir_created_from_override(workdir: Path, chain: ValidationChain) -> None:
    """`-logging.dir:<новый>` → создаётся переопределённый каталог (V3 раньше V9)."""
    ctx = _context([str(workdir), "-logging.dir:логи прогона", "-report.dir:отчёты"])

    assert chain.run(ctx).ok is True
    assert (workdir / "логи прогона").is_dir()
    assert (workdir / "отчёты").is_dir()
    assert not (workdir / "out").exists()


# --- 10. Ветка `yaml` --------------------------------------------------------------------


def test_10_yaml_without_targets_is_error(workdir: Path, chain: ValidationChain) -> None:
    """`yaml` при пустых `target` и `repositories` → код 2, молча не сканируем."""
    result = chain.run(_context(["yaml"]))

    assert (result.ok, result.exit_code) == (False, 2)
    assert "цель не задана" in result.message


def test_10_yaml_mixed_list_resolves_every_kind(workdir: Path, chain: ValidationChain) -> None:
    """`yaml` со списком из трёх видов → три записи с верными `SourceKind`."""
    local = workdir / "проект"
    local.mkdir()
    ctx = _context(["yaml"])
    ctx.draft.assign(
        "source.repositories",
        [str(local), "git@github.com:dsp-gpu/radar.git", "https://github.com/executablebooks"],
        "y",
    )

    assert chain.run(ctx).ok is True
    assert ctx.resolved_targets == (
        (str(local), SourceKind.LOCAL),
        ("git@github.com:dsp-gpu/radar.git", SourceKind.REMOTE_REPO),
        ("https://github.com/executablebooks", SourceKind.GITHUB_ORG),
    )


def test_10_yaml_takes_target_and_repositories_together(
    workdir: Path, chain: ValidationChain
) -> None:
    """Заполнены и `target`, и `repositories` → сканируем всё вместе (часть 2 §2.0)."""
    ctx = _context(["yaml"])
    ctx.draft.assign("source.target", "https://github.com/dsp-gpu", "y")
    ctx.draft.assign("source.repositories", ["git@github.com:dsp-gpu/radar.git"], "y")

    assert chain.run(ctx).ok is True
    assert len(ctx.resolved_targets) == 2


# --- 11. Справка не выполняет V4…V10 -----------------------------------------------------


@pytest.mark.parametrize("argv", [[], ["-h"]], ids=["no-args", "help"])
def test_11_help_skips_rules_after_v3(
    workdir: Path, chain: ValidationChain, argv: list[str]
) -> None:
    """При справке V4…V10 не выполняются: каталоги не создаются, цели не определяются."""
    ctx = _context(argv)

    assert chain.run(ctx).ok is True
    assert ctx.target_path is None
    assert ctx.resolved_targets == ()
    assert list(workdir.iterdir()) == []


# --- Свойства цепочки и разборщика -------------------------------------------------------


def test_chain_stops_at_first_failure(workdir: Path) -> None:
    """Первый не-`ok` останавливает цепочку — следующие правила не вызываются."""
    calls: list[str] = []

    class _Rule:
        def __init__(self, name: str, result: ValidationResult) -> None:
            self._name = name
            self._result = result

        def validate(self, ctx: ValidationContext) -> ValidationResult:
            calls.append(self._name)
            return self._result

    chain = ValidationChain(
        (
            _Rule("first", ValidationResult(ok=True)),
            _Rule("second", ValidationResult(ok=False, exit_code=2, message="стоп")),
            _Rule("third", ValidationResult(ok=True)),
        )
    )

    result = chain.run(_context([str(workdir)]))

    assert result == ValidationResult(ok=False, exit_code=2, message="стоп")
    assert calls == ["first", "second"]


def test_parser_keeps_overrides_raw() -> None:
    """Разборщик ничего не проверяет: хвост командной строки сохраняется как есть."""
    args = ArgumentParser().parse(["yaml", "-workers.parse:8", "мусор"])

    assert args.target == "yaml"
    assert args.overrides == ("-workers.parse:8", "мусор")
    assert args.help_requested is False


def test_parser_result_is_immutable() -> None:
    """`CliArguments` неизменяем: разобранная командная строка не переписывается по ходу."""
    args = ArgumentParser().parse(["yaml"])

    with pytest.raises(AttributeError):
        args.target = "другое"  # type: ignore[misc]
