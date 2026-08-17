"""Тесты T-03 — конфигурация: defaults → mdscan.yaml → командная строка (D19).

Номера тестов соответствуют пунктам «Тесты» таска T-03
(`MemoryBank/tasks/TASK_hw01_modules_T01-T15.md`).

Тесты, которым нужно **читать** yaml, помечены `pytest.importorskip("yaml")`: PyYAML
объявлен в extra `hw01`, но может быть не установлен — создание файла и всё остальное
работают без него.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from core.mdscan.config.cli_override_applier import CliOverrideApplier
from core.mdscan.config.config_draft import ConfigDraft
from core.mdscan.config.config_printer import ConfigPrinter
from core.mdscan.config.defaults import Defaults
from core.mdscan.config.scan_config import ScanConfig
from core.mdscan.config.yaml_config_loader import YamlConfigLoader
from core.mdscan.enums.source_kind import SourceKind
from core.mdscan.errors import ConfigError, UnknownFieldError


@pytest.fixture
def defaults() -> Defaults:
    return Defaults()


@pytest.fixture
def draft(defaults: Defaults) -> ConfigDraft:
    return ConfigDraft.from_defaults(defaults)


@pytest.fixture
def applier(defaults: Defaults) -> CliOverrideApplier:
    return CliOverrideApplier(defaults)


@pytest.fixture
def loader(defaults: Defaults) -> YamlConfigLoader:
    return YamlConfigLoader(defaults)


def _config_from(draft: ConfigDraft) -> ScanConfig:
    return ScanConfig.from_draft(draft)


# --- 1. Холодный старт -------------------------------------------------------------------


def test_1_cold_start_creates_file_with_defaults(
    tmp_path: Path, loader: YamlConfigLoader, defaults: Defaults
) -> None:
    """Файла нет → он создан, значения черновика = defaults, источник у всех `d`."""
    path = tmp_path / "mdscan.yaml"

    result = loader.load(path)

    assert path.exists()
    assert result.data == defaults.tree
    assert result.sources == dict.fromkeys(defaults.paths, "d")


def test_1_created_file_keeps_comments(tmp_path: Path, loader: YamlConfigLoader) -> None:
    """Созданный файл самодокументирован: шапка и комментарии полей на месте (часть 2 §2)."""
    path = tmp_path / "mdscan.yaml"

    loader.load(path)
    text = path.read_text(encoding="utf-8")

    assert "mdscan.yaml — конфигурация сканера Markdown-ссылок" in text
    assert "# ЧТО сканируем и откуда берём репозитории." in text
    assert "# сколько .md-ФАЙЛОВ разбирается одновременно" in text
    assert "targets_resolved" not in text  # служебное поле в файл не выводится


def test_1_created_file_parses_back_to_defaults(
    tmp_path: Path, loader: YamlConfigLoader, defaults: Defaults
) -> None:
    """Созданный файл — валидный yaml, разбор даёт ровно значения по умолчанию."""
    yaml = pytest.importorskip("yaml", reason="PyYAML не установлен — разбор yaml пропущен")
    path = tmp_path / "mdscan.yaml"

    loader.load(path)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert loaded == defaults.tree


# --- 2. Приоритет defaults < yaml < cmdline ----------------------------------------------


def test_2_yaml_overrides_defaults_and_cli_overrides_yaml(
    tmp_path: Path, loader: YamlConfigLoader, applier: CliOverrideApplier
) -> None:
    """Поле из yaml перекрывает default, `-поле:значение` перекрывает yaml; источники d/y/c."""
    pytest.importorskip("yaml", reason="PyYAML не установлен — чтение yaml пропущено")
    path = tmp_path / "mdscan.yaml"
    path.write_text(
        "workers:\n  discover: 9\n  parse: 3\nhttp:\n  timeout_ms: 500\n", encoding="utf-8"
    )

    result = loader.load(path)
    applier.apply(result, ["-workers.parse:8"])
    config = _config_from(result)

    assert (config.workers.discover, config.workers.parse) == (9, 8)
    assert config.http.timeout_ms == 500
    assert config.progress.interval_sec == pytest.approx(1.0)  # не задано нигде → default
    assert result.sources["workers.discover"] == "y"
    assert result.sources["workers.parse"] == "c"
    assert result.sources["progress.interval_sec"] == "d"


def test_2_existing_file_is_not_rewritten(tmp_path: Path, loader: YamlConfigLoader) -> None:
    """Существующий файл конфигурации не перезаписывается без спроса (D19.1)."""
    pytest.importorskip("yaml", reason="PyYAML не установлен — чтение yaml пропущено")
    path = tmp_path / "mdscan.yaml"
    original = "workers:\n  parse: 2\n"
    path.write_text(original, encoding="utf-8")

    loader.load(path)

    assert path.read_text(encoding="utf-8") == original


def test_2_unknown_yaml_field_is_ignored(tmp_path: Path, loader: YamlConfigLoader) -> None:
    """Лишнее поле в yaml не роняет прогон: пропускается (в лог — WARNING)."""
    pytest.importorskip("yaml", reason="PyYAML не установлен — чтение yaml пропущено")
    path = tmp_path / "mdscan.yaml"
    path.write_text("workers:\n  parse: 4\n  parsee: 7\n", encoding="utf-8")

    result = loader.load(path)

    assert result.data["workers"]["parse"] == 4
    assert "parsee" not in result.data["workers"]


# --- 3. Приведение типов -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "path", "expected"),
    [
        ("-workers.parse:8", "workers.parse", 8),
        ("-http.timeout_ms:5000", "http.timeout_ms", 5000),
        ("-progress.enabled:false", "progress.enabled", False),
        ("-progress.enabled:TRUE", "progress.enabled", True),
        ("-run.fail_on_broken:0", "run.fail_on_broken", False),
        ("-progress.interval_sec:2.5", "progress.interval_sec", 2.5),
        ("-scan.md_extensions:.md,.markdown", "scan.md_extensions", [".md", ".markdown"]),
        ("-source.repositories:/a, /b", "source.repositories", ["/a", "/b"]),
        ("-logging.level:DEBUG", "logging.level", "DEBUG"),
    ],
    ids=[
        "int",
        "int-ms",
        "bool-false",
        "bool-true-upper",
        "bool-zero",
        "float",
        "list",
        "list-spaces",
        "str",
    ],
)
def test_3_type_is_taken_from_default_value(
    draft: ConfigDraft, applier: CliOverrideApplier, override: str, path: str, expected: object
) -> None:
    """Тип значения берётся у значения по умолчанию (D19.2, шаг 4)."""
    applier.apply(draft, [override])

    value = draft.value_at(path)
    assert value == expected
    assert type(value) is type(expected)
    assert draft.sources[path] == "c"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ("-workers.parse:abc", "целое число"),
        ("-progress.interval_sec:быстро", "число"),
        ("-progress.enabled:ага", "true/false"),
        ("workers.parse:8", "-поле:значение"),
        ("-workers.parse", "-поле:значение"),
    ],
    ids=["not-int", "not-float", "not-bool", "no-dash", "no-colon"],
)
def test_3_bad_value_raises_config_error(
    draft: ConfigDraft, applier: CliOverrideApplier, override: str, message: str
) -> None:
    """Непреобразуемое значение или сломанный синтаксис → `ConfigError` с внятным текстом."""
    with pytest.raises(ConfigError, match=message):
        applier.apply(draft, [override])


# --- 4. Неизвестное поле -----------------------------------------------------------------


def test_4_unknown_field_reports_similar_fields(
    draft: ConfigDraft, applier: CliOverrideApplier
) -> None:
    """Опечатка не проходит молча: `UnknownFieldError` с подсказкой «похожие поля: …»."""
    with pytest.raises(UnknownFieldError, match="похожие поля") as exc:
        applier.apply(draft, ["-workers.pasre:8"])

    assert "workers.parse" in str(exc.value)
    assert isinstance(exc.value, ConfigError)  # иерархия из core/mdscan/errors.py


def test_4_service_field_cannot_be_set_from_cli(
    draft: ConfigDraft, applier: CliOverrideApplier
) -> None:
    """Служебное `source.targets_resolved` через командную строку не задаётся (р5)."""
    with pytest.raises(UnknownFieldError):
        applier.apply(draft, ["-source.targets_resolved:/a"])


# --- 5. Значение с двоеточием ------------------------------------------------------------


def test_5_value_may_contain_colon(draft: ConfigDraft, applier: CliOverrideApplier) -> None:
    """Режем по ПЕРВОМУ двоеточию: заголовок с двоеточием сохраняется целиком."""
    applier.apply(draft, ["-report.title:Итоги: dsp-gpu"])

    assert _config_from(draft).report.title == "Итоги: dsp-gpu"


def test_5_url_value_survives(draft: ConfigDraft, applier: CliOverrideApplier) -> None:
    """URL в значении (`https://…`) не ломает разбор."""
    applier.apply(draft, ["-source.target:https://github.com/dsp-gpu"])

    assert _config_from(draft).source.target == "https://github.com/dsp-gpu"


# --- 6. Неизменяемость -------------------------------------------------------------------


def test_6_scan_config_is_frozen(draft: ConfigDraft) -> None:
    """`ScanConfig` и её секции неизменяемы — конфигурацию читают все потоки (D15.2)."""
    config = _config_from(draft)

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.workers = None  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.workers.parse = 99  # type: ignore[misc]


def test_6_lists_become_tuples(draft: ConfigDraft) -> None:
    """Списки из yaml превращаются в кортежи (изменяемых коллекций в конфиге нет)."""
    config = _config_from(draft)

    assert isinstance(config.scan.md_extensions, tuple)
    assert isinstance(config.parser.plugins, tuple)
    assert isinstance(config.source.repositories, tuple)


# --- 7. Печать конфигурации --------------------------------------------------------------


def test_7_printer_shows_usage_examples_and_every_field(
    draft: ConfigDraft, applier: CliOverrideApplier, defaults: Defaults
) -> None:
    """Печать без аргументов: usage, примеры, все поля и источник у каждого (D19.3)."""
    applier.apply(draft, ["-workers.parse:8"])
    draft.assign("http.timeout_ms", 5000, "y")
    config = _config_from(draft)

    text = ConfigPrinter(defaults).render(config, draft.sources)
    rows = {
        line.split()[0]: line.split() for line in text.splitlines() if line.startswith("  source.")
    }

    assert "ИСПОЛЬЗОВАНИЕ:" in text
    assert "python -m core.mdscan <цель> [-поле:значение ...]" in text
    assert "ПРИМЕРЫ:" in text
    assert "d=defaults" in text and "y=mdscan.yaml" in text and "c=cmdline" in text
    for path in defaults.paths:
        assert f"  {path} " in text, f"поле {path} не напечатано"
    assert rows["source.kind"][1:3] == ["auto", "d"]
    assert _source_letter(text, "workers.parse") == "c"
    assert _source_letter(text, "http.timeout_ms") == "y"
    assert _source_letter(text, "workers.discover") == "d"
    assert "потоков на разбор .md" in text  # колонка «описание»


def test_7_printer_shows_resolved_targets(draft: ConfigDraft, defaults: Defaults) -> None:
    """Служебное `targets_resolved` печатается отдельной строкой «цели», а не в таблице."""
    draft.data["source"]["targets_resolved"] = [
        ("/home/alex/DSP-GPU", SourceKind.LOCAL),
        ("https://github.com/dsp-gpu", SourceKind.GITHUB_ORG),
    ]

    text = ConfigPrinter(defaults).render(_config_from(draft), draft.sources)

    assert "цели (source.targets_resolved): /home/alex/DSP-GPU (local), " in text
    assert "https://github.com/dsp-gpu (github_org)" in text


def _source_letter(text: str, path: str) -> str:
    """Достать колонку «ист.» из строки таблицы для указанного поля."""
    line = next(line for line in text.splitlines() if line.strip().startswith(f"{path} "))
    return line.split()[2]


# --- 8. Сборка ScanConfig ----------------------------------------------------------------


def test_8_from_draft_builds_every_section(draft: ConfigDraft) -> None:
    """`from_draft` — единственная точка сборки; присутствуют все секции и «свежие» поля."""
    config = ScanConfig.from_draft(draft)

    assert config.http.user_agent == "mdscan/0.1"
    assert config.source.keep_clones is False
    assert config.source.clone_depth == 1
    assert config.checks.local is True and config.checks.anchors is True
    assert config.logging.level == "INFO"
    assert config.report.dir == "out/hw01"
    assert config.run.fail_on_broken is True
    assert config.source.targets_resolved == ()


def test_8_targets_resolved_becomes_tuple_of_pairs(draft: ConfigDraft) -> None:
    """Правило V5 пишет пары в черновик — в конфиге они кортеж `(адрес, SourceKind)`."""
    draft.data["source"]["targets_resolved"] = [
        ["/home/alex/DSP-GPU", "local"],
        ("git@github.com:dsp-gpu/radar.git", SourceKind.REMOTE_REPO),
    ]

    resolved = ScanConfig.from_draft(draft).source.targets_resolved

    assert resolved == (
        ("/home/alex/DSP-GPU", SourceKind.LOCAL),
        ("git@github.com:dsp-gpu/radar.git", SourceKind.REMOTE_REPO),
    )


def test_8_incomplete_draft_raises_config_error(draft: ConfigDraft) -> None:
    """Черновик без обязательной секции → `ConfigError`, а не `KeyError` наружу."""
    del draft.data["http"]

    with pytest.raises(ConfigError, match="http"):
        ScanConfig.from_draft(draft)


def test_8_defaults_are_declared_once(defaults: Defaults) -> None:
    """Значения по умолчанию живут только в defaults.py: все поля конфига описаны там."""
    config = ScanConfig.from_draft(ConfigDraft.from_defaults(defaults))
    declared = set(defaults.paths)

    actual = {
        f"{section.name}.{field.name}"
        for section in dataclasses.fields(config)
        for field in dataclasses.fields(getattr(config, section.name))
    }

    assert actual - declared == {"source.targets_resolved"}
    assert declared - actual == set()
