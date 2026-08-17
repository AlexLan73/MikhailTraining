"""Имя файла лога/отчёта по стандарту прогона (часть 1, D9)."""

from __future__ import annotations

import re
from datetime import datetime


class LogNaming:
    """Собирает имя вида ``<scope>_<YYYY-MM-DD>_<HH-MM-SS>.<ext>``.

    Метка времени приходит **снаружи** (одна на прогон): лог и отчёт одного запуска
    получают одинаковый суффикс и видны в каталоге парой (D9, решение Alex).
    Пользователь задаёт только каталог — имя файла всегда строится здесь.
    """

    _FALLBACK_SCOPE = "scan"
    _STAMP = "%Y-%m-%d_%H-%M-%S"
    _WHITESPACE = re.compile(r"\s+")
    # Запрещённые в именах файлов Windows/Linux символы (\x5c — обратный слэш);
    # кириллица и дефис остаются.
    _FORBIDDEN = re.compile(r'[<>:"/\x5c|?*\x00-\x1f]')

    def build(self, scope: str, when: datetime, ext: str) -> str:
        """Имя файла: нормализованный `scope`, метка времени `when`, расширение `ext`."""
        return f"{self._normalize(scope)}_{when.strftime(self._STAMP)}.{ext.lstrip('.')}"

    def _normalize(self, scope: str) -> str:
        """Пробелы → `_`, недопустимые символы ФС убираются, пусто → `scan`."""
        collapsed = self._WHITESPACE.sub("_", scope.strip())
        cleaned = self._FORBIDDEN.sub("", collapsed).strip("._ ")
        return cleaned or self._FALLBACK_SCOPE
