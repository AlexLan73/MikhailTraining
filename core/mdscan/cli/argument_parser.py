"""Разбор `argv` по закону CLI (D12.1): первый аргумент — всегда цель.

```text
1. Аргументов НЕТ        → печать конфигурации, код 0
2. Аргументов >= 1       → ПЕРВЫЙ аргумент ВСЕГДА цель (4 ветки)
3. Не подходит ни ветке  → ошибка, код 2
4. Остальные             → только -поле:значение, порядок любой
```

Флагов (`--workers` и т.п.) не существует: любое поле конфигурации задаётся единым
синтаксисом `-поле:значение` (D12.2), поэтому `argparse` здесь не нужен — он навязал бы
собственную грамматику флагов и собственные коды выхода.

Разборщик **ничего не проверяет**: пункты 3 и 4 закона обеспечивают правила V1…V10.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .cli_arguments import HELP_TOKENS, CliArguments

_LOG = logging.getLogger("core.mdscan.cli")


class ArgumentParser:
    """Превращает список аргументов в `CliArguments` (без проверок)."""

    def parse(self, argv: Sequence[str]) -> CliArguments:
        """Разложить `argv` (уже без имени программы) на цель и остальные аргументы."""
        args = list(argv)
        if not args:
            _LOG.debug("аргументов нет — запрошена печать конфигурации")
            return CliArguments(target=None, overrides=(), help_requested=True)
        first = args[0]
        if first in HELP_TOKENS:
            _LOG.debug("первый аргумент %r — запрос справки", first)
            return CliArguments(target=None, overrides=tuple(args[1:]), help_requested=True)
        _LOG.debug("цель: %r, прочих аргументов: %d", first, len(args) - 1)
        return CliArguments(target=first, overrides=tuple(args[1:]), help_requested=False)
