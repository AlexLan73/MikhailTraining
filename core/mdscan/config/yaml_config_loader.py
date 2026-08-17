"""Чтение `mdscan.yaml` и его создание при холодном старте (D19.1).

Приоритет `defaults < yaml`: черновик всегда начинается со значений по умолчанию, поля,
найденные в файле, помечаются источником `y`. Файла нет → он создаётся из тех же значений
**с комментариями** (часть 2, раздел 2), в лог уходит `INFO`; переопределения командной
строки накладывает уже `CliOverrideApplier` (источник `c`).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from .config_draft import SOURCE_YAML, ConfigDraft
from .defaults import Defaults, SectionSpec

_LOG = logging.getLogger("core.mdscan.config")
_PLAIN_SCALAR = re.compile(r"[A-Za-z0-9_./+-]+")


class YamlConfigLoader:
    """Загрузчик конфигурации: `defaults` + `mdscan.yaml` → `ConfigDraft`."""

    COMMENT_COLUMN = 35

    def __init__(self, defaults: Defaults | None = None) -> None:
        self._defaults = defaults or Defaults()

    def load(self, path: Path) -> ConfigDraft:
        """Собрать черновик; файла нет → создать его из значений по умолчанию."""
        draft = ConfigDraft.from_defaults(self._defaults)
        if not path.exists():
            self._create(path)
            return draft
        self._merge(draft, self._read(path))
        _LOG.info("конфигурация прочитана: %s", path)
        return draft

    def render_defaults(self) -> str:
        """Текст `mdscan.yaml` со значениями по умолчанию и комментариями."""
        lines = [f"# {line}" for line in self._defaults.BANNER]
        for section in self._defaults.sections:
            lines.append("")
            lines.extend(self._section_lines(section))
        lines.append("")
        return "\n".join(lines)

    def _create(self, path: Path) -> None:
        try:
            if path.parent != Path():
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.render_defaults(), encoding="utf-8")
        except OSError as exc:
            _LOG.exception("не удалось создать %s", path)
            raise ConfigError(f"не удалось создать файл конфигурации {path}: {exc}") from exc
        _LOG.info("конфиг не найден, создан %s со значениями по умолчанию", path)

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover — зависимость объявлена в extra hw01
            _LOG.error("PyYAML не установлен, читать %s нечем", path)
            raise ConfigError(
                f"для чтения {path} нужен PyYAML: pip install -e .[hw01]"
            ) from exc
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            _LOG.exception("не удалось прочитать %s", path)
            raise ConfigError(f"не удалось прочитать файл конфигурации {path}: {exc}") from exc
        if loaded is None:
            return {}
        if not isinstance(loaded, dict):
            raise ConfigError(f"{path}: ожидался словарь секций, получено {type(loaded).__name__}")
        return loaded

    def _merge(self, draft: ConfigDraft, loaded: dict[str, Any]) -> None:
        for section, values in loaded.items():
            if not isinstance(values, dict):
                _LOG.warning("секция %s: ожидался словарь полей, пропущена", section)
                continue
            for name, value in values.items():
                path = f"{section}.{name}"
                if not self._defaults.has(path):
                    _LOG.warning("неизвестное поле в mdscan.yaml: %s — пропущено", path)
                    continue
                draft.assign(path, value, SOURCE_YAML)

    def _section_lines(self, section: SectionSpec) -> list[str]:
        lines = [self._with_comment(f"{section.name}:", section.comment)]
        for field in section.fields:
            head = f"  {field.name}: {self._scalar(field.value)}"
            lines.append(self._with_comment(head, field.comment))
        return lines

    def _with_comment(self, head: str, comment: tuple[str, ...]) -> str:
        if not comment:
            return head
        pad = " " * max(self.COMMENT_COLUMN - len(head), 1)
        first = f"{head}{pad}# {comment[0]}"
        tail = [f"{' ' * self.COMMENT_COLUMN}# {line}" for line in comment[1:]]
        return "\n".join([first, *tail])

    def _scalar(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(self._quoted(str(item)) for item in value) + "]"
        text = str(value)
        if not text:
            return "''"
        if _PLAIN_SCALAR.fullmatch(text):
            return text
        return self._quoted(text)

    def _quoted(self, text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
