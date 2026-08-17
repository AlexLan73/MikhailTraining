"""Тесты модуля `core.mdscan.parsing` (T-06): чтение, извлечение, классификация.

Номера тестов соответствуют списку таска T-06
(`MemoryBank/tasks/TASK_hw01_modules_T01-T15.md`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin
from core.mdscan.errors import MarkdownReadError
from core.mdscan.models.md_link import MdLink
from core.mdscan.parsing.link_classifier import LinkClassifier
from core.mdscan.parsing.markdown_it_heading_source import MarkdownItHeadingSource
from core.mdscan.parsing.markdown_it_link_extractor import MarkdownItLinkExtractor
from core.mdscan.parsing.markdown_reader import MarkdownReader
from core.mdscan.parsing.rules.rule_github import GithubRule
from core.mdscan.parsing.rules.rule_http import HttpRule
from core.mdscan.parsing.rules.rule_local_path import LocalPathRule
from core.metrics.classification import accuracy, f1_score
from homework.hw01_mdlinks.support.expectations import ReferenceTree

#: Пороги качества на наборе A (часть 2, §9.2).
EXTRACT_F1_THRESHOLD = 0.95
CLASSIFY_ACCURACY_THRESHOLD = 0.98

#: Расширения Markdown, которые обходит сканер (`scan.md_extensions`).
MD_SUFFIXES = frozenset({".md", ".markdown"})


@pytest.fixture
def extractor() -> MarkdownItLinkExtractor:
    """Экстрактор со штатным пресетом и плагинами (`parser.*` по умолчанию)."""
    return MarkdownItLinkExtractor()


@pytest.fixture
def classifier() -> LinkClassifier:
    """Канонический порядок 9 правил (D8.3)."""
    return LinkClassifier.default()


def link(target: str, origin: LinkOrigin = LinkOrigin.INLINE) -> MdLink:
    """Ссылка-заготовка для проверок классификации (строка не важна)."""
    return MdLink(target=target, origin=origin, line=1)


# ─────────────────────────────────────────────────────────────────────────────
#  1. Все виды синтаксиса извлекаются
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "target", "origin"),
    [
        ("[x](docs/a.md)", "docs/a.md", LinkOrigin.INLINE),
        ("![x](img/a.png)", "img/a.png", LinkOrigin.INLINE),
        ("[t][id]\n\n[id]: docs/a.md\n", "docs/a.md", LinkOrigin.REFERENCE),
        ("<https://example.org/a>", "https://example.org/a", LinkOrigin.AUTOLINK),
        ("Смотри [[wiki]].", "wiki", LinkOrigin.WIKILINK),
        (
            "Текст[^1].\n\n[^1]: см. <https://example.org/f>\n",
            "https://example.org/f",
            LinkOrigin.FOOTNOTE,
        ),
        ("[пробелы](<path with spaces.md>)", "path with spaces.md", LinkOrigin.INLINE),
        ("[кириллица](справка.md)", "справка.md", LinkOrigin.INLINE),
    ],
    ids=[
        "inline",
        "image",
        "reference",
        "autolink",
        "wikilink",
        "footnote",
        "spaces-in-path",
        "cyrillic-path",
    ],
)
def test_extract_returns_single_link_with_origin(
    extractor: MarkdownItLinkExtractor, text: str, target: str, origin: LinkOrigin
) -> None:
    """Каждый вид синтаксиса даёт ровно одну ссылку с верной целью и origin."""
    links = extractor.extract(text)

    assert [(one.target, one.origin) for one in links] == [(target, origin)]


def test_extract_leaves_kind_unknown(extractor: MarkdownItLinkExtractor) -> None:
    """Экстрактор категорию не ставит — это ответственность `LinkClassifier`."""
    (found,) = extractor.extract("[x](https://github.com/org/repo)")

    assert found.kind is LinkKind.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
#  2. Ссылки в коде не извлекаются (инвариант 10)
# ─────────────────────────────────────────────────────────────────────────────


def test_links_inside_code_are_not_extracted(extractor: MarkdownItLinkExtractor) -> None:
    """Fenced- и inline-code не порождают ссылок; соседние — извлекаются."""
    text = (
        "# Код\n"
        "\n"
        "```markdown\n"
        "[в fenced](../nowhere.md)\n"
        "[[wiki-в-коде]]\n"
        "<https://example.org/in-code>\n"
        "```\n"
        "\n"
        "Инлайн: `[и эта](nope.md)`.\n"
        "\n"
        "- [живая](real.md)\n"
    )

    assert [one.target for one in extractor.extract(text)] == ["real.md"]


def test_indented_code_block_is_not_extracted(extractor: MarkdownItLinkExtractor) -> None:
    """Блок кода отступом в 4 пробела — тоже код, а не абзац со ссылкой."""
    text = "Текст:\n\n    [в отступе](nope.md)\n\n[живая](real.md)\n"

    assert [one.target for one in extractor.extract(text)] == ["real.md"]


# ─────────────────────────────────────────────────────────────────────────────
#  3. Номер строки
# ─────────────────────────────────────────────────────────────────────────────


def test_line_numbers_match_source(extractor: MarkdownItLinkExtractor) -> None:
    """`line` — 1-based строка блока со ссылкой (из `token.map`)."""
    text = "\n".join(
        [
            "# Заголовок",  # 1
            "",  # 2
            "- [a](a.md)",  # 3
            "- [b](b.md)",  # 4
            "",  # 5
            "Абзац со [c](c.md).",  # 6
            "",  # 7
            "```",  # 8
            "[skip](skip.md)",  # 9
            "```",  # 10
            "",  # 11
            "<https://example.org/d>",  # 12
            "",
        ]
    )

    assert [(one.target, one.line) for one in extractor.extract(text)] == [
        ("a.md", 3),
        ("b.md", 4),
        ("c.md", 6),
        ("https://example.org/d", 12),
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  4. Классификация: таблица «цель → категория»
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "origin", "expected"),
    [
        ("#install", LinkOrigin.INLINE, LinkKind.ANCHOR),
        ("mailto:alex@example.org", LinkOrigin.INLINE, LinkKind.MAILTO),
        ("MAILTO:Alex@Example.org", LinkOrigin.INLINE, LinkKind.MAILTO),
        ("tel:+78120000000", LinkOrigin.INLINE, LinkKind.TEL),
        ("https://github.com/org/repo", LinkOrigin.INLINE, LinkKind.GITHUB),
        ("git@github.com:org/repo.git", LinkOrigin.INLINE, LinkKind.GITHUB),
        ("https://gist.github.com/org/1", LinkOrigin.INLINE, LinkKind.GITHUB),
        ("https://raw.githubusercontent.com/o/r/main/a.md", LinkOrigin.INLINE, LinkKind.GITHUB),
        ("https://example.org/a", LinkOrigin.INLINE, LinkKind.URL),
        ("http://example.org/a", LinkOrigin.INLINE, LinkKind.URL),
        ("https://notgithub.com/org/repo", LinkOrigin.INLINE, LinkKind.URL),
        ("file:///tmp/report.html", LinkOrigin.INLINE, LinkKind.LOCAL),
        ("file:///C:/tmp/a.md", LinkOrigin.INLINE, LinkKind.LOCAL),
        ("docs/a.md", LinkOrigin.INLINE, LinkKind.LOCAL),
        ("../img/x.png", LinkOrigin.INLINE, LinkKind.LOCAL),
        ("a.md#раздел", LinkOrigin.INLINE, LinkKind.LOCAL),
        ("справка.md", LinkOrigin.REFERENCE, LinkKind.LOCAL),
        ("project-notes", LinkOrigin.WIKILINK, LinkKind.WIKILINK),
        ("https://example.org/f", LinkOrigin.FOOTNOTE, LinkKind.FOOTNOTE_URL),
        ("", LinkOrigin.INLINE, LinkKind.UNKNOWN),
    ],
    ids=[
        "anchor",
        "mailto",
        "mailto-upper",
        "tel",
        "github-https",
        "github-ssh",
        "github-gist",
        "github-raw",
        "url-https",
        "url-http",
        "url-lookalike-host",
        "file-url-posix",
        "file-url-windows",
        "local-relative",
        "local-parent",
        "local-with-anchor",
        "local-cyrillic",
        "wikilink",
        "footnote",
        "empty-unknown",
    ],
)
def test_classification_table(
    classifier: LinkClassifier, target: str, origin: LinkOrigin, expected: LinkKind
) -> None:
    """Категория определяется целью и синтаксисом; ничего не подошло → `UNKNOWN`."""
    assert classifier.classify(link(target, origin)) is expected


def test_classify_does_not_mutate_link(classifier: LinkClassifier) -> None:
    """Классификатор возвращает категорию, но сам `MdLink` не трогает (это делает worker)."""
    one = link("https://github.com/org/repo")

    assert classifier.classify(one) is LinkKind.GITHUB
    assert one.kind is LinkKind.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
#  5. Порядок правил: GithubRule строго до HttpRule
# ─────────────────────────────────────────────────────────────────────────────


def test_github_rule_precedes_http_rule_in_default_chain(classifier: LinkClassifier) -> None:
    """В каноническом порядке GitHub-URL → `GITHUB`, а не `URL`."""
    assert classifier.classify(link("https://github.com/dsp-gpu/mdscan")) is LinkKind.GITHUB


def test_swapped_order_downgrades_github_to_url() -> None:
    """Перестановка правил ломает категорию — тест доказывает, что порядок значим."""
    swapped = LinkClassifier([HttpRule(), GithubRule(), LocalPathRule()])

    assert swapped.classify(link("https://github.com/dsp-gpu/mdscan")) is LinkKind.URL


# ─────────────────────────────────────────────────────────────────────────────
#  6. Чтение файла: UTF-8-SIG и битый байт
# ─────────────────────────────────────────────────────────────────────────────


def test_reads_utf8_sig_without_bom_in_text(tmp_path: Path) -> None:
    """BOM снимается: текст начинается с решётки, а не с `\\ufeff`."""
    path = tmp_path / "utf8_sig.md"
    path.write_bytes("# Заголовок\n\n[a](a.md)\n".encode("utf-8-sig"))

    text = MarkdownReader().read(path)

    assert not text.startswith("\ufeff")
    assert text.startswith("# Заголовок")


def test_reads_plain_utf8(tmp_path: Path) -> None:
    """Обычный UTF-8 без BOM читается тем же кодеком — второй ветки нет."""
    path = tmp_path / "plain.md"
    path.write_bytes("# Кириллица\n".encode())

    assert MarkdownReader().read(path) == "# Кириллица\n"


def test_broken_byte_raises_markdown_read_error(tmp_path: Path) -> None:
    """Битый байт → `MarkdownReadError` с путём и позицией, а не `UnicodeDecodeError`."""
    path = tmp_path / "broken_byte.md"
    path.write_bytes(b"# Broken\n\n" + b"\xff\xfe" + b"\n")

    with pytest.raises(MarkdownReadError, match="не UTF-8"):
        MarkdownReader().read(path)


def test_broken_byte_message_contains_position(tmp_path: Path) -> None:
    """В тексте ошибки есть позиция байта — иначе файл не починить."""
    path = tmp_path / "broken_byte.md"
    path.write_bytes(b"abc" + b"\xff")

    with pytest.raises(MarkdownReadError, match=r"позиции 3"):
        MarkdownReader().read(path)


def test_missing_file_raises_markdown_read_error(tmp_path: Path) -> None:
    """Нечитаемый файл — та же ошибка пакета, worker ловит один тип."""
    with pytest.raises(MarkdownReadError, match="не читается"):
        MarkdownReader().read(tmp_path / "нет-такого.md")


# ─────────────────────────────────────────────────────────────────────────────
#  7. Качество на эталонном дереве (набор A)
# ─────────────────────────────────────────────────────────────────────────────


def _scan_tree(root: Path) -> tuple[set[tuple[str, str, LinkKind]], list[str]]:
    """Обходит дерево: `(rel_path, target, kind)` по всем `.md`/`.markdown` + нечитаемые файлы."""
    reader = MarkdownReader()
    extractor = MarkdownItLinkExtractor()
    classifier = LinkClassifier.default()
    found: set[tuple[str, str, LinkKind]] = set()
    unreadable: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MD_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = reader.read(path)
        except MarkdownReadError:
            unreadable.append(rel)
            continue
        for one in extractor.extract(text):
            found.add((rel, one.target, classifier.classify(one)))
    return found, unreadable


def test_extraction_f1_on_reference_tree(reference_tree: ReferenceTree) -> None:
    """Извлечение на наборе A: `f1_score` над объединением множеств троек ≥ 0.95."""
    found, _ = _scan_tree(reference_tree.root)
    expected = reference_tree.expectations.links

    universe = sorted(found | expected, key=str)
    y_true = [1 if item in expected else 0 for item in universe]
    y_pred = [1 if item in found else 0 for item in universe]

    assert f1_score(y_true, y_pred, positive=1) >= EXTRACT_F1_THRESHOLD


def test_classification_accuracy_on_reference_tree(reference_tree: ReferenceTree) -> None:
    """Классификация на наборе A: `accuracy` по совпавшим парам (файл, цель) ≥ 0.98."""
    found, _ = _scan_tree(reference_tree.root)
    expected_kind = {(rel, target): kind for rel, target, kind in reference_tree.expectations.links}
    found_kind = {(rel, target): kind for rel, target, kind in found}

    shared = sorted(set(expected_kind) & set(found_kind), key=str)
    assert shared, "не найдено ни одной ссылки эталона — сравнивать нечего"
    y_true = [expected_kind[key] for key in shared]
    y_pred = [found_kind[key] for key in shared]

    assert accuracy(y_true, y_pred) >= CLASSIFY_ACCURACY_THRESHOLD


def test_reference_tree_broken_byte_file_is_reported(reference_tree: ReferenceTree) -> None:
    """Файл с битым байтом набора A не читается — и это единственный такой файл."""
    _, unreadable = _scan_tree(reference_tree.root)

    assert unreadable == ["encoding/broken_byte.md"]


# ─────────────────────────────────────────────────────────────────────────────
#  8. Заголовки для проверки якорей (HeadingSource)
# ─────────────────────────────────────────────────────────────────────────────


def test_headings_are_returned_in_order_without_code_blocks() -> None:
    """Заголовки всех уровней по порядку; `#` внутри кода заголовком не считается."""
    text = (
        "# Первый\n"
        "\n"
        "текст\n"
        "\n"
        "## Как запустить\n"
        "\n"
        "```bash\n"
        "# не заголовок, а комментарий\n"
        "```\n"
        "\n"
        "###### Шестой уровень\n"
        "\n"
        "### Раздел с `кодом` и [ссылкой](a.md)\n"
    )

    assert MarkdownItHeadingSource().headings(text) == (
        "Первый",
        "Как запустить",
        "Шестой уровень",
        "Раздел с кодом и ссылкой",
    )


def test_headings_empty_for_text_without_headings() -> None:
    """Нет заголовков → пустой кортеж, а не `None` (Null Object для чекера якорей)."""
    assert MarkdownItHeadingSource().headings("просто текст\n") == ()


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("## Как **запустить**", "Как запустить"),
        ("## Как _запустить_", "Как запустить"),
        ("## Как `запустить`", "Как запустить"),
        ("## Как [запустить](run.md)", "Как запустить"),
        ("## Как ![схема](run.png) запустить", "Как схема запустить"),
        ("## Как ~~не~~ запустить", "Как не запустить"),
        ("## Как <b>запустить</b>", "Как запустить"),
        (r"## Как \*запустить\*", "Как *запустить*"),
    ],
    ids=["strong", "em", "code", "link", "image", "strike", "html", "escape"],
)
def test_heading_text_drops_inline_markup(heading: str, expected: str) -> None:
    """H-05 (G-H): разметка в заголовке в текст не попадает — значит и в slug.

    GitHub считает `## Как **запустить**` якорем `#как-запустить`: звёздочки в slug не идут.
    Документ разбирается блочно (inline-правила выключены), поэтому разметку из сырого
    `token.content` снимает отдельный inline-проход по тексту заголовка.
    """
    assert MarkdownItHeadingSource().headings(heading + "\n") == (expected,)


def test_heading_with_reference_link_uses_link_text() -> None:
    """`[текст][ref]` в заголовке даёт `текст`: определения ссылок видны inline-проходу (общий `env`)."""
    text = "## Смотри [руководство][ref]\n\n[ref]: docs/guide.md\n"

    assert MarkdownItHeadingSource().headings(text) == ("Смотри руководство",)


def test_headings_inside_list_and_quote_are_found() -> None:
    """Блочная структура нужна целиком: GitHub даёт якорь и заголовку в списке, и в цитате."""
    text = "- ## В списке\n\n> ### В цитате\n\n    # в отступном коде\n"

    assert MarkdownItHeadingSource().headings(text) == ("В списке", "В цитате")


def test_headings_on_reference_tree_file(reference_tree: ReferenceTree) -> None:
    """На реальном файле набора A заголовки совпадают с исходником."""
    text = MarkdownReader().read(reference_tree.root / "docs" / "install.md")

    assert MarkdownItHeadingSource().headings(text) == ("Установка", "Требования")


def test_bare_filenames_are_not_linkified() -> None:
    """Боевой прогон dsp-gpu: `Full.md`/`conftest.py` не должны становиться URL (fuzzy linkify выключен)."""
    text = "см. Full.md и conftest.py, а также https://example.com/x и http://prng.cl"
    targets = [link.target for link in MarkdownItLinkExtractor().extract(text)]
    assert targets == ["https://example.com/x", "http://prng.cl"]


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("data:image/png;base64,iVBORw0KGgo=", LinkKind.UNKNOWN, id="data-uri"),
        pytest.param("javascript:void(0)", LinkKind.UNKNOWN, id="javascript"),
        pytest.param("ftp://host/file.txt", LinkKind.UNKNOWN, id="ftp"),
        pytest.param("std::string", LinkKind.UNKNOWN, id="cpp-scope-not-a-path"),  # H-02 Д-7, H-10
        pytest.param("af::array", LinkKind.UNKNOWN, id="cpp-scope-2"),
        pytest.param("C:/tmp/a.md", LinkKind.LOCAL, id="windows-drive-not-a-scheme"),
        pytest.param("docs/a.md", LinkKind.LOCAL, id="plain-path"),
        pytest.param("file:///tmp/a.md", LinkKind.LOCAL, id="file-uri-stays-local"),
    ],
)
def test_other_schemes_are_unknown_not_local(classifier: LinkClassifier, target: str, expected: LinkKind) -> None:
    """H-01/H-02: `data:`-картинка не должна становиться «битым локальным файлом»."""
    assert classifier.classify(MdLink(target, LinkOrigin.INLINE, 1)) is expected
