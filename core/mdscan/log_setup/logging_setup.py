"""Подъём и остановка логирования прогона (часть 1, D9; правило 11)."""

from __future__ import annotations

import logging
import logging.handlers
import queue
from collections.abc import Mapping
from pathlib import Path

from .log_format import LogFormat

#: Имя логгера пакета; модули берут ``logging.getLogger("core.mdscan.<пакет>")``.
#: Корневой логгер не трогаем — чужие библиотеки не должны попадать в наш файл.
LOGGER_NAME = "core.mdscan"


class LoggingSetup:
    """Владелец обработчиков логгера `core.mdscan` на время прогона.

    Потоки пишут в `QueueHandler` (не блокируются на диске), единственный
    `QueueListener` разбирает очередь и отдаёт записи `FileHandler`-у — строки
    из разных потоков не перемешиваются (D9).

    `start()` — единственная точка установки обработчиков (фаза 0, D4): прежние
    обработчики логгера снимаются, чтобы повторный подъём не удваивал строки.
    """

    _HEADER_KEY_WIDTH = 12

    def __init__(self, log_format: LogFormat | None = None) -> None:
        self._format = log_format or LogFormat()
        self._listener: logging.handlers.QueueListener | None = None
        self._file_handler: logging.FileHandler | None = None
        self._handler: logging.Handler | None = None

    def start(self, log_file: Path | None, level: str, header: Mapping[str, str]) -> logging.Logger:
        """Поднять логирование и вернуть логгер пакета.

        `log_file=None` (`logging.enabled: false`) → `NullHandler`: файл не создаётся,
        вызовы логгера не падают. `level` — `"DEBUG" | "INFO" | "WARNING"` (иначе `ValueError`).
        `header` — шапка файла (scope, время, вход, workers, проверки, отчёт): что передали, то и пишем.
        """
        logger = logging.getLogger(LOGGER_NAME)
        logger.propagate = False
        logger.setLevel(self._level_of(level))
        for stale in list(logger.handlers):
            logger.removeHandler(stale)

        if log_file is None:
            self._handler = logging.NullHandler()
            logger.addHandler(self._handler)
            return logger

        self._file_handler = self._open(Path(log_file), header)
        records: queue.Queue[logging.LogRecord] = queue.Queue(-1)
        self._listener = logging.handlers.QueueListener(
            records, self._file_handler, respect_handler_level=False
        )
        self._listener.start()
        self._handler = logging.handlers.QueueHandler(records)
        logger.addHandler(self._handler)
        return logger

    def stop(self) -> None:
        """Дождаться разбора очереди и снять обработчики; повторный вызов безопасен."""
        if self._listener is None and self._handler is None and self._file_handler is None:
            return
        try:
            if self._listener is not None:
                self._listener.stop()  # кладёт сентинел и join'ит поток: очередь разобрана до конца
        finally:
            self._listener = None
            if self._handler is not None:
                logging.getLogger(LOGGER_NAME).removeHandler(self._handler)
                self._handler = None
            if self._file_handler is not None:
                self._file_handler.close()
                self._file_handler = None

    def _open(self, log_file: Path, header: Mapping[str, str]) -> logging.FileHandler:
        """Открыть файл лога и записать шапку до старта слушателя."""
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        handler.setFormatter(self._format.formatter())
        handler.setLevel(logging.NOTSET)
        self._write_header(handler, header)
        return handler

    def _write_header(self, handler: logging.FileHandler, header: Mapping[str, str]) -> None:
        """Шапка прогона: строки `# ключ : значение` (D9), маркер `#` отделяет её от записей."""
        stream = handler.stream
        if stream is None:  # FileHandler(delay=False) открывает поток сразу; ветка — для mypy и защиты
            return
        for key, value in header.items():
            stream.write(f"# {key:<{self._HEADER_KEY_WIDTH}}: {value}\n")
        stream.flush()

    @staticmethod
    def _level_of(level: str) -> int:
        """Имя уровня → число; неизвестное имя не проглатываем (правило 11)."""
        try:
            return logging.getLevelNamesMapping()[level.strip().upper()]
        except KeyError as exc:
            raise ValueError(f"неизвестный уровень логирования: {level!r}") from exc
