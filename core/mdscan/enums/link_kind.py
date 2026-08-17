"""Категория ссылки — по ней выбирается чекер (`CheckerFactory.for_kind`)."""

from __future__ import annotations

from enum import Enum


class LinkKind(Enum):
    """Что за ссылка по существу цели, а не по синтаксису (синтаксис — `LinkOrigin`)."""

    LOCAL = "local"                 # путь к файлу в дереве репозитория
    ANCHOR = "anchor"               # якорь `#заголовок` в своём файле
    GITHUB = "github"               # URL на github.com (проверяется до общего URL)
    URL = "url"                     # прочий http(s)-адрес
    MAILTO = "mailto"               # mailto:
    TEL = "tel"                     # tel:
    WIKILINK = "wikilink"           # [[wikilink]]
    FOOTNOTE_URL = "footnote_url"   # цель сноски [^1]
    UNKNOWN = "unknown"             # не подошло ни одно правило классификации
