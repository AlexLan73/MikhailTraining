"""Состояние, над которым работает цепочка правил: аргументы + черновик конфигурации.

Правила не только читают, но и **дописывают** контекст: V3 накладывает переопределения
`-поле:значение`, V4 кладёт нормализованный путь цели, V5 пишет `source.targets_resolved`.
Поэтому контекст изменяем, а неизменяемый `ScanConfig` собирается уже после цепочки
(`ScanConfig.from_draft`) — до этого момента конфигурация ещё «сырая» (D15.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ...config.config_draft import ConfigDraft
from ...enums.source_kind import SourceKind
from ..cli_arguments import YAML_TARGET, CliArguments

#: Путь служебного поля с целями, которые классифицировало правило V5.
TARGETS_RESOLVED: Final = "source.targets_resolved"

#: Признаки адреса-URL (а не пути на диске) — один источник истины для V4 и V5.
URL_MARKERS: Final = ("://", "git@")


@dataclass(slots=True)
class ValidationContext:
    """Аргументы командной строки и черновик конфигурации на время проверок."""

    args: CliArguments
    draft: ConfigDraft
    target_path: Path | None = None  # нормализованный путь цели; заполняет V4

    @property
    def yaml_branch(self) -> bool:
        """Цель — слово `yaml`: адреса берутся из конфигурации, а не из аргумента.

        Явный `-source.kind:…` снимает ветку: так разрешается спорный случай
        «каталог с именем yaml» (часть 2 §1.1.1) — человек сказал, как трактовать адрес.
        """
        if self.args.target != YAML_TARGET:
            return False
        return str(self.draft.value_at("source.kind")).strip().lower() in ("", "auto")

    @property
    def resolved_targets(self) -> tuple[tuple[str, SourceKind], ...]:
        """Классифицированные цели (пусто, пока не отработало правило V5)."""
        try:
            resolved = self.draft.value_at(TARGETS_RESOLVED)
        except KeyError:
            return ()
        return tuple((str(address), kind) for address, kind in resolved)

    @property
    def local_targets(self) -> tuple[Path, ...]:
        """Только локальные цели — их проверяют правила V6, V7 и V8."""
        return tuple(
            Path(address) for address, kind in self.resolved_targets if kind is SourceKind.LOCAL
        )
