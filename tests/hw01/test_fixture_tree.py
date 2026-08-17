"""Тесты генератора тестовых деревьев hw01 (T-02).

Проверяются свойства, а не печать:

1. `reference()` в двух разных `tmp_path` даёт побайтово одинаковые деревья.
2. Числа файлов и ссылок совпадают с `Expectations`.
3. Битых ровно 7, и каждая действительно битая (проверка резолвом по диску);
   зеркально — каждая небитая локальная/якорная ссылка действительно резолвится.
4. Каждый «злой» случай присутствует в дереве (по одному assert на случай).
5. `generated(files=50, seed=1)` даёт ровно 50 файлов; другой сид — другое дерево.
6. Повторный вызов при существующем каталоге не падает и не портит дерево.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.mdscan.enums.link_kind import LinkKind
from homework.hw01_mdlinks.support.expectations import REFERENCE_EXPECTATIONS, ReferenceTree
from homework.hw01_mdlinks.support.fixture_tree_builder import FixtureTreeBuilder

MD_EXTENSIONS = (".md", ".markdown")
STAMP_NAME = ".fixture_stamp"

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<text>.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(?P<fence>`{3,}|~{3,})")
_PUNCT_RE = re.compile(r"[^\w\s-]")


# ─────────────────────────────────────────────────────────────────────────────
#  Хелперы теста (независимая от core.mdscan проверка ссылок)
# ─────────────────────────────────────────────────────────────────────────────


def _snapshot(root: Path) -> dict[str, bytes]:
    """Всё дерево в виде «относительный путь POSIX → байты» — для сравнения."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _md_files(root: Path) -> list[Path]:
    """Файлы Markdown дерева (`.md` + `.markdown`)."""
    return sorted(path for path in root.rglob("*") if path.suffix in MD_EXTENSIONS)


