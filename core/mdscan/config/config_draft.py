"""Изменяемый черновик конфигурации фазы 0 (живёт только до сборки `ScanConfig`).

Черновик — единственное место, где конфигурация ещё **меняется**: в него по очереди
пишут `YamlConfigLoader` (источник `y`), правило V3 через `CliOverrideApplier` (`c`)
и правило V5 (служебное `source.targets_resolved`). После `ScanConfig.from_draft`
конфигурация неизменяема (D15.2) и её читают все потоки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .defaults import Defaults

SOURCE_DEFAULTS = "d"
SOURCE_YAML = "y"
SOURCE_CMDLINE = "c"


@dataclass(slots=True)
class ConfigDraft:
    """Дерево значений + происхождение каждого поля (`d` / `y` / `c`)."""

    data: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_defaults(cls, defaults: Defaults | None = None) -> ConfigDraft:
        """Черновик из значений по умолчанию: у всех полей источник `d`."""
        spec = defaults or Defaults()
        return cls(data=spec.tree, sources={path: SOURCE_DEFAULTS for path in spec.paths})

    def value_at(self, path: str) -> Any:
        """Текущее значение поля по пути `секция.поле`; нет такого → `KeyError`."""
        section, _, name = path.partition(".")
        return self.data[section][name]

    def assign(self, path: str, value: Any, source: str) -> None:
        """Записать значение и пометить, откуда оно пришло (`d` / `y` / `c`)."""
        section, _, name = path.partition(".")
        self.data.setdefault(section, {})[name] = value
        self.sources[path] = source
