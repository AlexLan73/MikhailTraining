"""Контракт проверки одной ссылки — Strategy, по реализации на каждый `LinkKind`.

Владелец контракта — T-07 (потребитель — конвейер T-10): worker получает чекер
у `CheckerFactory` и зовёт `check(link, md_file)`, не зная, какая это реализация.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models.md_link import MdLink


class LinkChecker(Protocol):
    """Проверяет ссылку и записывает исход **в неё же**.

    Почему `md_file`, а не базовый каталог (✅ Alex): якорному чекеру нужен сам
    файл-владелец, локальному достаточно `md_file.parent`. Один аргумент вместо
    двух — и обе реализации взаимозаменяемы (LSP).

    Реализация ничего не возвращает и **не бросает**: любая ошибка превращается
    в `status` + `detail` конкретной ссылки (D2.1), прогон не останавливается.
    """

    def check(self, link: MdLink, md_file: Path) -> None:
        """Заполнить `link.status`, `link.detail`, `link.http_code`."""
        ...
