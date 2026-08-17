"""Проверка якоря заголовка: `#раздел` в своём файле, `a.md#раздел` — в целевом."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from urllib.parse import unquote

from ..enums.check_status import CheckStatus
from ..models.md_link import MdLink
from .heading_source import HeadingSource

_log = logging.getLogger("core.mdscan.checking")

#: Символы, которые GitHub оставляет в slug помимо букв и цифр.
_KEPT_PUNCTUATION = "-_"


class AnchorChecker:
    """Сверяет фрагмент ссылки с GitHub-slug'ами заголовков файла (инвариант 24).

    Текст файла читает **сам** (`parsing.MarkdownReader` импортировать нельзя —
    это чужой модуль, §2.5), заголовки получает через `HeadingSource`. Результат
    разбора кэшируется по файлу: один прогон — одно чтение (кэш под `Lock`,
    экземпляр общий на все parse-потоки).
    """

    def __init__(self, headings: HeadingSource) -> None:
        self._headings = headings
        self._cache: dict[Path, tuple[str, ...]] = {}
        self._lock = Lock()

    def check(self, link: MdLink, md_file: Path) -> None:
        """Проверить фрагмент `link.target` по заголовкам `md_file`."""
        fragment = unquote(link.target.partition("#")[2]).strip()
        if not fragment:
            link.status = CheckStatus.OK
            _log.debug("якоря нет, проверять нечего: %s", link.target)
            return
        try:
            slugs = self._slugs_of(md_file)
        except Exception as exc:  # noqa: BLE001 — исход ошибки = статус ссылки (D2.1)
            link.status = CheckStatus.BROKEN
            link.detail = f"заголовки не прочитаны: {type(exc).__name__}: {exc}"
            _log.exception("не удалось получить заголовки файла %s", md_file)
            return
        if _slugify(fragment) in slugs:
            link.status = CheckStatus.OK
            _log.debug("якорь найден: #%s в %s", fragment, md_file.name)
            return
        link.status = CheckStatus.BROKEN
        link.detail = f"нет заголовка с якорем «{fragment}» в {md_file.name}"
        _log.debug("битый якорь: #%s в %s", fragment, md_file)  # H-06: одна WARNING на ссылку — у воркера

    def _slugs_of(self, md_file: Path) -> tuple[str, ...]:
        """Slug'и заголовков файла; повторный вызов берёт их из кэша.

        Ключ кэша — путь как он пришёл: сам его не резолвим (это обращение к ОС на каждую
        якорную ссылку). Абсолютный резолвленный путь обеспечивает вызывающий — обход
        (`MarkdownFileFinder`) для своего файла и `LocalFileChecker` для целевого; проверено
        замером H-05: 257 файлов с якорями → 257 разборов заголовков на прогон.
        """
        with self._lock:
            cached = self._cache.get(md_file)
        if cached is not None:
            return cached
        text = md_file.read_text(encoding="utf-8-sig", errors="replace")
        slugs = _with_duplicate_suffixes(self._headings.headings(text))
        with self._lock:
            return self._cache.setdefault(md_file, slugs)


def _slugify(text: str) -> str:
    """Заголовок → GitHub-slug: нижний регистр, пробелы `-`, пунктуация убрана.

    Кириллица сохраняется (`str.isalnum` считает её буквами), поэтому
    `## Как запустить` даёт `как-запустить`.
    """
    letters = [
        "-" if symbol.isspace() else symbol
        for symbol in text.strip().lower()
        if symbol.isalnum() or symbol.isspace() or symbol in _KEPT_PUNCTUATION
    ]
    return "".join(letters)


def _with_duplicate_suffixes(headings: tuple[str, ...]) -> tuple[str, ...]:
    """Повторяющийся заголовок получает суффикс `-1`, `-2` — как на GitHub."""
    seen: dict[str, int] = {}
    slugs: list[str] = []
    for heading in headings:
        base = _slugify(heading)
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.append(base if count == 0 else f"{base}-{count}")
    return tuple(slugs)
