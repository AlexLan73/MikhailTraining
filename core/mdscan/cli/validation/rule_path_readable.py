"""V7 — на локальную цель есть право чтения.

Без этой проверки прогон стартовал бы, создал лог и отчёт и только потом упёрся бы в
`PermissionError` внутри обхода — человек получил бы пустой отчёт вместо внятной ошибки.

Сама проверка доступа инжектируется в конструктор: тест подменяет её, не трогая
права файловой системы (спека разработки §3.3).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class PathReadableRule:
    """Каждая цель вида `LOCAL` доступна на чтение."""

    def __init__(self, is_readable: Callable[[Path], bool] | None = None) -> None:
        self._is_readable = is_readable or self._readable

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Нет права чтения → код 2 с именем каталога."""
        for path in ctx.local_targets:
            if not self._is_readable(path):
                _LOG.error("нет права на чтение цели: %s", path)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"нет права на чтение каталога «{path}»",
                )
        return ValidationResult(ok=True)

    def _readable(self, path: Path) -> bool:
        return os.access(path, os.R_OK)
