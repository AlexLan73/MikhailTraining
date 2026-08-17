"""Генератор тестовых деревьев Markdown для hw01 (наборы A и B).

Оба набора строит **код**, а не git: деревья лежат в `out/hw01/` (каталог в `.gitignore`),
поэтому на другой машине их надо уметь воссоздать побайтово (часть 1, D1).

- **Набор A** — `reference()`: фиксированное эталонное дерево, ≈28 файлов, 82 ссылки,
  ровно 7 битых, со всеми «злыми» случаями (fenced code, reference-ссылки, пробелы и
  кириллица в путях, `../../README.md`, UTF-8-SIG, битый байт, пустой файл, `.markdown`,
  `file:///`, `mailto:`, `tel:`, wikilink, сноска). Ожидания — в `expectations.py`.
- **Набор B** — `generated()`: дерево заданного размера, детерминированное по сиду,
  для нагрузки и замера `speedup`.

Каталог с деревом переиспользуется, если он собран этой же версией генератора
(файл-метка со стемпом содержимого); иначе пересобирается с нуля.
"""

from __future__ import annotations

import hashlib
import logging
import random
import shutil
from pathlib import Path

from .expectations import REFERENCE_EXPECTATIONS, ReferenceTree

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Набор A: содержимое файлов (данные, не логика)
# ─────────────────────────────────────────────────────────────────────────────

_MD_TEXTS: tuple[tuple[str, str], ...] = (
    (
        "README.md",
        """# Тестовое дерево hw01

Эталонный набор A: дерево `.md` для проверки обхода, разбора и проверки ссылок.

## Разделы

- [Документация](docs/index.md)
- [Установка](docs/install.md#установка)
- [Проект на GitHub](https://github.com/dsp-gpu/mdscan)
- [К разделам](#разделы)
""",
    ),
    (
        "CHANGELOG.md",
        """# История изменений

## 1.0.0

- первая версия — [документация](docs/index.md)
- обсуждение — [issue 1](https://github.com/dsp-gpu/mdscan/issues/1)
- внешняя [спецификация](https://example.org/spec)
""",
    ),
    (
        "docs/index.md",
        """# Документация

- [Справка](справка.md)
- [Установка](install.md#установка)
- [Битая ссылка](missing/nope.md)
- [Обзор](guide/overview.md)
""",
    ),
    (
        "docs/install.md",
        """# Установка

## Требования

- [Битый якорь](#нет-такого)
- [Наверх](#установка)
- [Справочник API](api/reference.md)
""",
    ),
    (
        "docs/справка.md",
        """# Справка

- [Документация](index.md)
- [Установка](install.md)
- [Написать в поддержку](mailto:help@example.org)
""",
    ),
    (
        "docs/guide/overview.md",
        """# Обзор

- [Файл с пробелами](<path with spaces.md>)
- [Корневой README](../../README.md)
- [Второе расширение](extra.markdown)
- [Внешняя статья](https://example.org/guide)
""",
    ),
    (
        "docs/guide/path with spaces.md",
        """# Файл с пробелами в имени

- [Обзор](overview.md)
- [Глубже](deep/level4.md)
- [Сайт](https://example.com/)
""",
    ),
    (
        "docs/guide/extra.markdown",
        """# Файл с расширением .markdown

- [Обзор](overview.md)
- [Список задач](../../notes/todo.md)
- [Инструменты](https://github.com/dsp-gpu/tools)
""",
    ),
    (
        "docs/guide/deep/level4.md",
        """# Уровень 4

## Глубина

- [Битый якорь](#нет-раздела)
- [К разделу](#глубина)
- [Уровень 5](more/level5.md)
- [Наверх](../overview.md)
""",
    ),
    (
        "docs/guide/deep/fenced.md",
        """# Ссылки внутри кода

```markdown
[Эта ссылка внутри fenced code не извлекается](../../../nowhere.md)
```

Инлайн-код тоже не ссылка: `[и эта](nope.md)`.

- [Уровень 4](level4.md)
- [Документация](../../index.md)
""",
    ),
    (
        "docs/guide/deep/more/level5.md",
        """# Уровень 5

- [Наверх](../level4.md)
- [Reference-ссылки](refs.md)
- [Корневой README](../../../../README.md)
""",
    ),
    (
        "docs/guide/deep/more/refs.md",
        """# Reference-ссылки

Смотри [обзор][ov] и [четвёртый уровень][deep].

[ov]: ../../overview.md
[deep]: ../level4.md
""",
    ),
    (
        "docs/api/reference.md",
        """# Справочник API

## Функции

- [Ошибки](errors.md)
- [Битый якорь в другом файле](errors.md#несуществующий-раздел)
- [К функциям](#функции)
- [Документация](../index.md)
""",
    ),
    (
        "docs/api/errors.md",
        """# Ошибки

## Коды возврата

- [К кодам](#коды-возврата)
- [Справочник](reference.md)
- [issue 2](https://github.com/dsp-gpu/mdscan/issues/2)
""",
    ),
    (
        "notes/todo.md",
        """# Список задач

- [Битая ссылка](../docs/guide/absent.md)
- [Разные ссылки](links.md)
- [Дневник](личное/дневник.md)
- [Трекер](https://example.org/tracker)
""",
    ),
    (
        "notes/links.md",
        """# Разные ссылки

Автолинк: <https://example.org/auto>

- [Организация](https://github.com/dsp-gpu)
- [Список задач](todo.md)
- [Документация](../docs/index.md)
""",
    ),
    (
        "notes/личное/дневник.md",
        """# Дневник

- [Планы](планы.md)
- [Список задач](../todo.md)
- [Заметка](https://example.org/diary)
""",
    ),
    (
        "notes/личное/планы.md",
        """# Планы

- [Битая ссылка](отсутствует.md)
- [Дневник](дневник.md)
- [Корневой README](../../README.md)
""",
    ),
    (
        "src/README.md",
        """# Исходники

- [Модуль](module.md)
- [Документация](../docs/index.md)
- [Каталог src на GitHub](https://github.com/dsp-gpu/mdscan/tree/main/src)
""",
    ),
    (
        "src/module.md",
        """# Модуль

- [Битая ссылка](../lib/missing.md)
- [README](README.md)
- [Справочник API](../docs/api/reference.md)
""",
    ),
    (
        "assets/media.md",
        """# Медиа

![Логотип](img/logo.png)

- [Локальный отчёт](file:///tmp/report.html)
- [Правовая информация](legal.md)
""",
    ),
    (
        "assets/legal.md",
        """# Правовая информация

- [Лицензия](https://example.org/mit)
- [Медиа](media.md)
- [Юристы](mailto:legal@example.org)
""",
    ),
    (
        "misc/contacts.md",
        """# Контакты

- [Написать](mailto:support@example.org)
- [Позвонить](tel:+78120000000)
- [Сайт](https://example.org/contacts)
""",
    ),
    (
        "misc/wiki.md",
        """# Вики-ссылки

Смотри [[project-notes]].

- [Контакты](contacts.md)
- [Сноски](footnotes.md)
""",
    ),
    (
        "misc/footnotes.md",
        """# Сноски

Текст со сноской[^1].

- [Вики-ссылки](wiki.md)

[^1]: Подробности — <https://example.org/footnote-spec>
""",
    ),
)

