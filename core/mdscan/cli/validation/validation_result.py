"""Итог одной проверки: прошла или нет, с каким кодом возврата и текстом.

Коды возврата — часть 2 §1.4: `0` — успех, `2` — ошибка аргументов или конфигурации.
Правило никогда не печатает и не завершает процесс: оно возвращает решение, а печатает
и выходит слой вывода (`__main__`, T-13) — правило 09 п. 8.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Решение правила: `ok=False` останавливает цепочку и задаёт код выхода."""

    ok: bool
    exit_code: int = 0
    message: str = ""
