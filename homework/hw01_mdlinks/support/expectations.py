"""Ожидания эталонного дерева (набор A) для hw01.

Набор A — фиксированное дерево `.md`, которое строит
:class:`homework.hw01_mdlinks.support.fixture_tree_builder.FixtureTreeBuilder`.
Здесь лежит **эталон**: сколько в нём файлов, сколько ссылок каждой категории,
полный список троек ``(rel_path, target, kind)`` и перечень битых ссылок.

Почему рядом с генератором, а не в json (спека разработки §3.4): ожидания и дерево
меняются одной правкой — так они не могут разъехаться.

`rel_path` — путь файла относительно корня дерева в POSIX-виде (разделитель `/`),
одинаковый на Windows и Linux.

Модуль — **данные** (как `enums` / `config`), поэтому в нём два неизменяемых
value object и таблицы-константы, а не логика.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from core.mdscan.enums.link_kind import LinkKind

# ─────────────────────────────────────────────────────────────────────────────
#  Value objects
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Expectations:
    """Эталонные числа набора A — на них опираются тесты качества (T-06, T-13)."""

    files_total: int
    """Сколько файлов Markdown (`.md` + `.markdown`) в дереве."""

    links_total: int
    """Сколько ссылок извлекается из дерева (внутри code-блоков — не считаются)."""

    broken_total: int
    """Сколько ссылок битые (только локальные и якорные, см. `broken`)."""

    links_by_kind: dict[LinkKind, int]
    """Разбивка ссылок по категориям; присутствуют все значения `LinkKind`."""

    links: frozenset[tuple[str, str, LinkKind]]
    """Полный эталон извлечения: `(rel_path, target, kind)`."""

    broken: frozenset[tuple[str, str]]
    """Битые ссылки: `(rel_path, target)` — перечень зафиксирован вручную."""


@dataclass(frozen=True, slots=True)
class ReferenceTree:
    """Построенное дерево набора A: корень на диске + его ожидания."""

    root: Path
    expectations: Expectations


# ─────────────────────────────────────────────────────────────────────────────
#  Эталон набора A
# ─────────────────────────────────────────────────────────────────────────────

#: Файлов Markdown в дереве (`.md` + один `.markdown`).
FILES_TOTAL: int = 28

#: Полный список ссылок эталона: (rel_path, target, kind).
#: Порядок — как в дереве; ссылки внутри fenced/inline code сюда НЕ входят.
REFERENCE_LINKS: tuple[tuple[str, str, LinkKind], ...] = (
    # ── корень ───────────────────────────────────────────────────────────────
    ("README.md", "docs/index.md", LinkKind.LOCAL),
    ("README.md", "docs/install.md#установка", LinkKind.LOCAL),
    ("README.md", "https://github.com/dsp-gpu/mdscan", LinkKind.GITHUB),
    ("README.md", "#разделы", LinkKind.ANCHOR),
    ("CHANGELOG.md", "docs/index.md", LinkKind.LOCAL),
    ("CHANGELOG.md", "https://github.com/dsp-gpu/mdscan/issues/1", LinkKind.GITHUB),
    ("CHANGELOG.md", "https://example.org/spec", LinkKind.URL),
    # ── docs/ ────────────────────────────────────────────────────────────────
    ("docs/index.md", "справка.md", LinkKind.LOCAL),
    ("docs/index.md", "install.md#установка", LinkKind.LOCAL),
    ("docs/index.md", "missing/nope.md", LinkKind.LOCAL),
    ("docs/index.md", "guide/overview.md", LinkKind.LOCAL),
    ("docs/install.md", "#нет-такого", LinkKind.ANCHOR),
    ("docs/install.md", "#установка", LinkKind.ANCHOR),
    ("docs/install.md", "api/reference.md", LinkKind.LOCAL),
    ("docs/справка.md", "index.md", LinkKind.LOCAL),
    ("docs/справка.md", "install.md", LinkKind.LOCAL),
    ("docs/справка.md", "mailto:help@example.org", LinkKind.MAILTO),
    # ── docs/guide/ ──────────────────────────────────────────────────────────
    ("docs/guide/overview.md", "path with spaces.md", LinkKind.LOCAL),
    ("docs/guide/overview.md", "../../README.md", LinkKind.LOCAL),
    ("docs/guide/overview.md", "extra.markdown", LinkKind.LOCAL),
    ("docs/guide/overview.md", "https://example.org/guide", LinkKind.URL),
    ("docs/guide/path with spaces.md", "overview.md", LinkKind.LOCAL),
    ("docs/guide/path with spaces.md", "deep/level4.md", LinkKind.LOCAL),
    ("docs/guide/path with spaces.md", "https://example.com/", LinkKind.URL),
    ("docs/guide/extra.markdown", "overview.md", LinkKind.LOCAL),
    ("docs/guide/extra.markdown", "../../notes/todo.md", LinkKind.LOCAL),
    ("docs/guide/extra.markdown", "https://github.com/dsp-gpu/tools", LinkKind.GITHUB),
    # ── docs/guide/deep/ ─────────────────────────────────────────────────────
    ("docs/guide/deep/level4.md", "#нет-раздела", LinkKind.ANCHOR),
    ("docs/guide/deep/level4.md", "#глубина", LinkKind.ANCHOR),
    ("docs/guide/deep/level4.md", "more/level5.md", LinkKind.LOCAL),
    ("docs/guide/deep/level4.md", "../overview.md", LinkKind.LOCAL),
    ("docs/guide/deep/fenced.md", "level4.md", LinkKind.LOCAL),
    ("docs/guide/deep/fenced.md", "../../index.md", LinkKind.LOCAL),
    # ── docs/guide/deep/more/ (глубина 5) ────────────────────────────────────
    ("docs/guide/deep/more/level5.md", "../level4.md", LinkKind.LOCAL),
    ("docs/guide/deep/more/level5.md", "refs.md", LinkKind.LOCAL),
    ("docs/guide/deep/more/level5.md", "../../../../README.md", LinkKind.LOCAL),
    ("docs/guide/deep/more/refs.md", "../../overview.md", LinkKind.LOCAL),
    ("docs/guide/deep/more/refs.md", "../level4.md", LinkKind.LOCAL),
    # ── docs/api/ ────────────────────────────────────────────────────────────
    ("docs/api/reference.md", "errors.md", LinkKind.LOCAL),
    ("docs/api/reference.md", "errors.md#несуществующий-раздел", LinkKind.LOCAL),
    ("docs/api/reference.md", "#функции", LinkKind.ANCHOR),
    ("docs/api/reference.md", "../index.md", LinkKind.LOCAL),
    ("docs/api/errors.md", "#коды-возврата", LinkKind.ANCHOR),
    ("docs/api/errors.md", "reference.md", LinkKind.LOCAL),
    ("docs/api/errors.md", "https://github.com/dsp-gpu/mdscan/issues/2", LinkKind.GITHUB),
    # ── encoding/ (utf-8-sig, битый байт, пустой файл) ───────────────────────
    ("encoding/utf8_sig.md", "../README.md", LinkKind.LOCAL),
    ("encoding/utf8_sig.md", "empty.md", LinkKind.LOCAL),
    ("encoding/utf8_sig.md", "https://example.org/encoding", LinkKind.URL),
    # encoding/broken_byte.md — не читается (MarkdownReadError), ссылок нет
    # encoding/empty.md — пустой, ссылок нет
    # ── notes/ ───────────────────────────────────────────────────────────────
    ("notes/todo.md", "../docs/guide/absent.md", LinkKind.LOCAL),
    ("notes/todo.md", "links.md", LinkKind.LOCAL),
    ("notes/todo.md", "личное/дневник.md", LinkKind.LOCAL),
    ("notes/todo.md", "https://example.org/tracker", LinkKind.URL),
    ("notes/links.md", "https://example.org/auto", LinkKind.URL),
    ("notes/links.md", "https://github.com/dsp-gpu", LinkKind.GITHUB),
    ("notes/links.md", "todo.md", LinkKind.LOCAL),
    ("notes/links.md", "../docs/index.md", LinkKind.LOCAL),
    ("notes/личное/дневник.md", "планы.md", LinkKind.LOCAL),
    ("notes/личное/дневник.md", "../todo.md", LinkKind.LOCAL),
    ("notes/личное/дневник.md", "https://example.org/diary", LinkKind.URL),
    ("notes/личное/планы.md", "отсутствует.md", LinkKind.LOCAL),
    ("notes/личное/планы.md", "дневник.md", LinkKind.LOCAL),
    ("notes/личное/планы.md", "../../README.md", LinkKind.LOCAL),
    # ── src/ ─────────────────────────────────────────────────────────────────
    ("src/README.md", "module.md", LinkKind.LOCAL),
    ("src/README.md", "../docs/index.md", LinkKind.LOCAL),
    ("src/README.md", "https://github.com/dsp-gpu/mdscan/tree/main/src", LinkKind.GITHUB),
    ("src/module.md", "../lib/missing.md", LinkKind.LOCAL),
    ("src/module.md", "README.md", LinkKind.LOCAL),
    ("src/module.md", "../docs/api/reference.md", LinkKind.LOCAL),
    # ── assets/ (картинка + file:///) ────────────────────────────────────────
    ("assets/media.md", "img/logo.png", LinkKind.LOCAL),
    ("assets/media.md", "file:///tmp/report.html", LinkKind.LOCAL),
    ("assets/media.md", "legal.md", LinkKind.LOCAL),
    ("assets/legal.md", "https://example.org/mit", LinkKind.URL),
    ("assets/legal.md", "media.md", LinkKind.LOCAL),
    ("assets/legal.md", "mailto:legal@example.org", LinkKind.MAILTO),
    # ── misc/ (mailto, tel, wikilink, сноска) ────────────────────────────────
    ("misc/contacts.md", "mailto:support@example.org", LinkKind.MAILTO),
    ("misc/contacts.md", "tel:+78120000000", LinkKind.TEL),
    ("misc/contacts.md", "https://example.org/contacts", LinkKind.URL),
    ("misc/wiki.md", "project-notes", LinkKind.WIKILINK),
    ("misc/wiki.md", "contacts.md", LinkKind.LOCAL),
    ("misc/wiki.md", "footnotes.md", LinkKind.LOCAL),
    ("misc/footnotes.md", "wiki.md", LinkKind.LOCAL),
    ("misc/footnotes.md", "https://example.org/footnote-spec", LinkKind.FOOTNOTE_URL),
)

#: Битые ссылки набора A — ровно 7 (решение Alex, часть 1 D1).
#:
#: Битыми считаются **только локальные и якорные** цели: внешние URL и GitHub-URL
#: при прогоне тестов не проверяются (`http.enabled: false`), поэтому в перечень
#: не входят. Цель `file:///tmp/report.html` (assets/media.md) — «злой» случай для
#: классификатора; её проверка зависит от политики T-07 и в число битых сознательно
#: **не** включена.
REFERENCE_BROKEN: tuple[tuple[str, str], ...] = (
    ("docs/index.md", "missing/nope.md"),                          # нет файла
    ("docs/install.md", "#нет-такого"),                            # нет якоря в своём файле
    ("docs/guide/deep/level4.md", "#нет-раздела"),                 # нет якоря в своём файле
    ("docs/api/reference.md", "errors.md#несуществующий-раздел"),  # файл есть, якоря нет
    ("notes/todo.md", "../docs/guide/absent.md"),                  # нет файла
    ("notes/личное/планы.md", "отсутствует.md"),                   # нет файла (кириллица)
    ("src/module.md", "../lib/missing.md"),                        # нет каталога и файла
)


def _links_by_kind() -> dict[LinkKind, int]:
    """Разбивка `REFERENCE_LINKS` по категориям — все значения `LinkKind` присутствуют."""
    counter = Counter(kind for _, _, kind in REFERENCE_LINKS)
    return {kind: counter.get(kind, 0) for kind in LinkKind}


#: Готовые ожидания набора A — единственный публичный эталон.
REFERENCE_EXPECTATIONS: Expectations = Expectations(
    files_total=FILES_TOTAL,
    links_total=len(REFERENCE_LINKS),
    broken_total=len(REFERENCE_BROKEN),
    links_by_kind=_links_by_kind(),
    links=frozenset(REFERENCE_LINKS),
    broken=frozenset(REFERENCE_BROKEN),
)
