"""V4 — путь-цель приводится к абсолютному: `~`, относительный, пробелы, кириллица, UNC.

Нормализация стоит **до** проверок существования (V5…V8): иначе `../DSP-GPU` и
`~/proj` проверялись бы относительно случайного текущего каталога и в отчёт попадали бы
разные записи для одного и того же дерева.

URL и ветка `yaml` путями не являются и остаются как есть — их разбирает V5.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .validation_context import URL_MARKERS, ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")


class PathNormalizationRule:
    """Кладёт в контекст абсолютный `Path`, если цель похожа на путь на диске."""

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Заполнить `ctx.target_path`; недопустимый путь → код 2."""
        target = ctx.args.target
        if target is None or ctx.yaml_branch or any(mark in target for mark in URL_MARKERS):
            return ValidationResult(ok=True)
        try:
            ctx.target_path = Path(target).expanduser().resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            _LOG.exception("не удалось нормализовать путь цели: %r", target)
            return ValidationResult(
                ok=False,
                exit_code=2,
                message=f"недопустимый путь цели «{target}»: {exc}",
            )
        _LOG.debug("цель нормализована: %r → %s", target, ctx.target_path)
        return ValidationResult(ok=True)
