"""Результат разбора командной строки — без единой проверки (закон CLI, D12.1).

Разбор и валидация разделены намеренно: `ArgumentParser` только раскладывает `argv`
на «цель» и «остальное», а решает, законно ли это, цепочка правил V1…V10. Поэтому
здесь нет ни одной ветки «а если поле неизвестно» — объект описывает то, что человек
набрал, а не то, что программа сочла допустимым.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Слово-цель «взять цели из mdscan.yaml» (четвёртая ветка цели, часть 2 §1.1.1).
YAML_TARGET: Final = "yaml"

#: Аргументы-исключения: первым аргументом равны запуску без аргументов (решение Alex).
HELP_TOKENS: Final = frozenset({"-h", "--help", "-?"})


@dataclass(frozen=True, slots=True)
class CliArguments:
    """Разобранная командная строка: цель, сырые переопределения, запрос справки."""

    target: str | None
    overrides: tuple[str, ...]
    help_requested: bool
