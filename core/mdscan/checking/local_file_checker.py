"""Проверка локальной ссылки: существование файла относительно файла-владельца."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from urllib.parse import unquote

from ..enums.check_status import CheckStatus
from ..models.md_link import MdLink
from .anchor_checker import AnchorChecker

_log = logging.getLogger("core.mdscan.checking")

#: Схема, которую мы принципиально не проверяем (см. докстринг класса).
_FILE_SCHEME = "file://"


class LocalFileChecker:
    """Ищет цель ссылки на диске; при `a.md#раздел` — ещё и якорь в целевом файле.

    Базовый каталог — **папка файла-владельца** (`md_file.parent`, требование T10
    условия ДЗ), а не корень репозитория: `../../README.md` из вложенного файла
    обязан резолвиться так же, как его резолвит GitHub.

    `file://…` не проверяется (`SKIPPED`): это абсолютный адрес чужой машины,
    попытка его резолвить дала бы ложные битые ссылки (🔧 р5, по итогу T-02).
    """

    def __init__(self, anchors: AnchorChecker | None) -> None:
        self._anchors = anchors
        # H-05/G2: каталог файла-владельца резолвится один раз на каталог, а не на каждую ссылку
        # (на наборе B — ~1000 лишних `_getfinalpathname`); чекер общий на прогон → под замком.
        self._bases: dict[Path, Path] = {}
        self._bases_lock = threading.Lock()

    def check(self, link: MdLink, md_file: Path) -> None:
        """Заполнить статус ссылки по наличию файла (и якоря) на диске."""
        target = link.target
        if target.lower().startswith(_FILE_SCHEME):
            link.status = CheckStatus.SKIPPED
            link.detail = "file:// URI не проверяется"
            _log.debug("file:// пропущен: %s", target)
            return
        path_part, _, fragment = target.partition("#")
        if not path_part:
            self._check_anchor(link, md_file)
            return
        try:
            resolved = self._resolve(self._base_of(md_file.parent), path_part)
        except (OSError, ValueError) as exc:
            link.status = CheckStatus.BROKEN
            link.detail = f"путь не разобран: {type(exc).__name__}: {exc}"
            _log.warning("не удалось разобрать путь %s из %s", target, md_file, exc_info=True)
            return
        if resolved is None:
            link.status = CheckStatus.BROKEN
            link.detail = f"нет файла: {path_part}"
            # DEBUG, а не WARNING: единственную громкую строку на битую ссылку пишет
            # `MarkdownWorker._log_link` — у него есть поля repo/file формата лога (H-06).
            _log.debug("битая локальная ссылка: %s (из %s)", target, md_file)
            return
        if fragment:
            self._check_anchor(link, resolved)
            return
        link.status = CheckStatus.OK
        _log.debug("локальная ссылка цела: %s → %s", target, resolved)

    def _check_anchor(self, link: MdLink, target_file: Path) -> None:
        """Якорная часть ссылки; при `checks.anchors: false` чекера нет — считаем целой."""
        if self._anchors is None:
            link.status = CheckStatus.OK
            _log.debug("проверка якорей выключена: %s", link.target)
            return
        self._anchors.check(link, target_file)

    def _base_of(self, directory: Path) -> Path:
        """Абсолютный каталог файла-владельца — из кэша прогона (`resolve()` один раз на каталог)."""
        with self._bases_lock:
            cached = self._bases.get(directory)
            if cached is None:
                cached = directory.resolve()
                self._bases[directory] = cached
            return cached

    @staticmethod
    def _resolve(base: Path, path_part: str) -> Path | None:
        """Путь относительно (уже абсолютного) каталога файла-владельца; нет такого — `None`.

        Пробуем и как есть, и после `unquote`: `%20` в ссылке — тот же пробел в имени файла.
        `../..` снимает `os.path.normpath` — без обращения к ФС; символические ссылки в самой цели
        не разворачиваются (для проверки существования это и не нужно).
        """
        for candidate in dict.fromkeys((path_part, unquote(path_part))):
            resolved = Path(os.path.normpath(base / candidate))
            if resolved.exists():
                return resolved
        return None
