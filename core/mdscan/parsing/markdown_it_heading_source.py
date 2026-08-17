"""Заголовки Markdown-файла — источник данных для проверки якорей (`#раздел`).

Класс структурно реализует `checking.HeadingSource` (владелец контракта — T-07).
Импортировать `core.mdscan.checking.*` здесь **нельзя**: модули пишутся в одной
волне, файла контракта ещё нет; совпадение сигнатур проверит `mypy` на приёмке
(спека разработки §2.5).
"""

from __future__ import annotations

import logging

from markdown_it import MarkdownIt
from markdown_it.token import Token

logger = logging.getLogger("core.mdscan.parsing")


class MarkdownItHeadingSource:
    """Тексты заголовков всех уровней в порядке появления.

    Берём тем же токенизатором, что и ссылки: заголовок внутри ``` fenced code ```
    заголовком не является, а `## Как запустить` в кавычках/списке — является ровно
    тогда, когда так считает GitHub. Своего разбора `#` в начале строки не пишем.

    Возвращается **текст** заголовка (`## Как запустить` → `Как запустить`);
    превращение текста в GitHub-slug — дело `AnchorChecker` (T-07).
    """

    _DEFAULT_PRESET = "gfm-like"

    def __init__(self, preset: str = _DEFAULT_PRESET) -> None:
        md = MarkdownIt(preset)
        if md.linkify is None and md.options.get("linkify"):
            md.options["linkify"] = False
        self._md = md

    def headings(self, text: str) -> tuple[str, ...]:
        """Тексты заголовков `h1…h6` по порядку; из code-блоков — ни одного."""
        titles: list[str] = []
        expect_inline = False
        for token in self._md.parse(text):
            if token.type == "heading_open":
                expect_inline = True
            elif expect_inline and token.type == "inline":
                titles.append(self._plain(token))
                expect_inline = False
        logger.debug("заголовков найдено: %d", len(titles))
        return tuple(titles)

    # ── приватные хелперы ────────────────────────────────────────────────────

    @classmethod
    def _plain(cls, token: Token) -> str:
        """Текст заголовка без разметки: `# Раздел с [ссылкой](a.md)` → `Раздел с ссылкой`."""
        parts: list[str] = []
        cls._flatten(token, parts)
        return "".join(parts).strip()

    @classmethod
    def _flatten(cls, token: Token, parts: list[str]) -> None:
        """Собирает текстовые куски inline-дерева заголовка."""
        for child in token.children or ():
            if child.type in {"text", "code_inline"}:
                parts.append(child.content)
            if child.children:
                cls._flatten(child, parts)