#: Файл в кодировке UTF-8 с BOM («злой» случай чтения).
_UTF8_SIG_TEXT: tuple[tuple[str, str], ...] = (
    (
        "encoding/utf8_sig.md",
        """# Файл в кодировке UTF-8-SIG

- [Корневой README](../README.md)
- [Пустой файл](empty.md)
- [Про кодировки](https://example.org/encoding)
""",
    ),
)

#: Файлы, которые задаются байтами: пустой, с битым байтом, картинка-заглушка.
_BINARY_FILES: tuple[tuple[str, bytes], ...] = (
    ("encoding/empty.md", b""),
    (
        "encoding/broken_byte.md",
        "# Битый байт\n\nСледующий байт не UTF-8: ".encode() + b"\xff\xfe" + b"\n",
    ),
    ("assets/img/logo.png", b"\x89PNG\r\n\x1a\nfixture-stub"),
)


def _reference_payload() -> tuple[tuple[str, bytes], ...]:
    """Собирает набор A в пары «относительный путь → байты файла».

    Переводы строк принудительно `\\n`, кодировки заданы явно — дерево получается
    побайтово одинаковым на Windows и Linux.
    """
    items: list[tuple[str, bytes]] = []
    items.extend((rel, text.replace("\r\n", "\n").encode("utf-8")) for rel, text in _MD_TEXTS)
    items.extend((rel, text.replace("\r\n", "\n").encode("utf-8-sig")) for rel, text in _UTF8_SIG_TEXT)
    items.extend(_BINARY_FILES)
    return tuple(items)


