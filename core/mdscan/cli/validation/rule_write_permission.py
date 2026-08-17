"""V10 — в каталоги лога и отчёта действительно можно писать.

Существование каталога (V9) ещё не значит, что запись разрешена: сетевая шара, том
только для чтения, чужие права. Дешевле узнать это до прогона, чем после часа обхода
на попытке записать отчёт (код 3).

Пробная запись инжектируется в конструктор — тест проверяет отказ, не ломая права ФС.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class WritePermissionRule:
    """Пробная запись файла в каждый выходной каталог удалась."""

    FIELDS = ("logging.dir", "report.dir")

    def __init__(self, probe: Callable[[Path], None] | None = None) -> None:
        self._probe = probe or self._write_probe

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Записать и удалить временный файл; отказ → код 2."""
        for field in self.FIELDS:
            path = Path(str(ctx.draft.value_at(field))).expanduser()
            try:
                self._probe(path)
            except OSError as exc:
                _LOG.exception("каталог %s недоступен для записи (%s)", path, field)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"{field}: нет права на запись в «{path}»: {exc}",
                )
            _LOG.debug("каталог %s доступен для записи", path)
        return ValidationResult(ok=True)

    def _write_probe(self, directory: Path) -> None:
        probe = directory / f".mdscan-write-test-{os.getpid()}"
        try:
            probe.write_text("", encoding="utf-8")
        finally:
            probe.unlink(missing_ok=True)