def _slugs(text: str) -> set[str]:
    """GitHub-slug'и заголовков файла; заголовки внутри fenced code игнорируются."""
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    fence: str | None = None
    for line in text.splitlines():
        opening = _FENCE_RE.match(line)
        if opening is not None:
            marker = opening.group("fence")[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        heading = _HEADING_RE.match(line)
        if heading is None:
            continue
        base = _PUNCT_RE.sub("", heading.group("text").strip().lower()).replace(" ", "-")
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.add(base if count == 0 else f"{base}-{count}")
    return slugs


def _is_broken(root: Path, rel_path: str, target: str) -> bool:
    """`True`, если локальная/якорная цель не резолвится от файла-владельца."""
    owner = root / rel_path
    path_part, _, anchor = target.partition("#")
    target_file = owner if path_part == "" else owner.parent / path_part
    if not target_file.exists():
        return True
    if not anchor:
        return False
    return anchor not in _slugs(target_file.read_text(encoding="utf-8-sig", errors="replace"))


def _checkable_links(expectations_links: frozenset[tuple[str, str, LinkKind]]) -> list[tuple[str, str]]:
    """Локальные и якорные ссылки, кроме `file://` (её политика — за T-07)."""
    return [
        (rel_path, target)
        for rel_path, target, kind in sorted(expectations_links)
        if kind in (LinkKind.LOCAL, LinkKind.ANCHOR) and not target.startswith("file://")
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  1. Детерминизм
# ─────────────────────────────────────────────────────────────────────────────


def test_reference_is_byte_identical_in_two_roots(tmp_path: Path) -> None:
    """Тест 1: два построения в разных каталогах совпадают побайтово."""
    builder = FixtureTreeBuilder()
    first = builder.reference(tmp_path / "one").root
    second = builder.reference(tmp_path / "two").root

    assert _snapshot(first) == _snapshot(second)


# ─────────────────────────────────────────────────────────────────────────────
#  2. Числа совпадают с ожиданиями
# ─────────────────────────────────────────────────────────────────────────────


def test_files_and_links_match_expectations(reference_tree: ReferenceTree) -> None:
    """Тест 2: файлов на диске и ссылок в эталоне ровно столько, сколько заявлено."""
    expectations = reference_tree.expectations

    assert len(_md_files(reference_tree.root)) == expectations.files_total
    assert len(expectations.links) == expectations.links_total
    assert sum(expectations.links_by_kind.values()) == expectations.links_total


def test_links_by_kind_covers_all_kinds(reference_tree: ReferenceTree) -> None:
    """Разбивка по категориям содержит все значения `LinkKind` (в т.ч. нулевые)."""
    assert set(reference_tree.expectations.links_by_kind) == set(LinkKind)


def test_every_expected_link_belongs_to_existing_file(reference_tree: ReferenceTree) -> None:
    """Каждая тройка эталона ссылается на реально существующий файл дерева."""
    for rel_path, _, _ in sorted(reference_tree.expectations.links):
        assert (reference_tree.root / rel_path).is_file(), rel_path


# ─────────────────────────────────────────────────────────────────────────────
#  3. Битые ссылки
# ─────────────────────────────────────────────────────────────────────────────


def test_broken_total_is_seven(reference_tree: ReferenceTree) -> None:
    """Тест 3: битых ровно 7 (решение Alex)."""
    expectations = reference_tree.expectations

    assert expectations.broken_total == 7
    assert len(expectations.broken) == 7


def test_declared_broken_links_are_really_broken(reference_tree: ReferenceTree) -> None:
    """Каждая заявленная битой ссылка не резолвится на диске."""
    for rel_path, target in sorted(reference_tree.expectations.broken):
        assert _is_broken(reference_tree.root, rel_path, target), f"{rel_path} -> {target}"


def test_other_local_links_resolve(reference_tree: ReferenceTree) -> None:
    """Зеркальная проверка: все остальные локальные/якорные ссылки живые."""
    broken = reference_tree.expectations.broken
    for rel_path, target in _checkable_links(reference_tree.expectations.links):
        if (rel_path, target) in broken:
            continue
        assert not _is_broken(reference_tree.root, rel_path, target), f"{rel_path} -> {target}"


# ─────────────────────────────────────────────────────────────────────────────
#  4. «Злые» случаи
# ─────────────────────────────────────────────────────────────────────────────

EVIL_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("fenced_code", "docs/guide/deep/fenced.md", "[Эта ссылка внутри fenced code не извлекается]"),
    ("inline_code", "docs/guide/deep/fenced.md", "`[и эта](nope.md)`"),
    ("reference_link_use", "docs/guide/deep/more/refs.md", "[обзор][ov]"),
    ("reference_link_def", "docs/guide/deep/more/refs.md", "[ov]: ../../overview.md"),
    ("path_with_spaces", "docs/guide/overview.md", "(<path with spaces.md>)"),
    ("parent_relative", "docs/guide/overview.md", "(../../README.md)"),
    ("broken_file", "docs/index.md", "(missing/nope.md)"),
    ("broken_anchor", "docs/install.md", "(#нет-такого)"),
    ("anchor_in_other_file", "docs/index.md", "(install.md#установка)"),
    ("file_url", "assets/media.md", "(file:///tmp/report.html)"),
    ("mailto", "misc/contacts.md", "(mailto:support@example.org)"),
    ("tel", "misc/contacts.md", "(tel:+78120000000)"),
    ("external_url", "misc/contacts.md", "(https://example.org/contacts)"),
    ("github_url", "README.md", "(https://github.com/dsp-gpu/mdscan)"),
    ("wikilink", "misc/wiki.md", "[[project-notes]]"),
    ("footnote_url", "misc/footnotes.md", "[^1]: Подробности — <https://example.org/footnote-spec>"),
    ("image", "assets/media.md", "![Логотип](img/logo.png)"),
)

EVIL_PATHS: tuple[tuple[str, str], ...] = (
    ("cyrillic_dir", "notes/личное/дневник.md"),
    ("cyrillic_file", "docs/справка.md"),
    ("spaces_in_name", "docs/guide/path with spaces.md"),
    ("markdown_extension", "docs/guide/extra.markdown"),
    ("depth_five", "docs/guide/deep/more/level5.md"),
)


@pytest.mark.parametrize(("case_id", "rel_path", "marker"), EVIL_MARKERS, ids=[c[0] for c in EVIL_MARKERS])
def test_evil_case_marker_present(
    reference_tree: ReferenceTree, case_id: str, rel_path: str, marker: str
) -> None:
    """Тест 4: «злой» случай присутствует в тексте нужного файла."""
    text = (reference_tree.root / rel_path).read_text(encoding="utf-8-sig")

    assert marker in text, case_id


@pytest.mark.parametrize(("case_id", "rel_path"), EVIL_PATHS, ids=[c[0] for c in EVIL_PATHS])
def test_evil_case_path_present(reference_tree: ReferenceTree, case_id: str, rel_path: str) -> None:
    """Тест 4: «злой» случай присутствует как отдельный файл дерева."""
    assert (reference_tree.root / rel_path).is_file(), case_id


def test_utf8_sig_file_has_bom(reference_tree: ReferenceTree) -> None:
    """Тест 4: файл в UTF-8-SIG начинается с BOM."""
    assert (reference_tree.root / "encoding/utf8_sig.md").read_bytes().startswith(b"\xef\xbb\xbf")


def test_broken_byte_file_is_not_valid_utf8(reference_tree: ReferenceTree) -> None:
    """Тест 4: файл с битым байтом не читается строгим UTF-8."""
    with pytest.raises(UnicodeDecodeError):
        (reference_tree.root / "encoding/broken_byte.md").read_bytes().decode("utf-8")


def test_empty_md_is_empty(reference_tree: ReferenceTree) -> None:
    """Тест 4: пустой `.md` действительно нулевого размера."""
    assert (reference_tree.root / "encoding/empty.md").stat().st_size == 0


# ─────────────────────────────────────────────────────────────────────────────
#  5–6. Набор B и переиспользование каталога
# ─────────────────────────────────────────────────────────────────────────────


def test_generated_creates_requested_number_of_files(tmp_path: Path) -> None:
    """Тест 5: `generated(files=50, seed=1)` даёт ровно 50 файлов `.md`."""
    root = FixtureTreeBuilder().generated(tmp_path / "gen", files=50, seed=1)

    assert len(_md_files(root)) == 50


def test_generated_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    """Тест 5: один сид — побайтово одно и то же дерево."""
    builder = FixtureTreeBuilder()
    first = builder.generated(tmp_path / "a", files=20, seed=7)
    second = builder.generated(tmp_path / "b", files=20, seed=7)

    assert _snapshot(first) == _snapshot(second)


def test_generated_differs_for_other_seed(tmp_path: Path) -> None:
    """Тест 5: другой сид — другое дерево."""
    builder = FixtureTreeBuilder()
    first = builder.generated(tmp_path / "a", files=20, seed=1)
    second = builder.generated(tmp_path / "b", files=20, seed=2)

    assert _snapshot(first) != _snapshot(second)


def test_generated_rejects_non_positive_files(tmp_path: Path) -> None:
    """Число файлов ≤ 0 — понятная ошибка, а не пустое дерево."""
    with pytest.raises(ValueError, match="files"):
        FixtureTreeBuilder().generated(tmp_path / "gen", files=0, seed=1)


def test_reference_reuses_existing_directory(tmp_path: Path) -> None:
    """Тест 6: повторный вызов на существующем каталоге не падает и не меняет дерево."""
    builder = FixtureTreeBuilder()
    root = tmp_path / "tree"
    first = builder.reference(root)
    before = _snapshot(first.root)

    second = builder.reference(root)

    assert second.root == first.root
    assert second.expectations == REFERENCE_EXPECTATIONS
    assert _snapshot(second.root) == before


def test_reference_rebuilds_stale_directory(tmp_path: Path) -> None:
    """Каталог от другой версии генератора пересобирается, а не переиспользуется."""
    builder = FixtureTreeBuilder()
    root = tmp_path / "tree"
    builder.reference(root)
    (root / STAMP_NAME).write_text("reference v0 stale", encoding="utf-8")
    (root / "README.md").write_text("мусор", encoding="utf-8")

    builder.reference(root)

    assert (root / "README.md").read_text(encoding="utf-8").startswith("# Тестовое дерево hw01")


def test_generated_reuses_existing_directory(tmp_path: Path) -> None:
    """Тест 6: то же для набора B — повторный вызов с теми же параметрами безопасен."""
    builder = FixtureTreeBuilder()
    root = tmp_path / "gen"
    builder.generated(root, files=10, seed=3)
    before = _snapshot(root)

    builder.generated(root, files=10, seed=3)

    assert _snapshot(root) == before