#: Готовое содержимое набора A: (rel_path в POSIX-виде, байты).
REFERENCE_FILES: tuple[tuple[str, bytes], ...] = _reference_payload()


class FixtureTreeBuilder:
    """Строит тестовые деревья Markdown: набор A (эталон) и набор B (по сиду)."""

    _STAMP_NAME = ".fixture_stamp"

    def reference(self, root: Path) -> ReferenceTree:
        """Набор A: эталонное дерево в `root`.

        Существующее дерево той же версии переиспользуется, иначе пересобирается.
        """
        stamp = self._reference_stamp()
        if self._is_fresh(root, stamp):
            logger.info("набор A переиспользован: %s", root)
            return ReferenceTree(root=root, expectations=REFERENCE_EXPECTATIONS)

        self._reset(root)
        for rel, payload in REFERENCE_FILES:
            self._write(root / rel, payload)
        self._write(root / self._STAMP_NAME, stamp.encode("utf-8"))
        logger.info("набор A построен: %s, файлов %d", root, len(REFERENCE_FILES))
        return ReferenceTree(root=root, expectations=REFERENCE_EXPECTATIONS)

    def generated(self, root: Path, files: int, seed: int) -> Path:
        """Набор B: `files` файлов `.md`, детерминированно по `seed`.

        Один и тот же `seed` даёт побайтово одно и то же дерево, разные — разные.
        """
        if files <= 0:
            raise ValueError(f"files должно быть > 0, получено {files}")

        stamp = f"generated v1 files={files} seed={seed}"
        if self._is_fresh(root, stamp):
            logger.info("набор B переиспользован: %s (files=%d, seed=%d)", root, files, seed)
            return root

        self._reset(root)
        rng = random.Random(seed)
        names = [self._generated_name(rng, index) for index in range(files)]
        for index, rel in enumerate(names):
            self._write(root / rel, self._generated_text(rng, index, names).encode("utf-8"))
        self._write(root / self._STAMP_NAME, stamp.encode("utf-8"))
        logger.info("набор B построен: %s, файлов %d, сид %d", root, files, seed)
        return root

    # ── приватные хелперы ────────────────────────────────────────────────────

    @staticmethod
    def _reference_stamp() -> str:
        """Отпечаток содержимого набора A — метка версии дерева."""
        digest = hashlib.sha256()
        for rel, payload in REFERENCE_FILES:
            digest.update(rel.encode("utf-8"))
            digest.update(payload)
        return f"reference v1 {digest.hexdigest()}"

    def _is_fresh(self, root: Path, stamp: str) -> bool:
        """`True`, если каталог уже собран этой же версией генератора."""
        marker = root / self._STAMP_NAME
        if not marker.is_file():
            return False
        try:
            return marker.read_text(encoding="utf-8") == stamp
        except OSError:
            logger.exception("метка %s не читается — дерево будет пересобрано", marker)
            return False

    @staticmethod
    def _reset(root: Path) -> None:
        """Удаляет старое дерево и создаёт пустой корень."""
        if root.exists():
            logger.debug("удаляю старое дерево %s", root)
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write(path: Path, payload: bytes) -> None:
        """Пишет файл, создавая родительские каталоги; ошибка — в лог и наружу."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        except OSError:
            logger.exception("не удалось записать %s", path)
            raise
        logger.debug("записан %s (%d байт)", path, len(payload))

    @staticmethod
    def _generated_name(rng: random.Random, index: int) -> str:
        """Относительный путь очередного файла набора B (глубина 0…4)."""
        parts = [f"d{rng.randrange(3)}" for _ in range(rng.randrange(5))]
        parts.append(f"note_{index:04d}.md")
        return "/".join(parts)

    @staticmethod
    def _generated_text(rng: random.Random, index: int, names: list[str]) -> str:
        """Текст очередного файла набора B: заголовок и 0…4 ссылки."""
        lines = [f"# Заметка {index:04d}", "", "## Раздел", ""]
        for number in range(rng.randrange(5)):
            roll = rng.randrange(3)
            if roll == 0:
                target = rng.choice(names)
            elif roll == 1:
                target = f"https://example.org/gen/{rng.randrange(1000)}"
            else:
                target = "#раздел"
            lines.append(f"- [ссылка {number}]({target})")
        lines.append("")
        return "\n".join(lines)
