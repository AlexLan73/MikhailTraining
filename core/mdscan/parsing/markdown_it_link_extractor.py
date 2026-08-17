"""Извлечение ссылок из Markdown готовым парсером `markdown-it-py` (решение D7).

Regex по тексту не пишем: три самых дорогих в отладке случая — код-блоки,
reference-ссылки `[t][id]` и номер строки — у токенизатора решены by design
(fenced/inline code не порождают link-токенов вообще, метки резолвит сам парсер,
строка берётся из `token.map`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.footnote import footnote_plugin

from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.models.md_link import MdLink

logger = logging.getLogger("core.mdscan.parsing")

#: Тип токена нашего собственного inline-правила `[[wiki]]`.
_WIKILINK_TOKEN = "wikilink"


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    """Inline-правило `[[Страница]]` / `[[Страница|подпись]]` для `markdown-it`.

    Пишем своё: в установленном `mdit-py-plugins` 0.6.1 плагина `wikilinks` нет.
    Правило встроено в inline-цепочку парсера, поэтому внутри code-блоков не
    работает; regex по всему тексту дал бы ссылки из ``` fenced code ```.
    """
    source, pos = state.src, state.pos
    if not source.startswith("[[", pos):
        return False
    end = source.find("]]", pos + 2)
    if end < 0:
        return False
    body = source[pos + 2 : end]
    if not body.strip() or "\n" in body or "[" in body or "]" in body:
        return False
    if not silent:
        token = state.push(_WIKILINK_TOKEN, "", 0)
        token.content = body.split("|", 1)[0].strip()
        token.markup = "[["
    state.pos = end + 2
    return True


def _allow_any_link(url: str) -> bool:
    """Мы сканируем, а не рендерим HTML: штатный `validateLink` режет `file:` — нам он нужен."""
    return True


def _keep_link_as_is(url: str) -> str:
    """Отключает percent-кодирование цели: `справка.md` должна остаться собой."""
    return url


class MarkdownItLinkExtractor:
    """Реализация `LinkExtractor` на `markdown-it-py` + плагинах (`parser.*` конфига).

    Заполняет `target`, `origin`, `line`; `kind` остаётся `UNKNOWN` — категорию
    ставит `LinkClassifier` (D8). `line` — строка **блока** со ссылкой (`token.map`
    есть только у блочных токенов); для списков, заголовков и однострочных абзацев
    это точная строка ссылки.
    """

    _DEFAULT_PRESET = "gfm-like"
    _DEFAULT_PLUGINS: tuple[str, ...] = ("footnote", "attrs", "wikilinks")

    def __init__(
        self,
        preset: str = _DEFAULT_PRESET,
        plugins: Sequence[str] = _DEFAULT_PLUGINS,
    ) -> None:
        self._md = self._build(preset, plugins)

    def extract(self, text: str) -> tuple[MdLink, ...]:
        """Все ссылки текста по порядку появления; из code-блоков — ни одной."""
        found: list[MdLink] = []
        line = 1
        footnotes = 0
        for token in self._md.parse(text):
            if token.map is not None:
                line = token.map[0] + 1
            if token.type == "footnote_open":
                footnotes += 1
            elif token.type == "footnote_close":
                footnotes = max(0, footnotes - 1)
            elif token.type == "inline":
                self._collect(token.children or (), line, footnotes > 0, found)
        logger.debug("извлечено ссылок: %d", len(found))
        return tuple(found)

    # ── приватные хелперы ────────────────────────────────────────────────────

    @staticmethod
    def _build(preset: str, plugins: Sequence[str]) -> MarkdownIt:
        """Собирает парсер: пресет, плагины из конфига, наши правила разбора цели."""
        md = MarkdownIt(preset, {"store_labels": True})
        md.validateLink = _allow_any_link  # type: ignore[method-assign]
        md.normalizeLink = _keep_link_as_is  # type: ignore[method-assign]
        if md.linkify is None and md.options.get("linkify"):
            logger.warning("linkify-it-py не установлен — автораспознавание голых URL выключено")
            md.options["linkify"] = False
        elif md.linkify is not None:
            # Боевой прогон dsp-gpu: «fuzzy»-режим linkify превращал имена файлов `Full.md`, `conftest.py`,
            # `prng.cl` в URL (`.md`/`.py`/`.cl` — доменные зоны) → десятки ложных BROKEN.
            # Голый URL считаем ссылкой только со схемой (`https://…`) или `www.`.
            md.linkify.set({"fuzzy_link": False, "fuzzy_email": False})
        for name in plugins:
            if name == "footnote":
                md.use(footnote_plugin)
            elif name == "attrs":
                md.use(attrs_plugin)
            elif name == "wikilinks":
                md.inline.ruler.before("link", _WIKILINK_TOKEN, _wikilink_rule)
            else:
                logger.warning("плагин parser.plugins «%s» неизвестен — пропущен", name)
        return md

    @classmethod
    def _collect(
        cls,
        tokens: Iterable[Token],
        line: int,
        in_footnote: bool,
        found: list[MdLink],
    ) -> None:
        """Рекурсивно обходит inline-токены и складывает найденные ссылки."""
        for token in tokens:
            target = cls._target(token)
            if target:
                link = MdLink(target=target, origin=cls._origin(token, in_footnote), line=line)
                logger.debug("ссылка %s (%s) строка %d", link.target, link.origin.value, link.line)
                found.append(link)
            if token.children:
                cls._collect(token.children, line, in_footnote, found)

    @staticmethod
    def _target(token: Token) -> str:
        """Цель ссылки для токенов-носителей; для остальных — пустая строка."""
        if token.type == "link_open":
            return str(token.attrs.get("href", "")).strip()
        if token.type == "image":
            return str(token.attrs.get("src", "")).strip()
        if token.type == _WIKILINK_TOKEN:
            return token.content.strip()
        return ""

    @staticmethod
    def _origin(token: Token, in_footnote: bool) -> LinkOrigin:
        """Синтаксис, которым записана ссылка (нужен правилам wikilink/footnote)."""
        if token.type == _WIKILINK_TOKEN:
            return LinkOrigin.WIKILINK
        if in_footnote:
            return LinkOrigin.FOOTNOTE
        if token.markup == "autolink":
            return LinkOrigin.AUTOLINK
        if token.meta.get("label"):
            return LinkOrigin.REFERENCE
        return LinkOrigin.INLINE
