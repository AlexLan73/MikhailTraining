"""Чтение файла `.md` в текст: UTF-8 и UTF-8-SIG, ошибка — понятным исключением."""

from __future__ import annotations

import logging
from pathlib import Path

from core.mdscan.errors import MarkdownReadError

logger = logging.getLogger("core.mdscan.parsing")


class MarkdownReader:
    """Единственный способ превратить файл `.md` в строку для парсера.

    Почему отдельный класс, а не `Path.read_text`: чтение — единственный шаг
    конвейера, который падает на «злых» файлах (битая кодировка, нет прав), и
    его ошибка обязана быть распознаваемой (`MarkdownReadError`), чтобы worker
    записал её в `MdFileResult.error` и продолжил прогон (правило 11).

    Кодек `utf-8-sig` покрывает оба случая сразу: BOM в начале снимается, файл
    без BOM читается как обычный UTF-8 — отдельной ветки «попробовать ещё раз»
    не нужно.
    """

    _ENCODING = "utf-8-sig"

    def read(self, path: Path) -> str:
        """Возвращает содержимое файла. Любая ошибка → `MarkdownReadError`."""
        payload = self._read_bytes(path)
        return self._decode(payload, path)

    # ── приватные хелперы ────────────────────────────────────────────────────

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        """Байты файла; ошибка ввода-вывода → `MarkdownReadError` с путём."""
        try:
            payload = path.read_bytes()
        except OSError as exc:
            logger.debug("не удалось прочитать %s", path, exc_info=True)  # ERROR с трейсом пишет ловящий (worker)
            message = f"{path}: файл не читается ({type(exc).__name__}: {exc})"
            raise MarkdownReadError(message) from exc
        logger.debug("прочитан %s (%d байт)", path, len(payload))
        return payload

    @classmethod
    def _decode(cls, payload: bytes, path: Path) -> str:
        """Декодирует байты; битая кодировка → `MarkdownReadError` с позицией байта."""
        try:
            return payload.decode(cls._ENCODING)
        except UnicodeDecodeError as exc:
            logger.debug("битая кодировка в %s", path, exc_info=True)  # ERROR с трейсом пишет ловящий (worker)
            byte = payload[exc.start] if exc.start < len(payload) else 0
            message = (
                f"{path}: не UTF-8 — байт 0x{byte:02x} в позиции {exc.start} ({exc.reason})"
            )
            raise MarkdownReadError(message) from exc
