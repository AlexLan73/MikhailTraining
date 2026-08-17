"""Заголовки Markdown-файла — источник данных для проверки якорей (`#раздел`).

Класс структурно реализует `checking.HeadingSource` (владелец контракта — T-07).
Импортировать `core.mdscan.checking.*` здесь **нельзя**: модули пишутся в одной
волне, файла контракта ещё нет; совпадение сигнатур проверит `mypy` на приёмке
(спека разработки §2.5).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

logger = logging.getLogger("core.mdscan.parsing")

#: Core-правила `markdown-it`, которые заголовкам не нужны: inline-разбор **всего** документа
#: (и работающие по его результату `linkify`/`text_join`). H-05: это 59 % цены `md.parse`,
#: а заголовкам достаточно блочной структуры.
_DOCUMENT_ONLY_BLOCKS: tuple[str, ...] = ("inline", "linkify", "text_join")

#: Признак inline-разметки в тексте заголовка. Ни одного такого символа — текст уже чистый,
#: разбирать нечего (быстрый путь: в наборе B так выглядят почти все заголовки).
_MARKUP = re.compile(r"[*_`\[\]<>&\\~!]")


class MarkdownItHeadingSource:
    """Тексты заголовков всех уровней в порядке появления.

    Берём тем же токенизатором, что и ссылки: заголовок внутри ``` fenced code ```
    заголовком не является, а `## Как запустить` в кавычках/списке — является ровно
    тогда, когда так считает GitHub. Своего разбора `#` в начале строки не пишем.

    Возвращается **текст** заголовка (`## Как запустить` → `Как запустить`);
    превращение текста в GitHub-slug — дело `AnchorChecker` (T-07).

    Разбор идёт в два дешёвых прохода (H-05, гипотеза G-H):

    1. `_blocks` — документ разбирается **блочно**: inline-правила выключены, у inline-токена
       остаётся сырой `token.content` (`Как **запустить**`). Именно inline-разбор всего текста
       (абзацы, списки, таблицы) и составлял основную цену второго разбора файла.
    2. `_inline` — сырой текст **одного заголовка** доразбирается полностью, чтобы разметка
       не попала в slug: GitHub считает `## Как **запустить**` якорем `#как-запустить`, а
       `# Раздел с [ссылкой](a.md)` — `#раздел-с-ссылкой` (цель ссылки в slug не входит).
       `env` общий с блочным проходом: в нём лежат определения `[ref]: url`, без них
       reference-ссылка в заголовке осталась бы литералом `[текст][ref]`.
    """

    _DEFAULT_PRESET = "gfm-like"

    def __init__(self, preset: str = _DEFAULT_PRESET) -> None:
        self._blocks = self._parser(preset)
        self._blocks.disable(list(_DOCUMENT_ONLY_BLOCKS))
        self._inline = self._parser(preset)

    def headings(self, text: str) -> tuple[str, ...]:
        """Тексты заголовков `h1…h6` по порядку; из code-блоков — ни одного."""
        env: dict[str, Any] = {}
        titles: list[str] = []
        expect_inline = False
        for token in self._blocks.parse(text, env):
            if token.type == "heading_open":
                expect_inline = True
            elif expect_inline and token.type == "inline":
                titles.append(self._plain(token.content, env))
                expect_inline = False
        logger.debug("заголовков найдено: %d", len(titles))
        return tuple(titles)

    # ── приватные хелперы ────────────────────────────────────────────────────

    @staticmethod
    def _parser(preset: str) -> MarkdownIt:
        """Парсер пресета с той же оговоркой про `linkify`, что у извлечения ссылок."""
        md = MarkdownIt(preset)
        if md.linkify is None and md.options.get("linkify"):
            md.options["linkify"] = False
        return md

    def _plain(self, content: str, env: dict[str, Any]) -> str:
        """Текст заголовка без разметки: `# Раздел с [ссылкой](a.md)` → `Раздел с ссылкой`."""
        if not _MARKUP.search(content):
            return content.strip()
        parts: list[str] = []
        for token in self._inline.parseInline(content, env):
            self._flatten(token, parts)
        return "".join(parts).strip()

    @classmethod
    def _flatten(cls, token: Token, parts: list[str]) -> None:
        """Собирает текстовые куски inline-дерева заголовка."""
        for child in token.children or ():
            if child.type in {"text", "code_inline"}:
                parts.append(child.content)
            if child.children:
                cls._flatten(child, parts)
