"""Формат строки лога (часть 1, D9; правило 11-exceptions-logging)."""

from __future__ import annotations

import logging


class LogFormat:
    """Строка лога: ``время | уровень | поток | repo | file | сообщение``.

    Контекст (`repo`, `file`) модули передают через ``extra=``; если поля нет,
    `Formatter` подставляет `-` (штатный механизм `defaults=`, Python ≥ 3.10),
    поэтому вызов без контекста не роняет запись.
    """

    PATTERN = "%(asctime)s | %(levelname)s | %(threadName)s | %(repo)s | %(file)s | %(message)s"
    MISSING = "-"

    def formatter(self) -> logging.Formatter:
        """Готовый `Formatter` для файлового обработчика."""
        return logging.Formatter(
            self.PATTERN,
            defaults={"repo": self.MISSING, "file": self.MISSING},
        )
