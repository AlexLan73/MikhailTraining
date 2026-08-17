"""V9 — каталоги лога и отчёта существуют (создаются при отсутствии).

Стоит после V3 намеренно: проверяется и создаётся **переопределённое** значение, то есть
`-logging.dir:out/hw01/logs` создаёт именно этот каталог, а не тот, что лежит в yaml
(часть 2 §1.3, ревью 3). При коде 2 из ранних правил сюда не доходит — каталоги на
неудачном запуске не появляются.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class OutputDirRule:
    """`logging.dir` и `report.dir` — каталоги; отсутствуют → создаются."""

    FIELDS = ("logging.dir", "report.dir")

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Создать оба каталога; занято файлом или нет прав → код 2."""
        for field in self.FIELDS:
            path = Path(str(ctx.draft.value_at(field))).expanduser()
            if path.exists() and not path.is_dir():
                _LOG.error("%s указывает не на каталог: %s", field, path)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"{field}: «{path}» существует и не является каталогом",
                )
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                _LOG.exception("не удалось создать каталог %s (%s)", path, field)
                return ValidationResult(
                    ok=False,
                    exit_code=2,
                    message=f"{field}: не удалось создать каталог «{path}»: {exc}",
                )
            _LOG.debug("каталог %s готов: %s", field, path)
        return ValidationResult(ok=True)
