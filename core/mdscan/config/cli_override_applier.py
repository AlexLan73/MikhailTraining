"""Наложение переопределений `-поле:значение` на черновик конфигурации (D19.2).

Вызывается из правила V3 цепочки валидации (T-05) — **до** проверок каталогов V9/V10,
потому что переопределение может задавать сам каталог (`-logging.dir:…`).

Механика: режем по **первому** двоеточию, путь ищем в значениях по умолчанию, тип берём
у значения по умолчанию, источник поля помечаем как `c`. Неизвестное поле не проходит
молча — `UnknownFieldError` с подсказкой «похожие поля: …» (код возврата 2 ставит CLI).
"""

from __future__ import annotations

import difflib
import logging
from typing import Any

from ..errors import ConfigError, UnknownFieldError
from .config_draft import SOURCE_CMDLINE, ConfigDraft
from .defaults import Defaults

_LOG = logging.getLogger("core.mdscan.config")

_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})


class CliOverrideApplier:
    """Применяет список сырых `-поле:значение` к черновику конфигурации."""

    SUGGESTIONS = 3

    def __init__(self, defaults: Defaults | None = None) -> None:
        self._defaults = defaults or Defaults()

    def apply(self, draft: ConfigDraft, overrides: list[str]) -> None:
        """Наложить переопределения по порядку; любая ошибка — исключение с текстом."""
        for raw in overrides:
            path, text = self._split(raw)
            if not self._defaults.has(path):
                raise UnknownFieldError(
                    f"неизвестное поле «{path}»; похожие поля: {self._suggest(path)}"
                )
            value = self._coerce(path, text)
            draft.assign(path, value, SOURCE_CMDLINE)
            _LOG.debug("переопределение из командной строки: %s = %r", path, value)

    def _split(self, raw: str) -> tuple[str, str]:
        if not raw.startswith("-") or len(raw) < 2:
            raise ConfigError(f"ожидался аргумент вида -поле:значение, получено: {raw!r}")
        body = raw[1:]
        path, sep, text = body.partition(":")
        if not sep or not path:
            raise ConfigError(f"ожидался аргумент вида -поле:значение, получено: {raw!r}")
        return path, text

    def _suggest(self, path: str) -> str:
        known = list(self._defaults.paths)
        close = difflib.get_close_matches(path, known, n=self.SUGGESTIONS, cutoff=0.4)
        if not close:
            close = difflib.get_close_matches(path, known, n=self.SUGGESTIONS, cutoff=0.0)
        return ", ".join(close) if close else "нет похожих"

    def _coerce(self, path: str, text: str) -> Any:
        default = self._defaults.value_at(path)
        if isinstance(default, bool):
            return self._as_bool(path, text)
        if isinstance(default, int):
            return self._as_number(path, text, int)
        if isinstance(default, float):
            return self._as_number(path, text, float)
        if isinstance(default, (list, tuple)):
            return [item.strip() for item in text.split(",") if item.strip()]
        return text

    def _as_bool(self, path: str, text: str) -> bool:
        lowered = text.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ConfigError(f"поле {path}: ожидалось true/false, получено {text!r}")

    def _as_number(self, path: str, text: str, kind: type) -> Any:
        try:
            return kind(text.strip())
        except ValueError as exc:
            expected = "целое число" if kind is int else "число"
            raise ConfigError(f"поле {path}: ожидалось {expected}, получено {text!r}") from exc
