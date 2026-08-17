"""Печать всей конфигурации: usage, примеры и таблица «поле · значение · источник» (D19.3).

Запуск без аргументов (и `-h` / `--help` / `-?`) выводит именно это — видно, какое значение
реально применилось и откуда оно пришло: `d` = defaults, `y` = mdscan.yaml, `c` = cmdline.
Класс ничего не печатает сам: возвращает строку, печатает слой вывода (правило 09 п. 8).
"""

from __future__ import annotations

from typing import Any

from .defaults import Defaults
from .scan_config import ScanConfig

_UNKNOWN_SOURCE = "?"


class ConfigPrinter:
    """Собирает текстовое представление конфигурации для вывода в консоль."""

    HEADER = "mdscan — сканер Markdown-ссылок в git-репозиториях"
    USAGE = (
        "ИСПОЛЬЗОВАНИЕ:",
        "  python -m core.mdscan <цель> [-поле:значение ...]",
        "",
        "  цель — одно из: локальный каталог · URL репозитория · URL организации · слово yaml",
        "  -h / --help / -? — то же, что запуск без аргументов (эта справка)",
        "  порядок ключей -поле:значение любой; значение режется по первому двоеточию",
    )
    EXAMPLES = (
        "ПРИМЕРЫ:",
        "  python -m core.mdscan yaml                          # всё из mdscan.yaml",
        "  python -m core.mdscan /home/alex/DSP-GPU            # локальный каталог",
        "  python -m core.mdscan git@github.com:org/repo.git   # один репозиторий",
        "  python -m core.mdscan https://github.com/dsp-gpu    # организация целиком",
        "  python -m core.mdscan yaml -workers.parse:8 -logging.dir:out/hw01/logs",
    )
    MAX_VALUE_WIDTH = 40

    def __init__(self, defaults: Defaults | None = None) -> None:
        self._defaults = defaults or Defaults()

    def render(self, config: ScanConfig, sources: dict[str, str]) -> str:
        """Текст: шапка, usage, таблица всех полей с источниками, примеры."""
        rows = [
            (path, self._format(self._value_of(config, path)), sources.get(path, _UNKNOWN_SOURCE))
            for path in self._defaults.paths
        ]
        lines = [self.HEADER, "", *self.USAGE, ""]
        lines.extend(self._table(rows))
        lines.append("")
        lines.append(f"  цели (source.targets_resolved): {self._targets(config)}")
        lines.extend(["", *self.EXAMPLES])
        return "\n".join(lines)

    def _table(self, rows: list[tuple[str, str, str]]) -> list[str]:
        descriptions = self._defaults.descriptions
        name_width = max((len(path) for path, _, _ in rows), default=4)
        value_width = min(max((len(value) for _, value, _ in rows), default=8), self.MAX_VALUE_WIDTH)
        lines = [
            "КОНФИГУРАЦИЯ (источник: d=defaults, y=mdscan.yaml, c=cmdline)",
            f"  {'поле':<{name_width}}  {'значение':<{value_width}}  ист.  описание",
            f"  {'─' * name_width}  {'─' * value_width}  ────  {'─' * 28}",
        ]
        lines.extend(
            f"  {path:<{name_width}}  {value:<{value_width}}  {source:<4}  {descriptions.get(path, '')}"
            for path, value, source in rows
        )
        return lines

    def _targets(self, config: ScanConfig) -> str:
        targets = config.source.targets_resolved
        if not targets:
            return "не заданы (определит правило V5)"
        return ", ".join(f"{address} ({kind.value})" for address, kind in targets)

    def _value_of(self, config: ScanConfig, path: str) -> Any:
        section, _, name = path.partition(".")
        return getattr(getattr(config, section), name)

    def _format(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value) if value else "[]"
        text = str(value)
        return text if text else "''"
