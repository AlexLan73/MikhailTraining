"""Точка входа `python -m core.mdscan` — фаза 0 прогона (часть 2, §1 и D6).

Единственный слой, которому разрешено печатать (правило 09 п. 8): всё остальное
возвращает значения. Здесь же живёт закон CLI — первый аргумент всегда цель,
`-h`/`--help`/`-?`/пусто = печать конфигурации.

Коды возврата (часть 2 §1.4): `0` успех · `1` найдены битые ссылки ·
`2` ошибка аргументов или конфигурации · `3` внутренняя ошибка ·
`130` прервано пользователем (`Ctrl+C`, соглашение POSIX 128+SIGINT; H-08).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from .cli.argument_parser import ArgumentParser
from .cli.validation.chain import ValidationChain
from .cli.validation.validation_context import ValidationContext
from .config.config_printer import ConfigPrinter
from .config.scan_config import ScanConfig
from .config.yaml_config_loader import YamlConfigLoader
from .runtime.scan_orchestrator import INTERNAL_ERROR_CODE, INTERRUPTED_CODE, ScanOrchestrator

logger = logging.getLogger("core.mdscan")

#: Имя файла конфигурации; ищется в текущем каталоге и создаётся при холодном старте (D19).
CONFIG_FILE: Final = "mdscan.yaml"


def main(argv: Sequence[str]) -> int:
    """Разобрать аргументы, собрать конфигурацию и выполнить прогон.

    Порядок фазы 0: разбор → `mdscan.yaml` → цепочка V1…V10 (V3 накладывает
    переопределения, V5 определяет вид целей) → `ScanConfig` → прогон.
    Проверки выполняются **до** печати справки: ошибка в `-поле:значение` должна
    быть видна и при `-h`, а не молча проглочена (см. `ValidationChain`).
    """
    try:
        args = ArgumentParser().parse(argv)
        draft = YamlConfigLoader().load(Path.cwd() / CONFIG_FILE)
        outcome = ValidationChain.default().run(ValidationContext(args=args, draft=draft))
        if not outcome.ok:
            sys.stderr.write(f"{outcome.message}\n")
            return outcome.exit_code
        config = ScanConfig.from_draft(draft)
        if args.help_requested:
            sys.stdout.write(f"{ConfigPrinter().render(config, draft.sources)}\n")
            return 0
        return ScanOrchestrator().scan(config).exit_code
    except KeyboardInterrupt:  # Ctrl+C в фазе 0: человеку строка, системе код 130
        logger.warning("прогон прерван пользователем (Ctrl+C)")
        sys.stderr.write("прервано пользователем (Ctrl+C)\n")
        return INTERRUPTED_CODE
    except Exception as exc:  # noqa: BLE001 — последний рубеж: человеку строка, системе код 3
        logger.critical("внутренняя ошибка: %s: %s", type(exc).__name__, exc, exc_info=True)
        sys.stderr.write(f"внутренняя ошибка: {type(exc).__name__}: {exc}\n")
        return INTERNAL_ERROR_CODE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
