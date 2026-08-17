"""Результат разбора одного файла — то, из чего строятся отчёт и статистика."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.models.md_link import MdLink
from core.mdscan.models.repo_info import RepoInfo

#: Статусы, которые считаются «ссылка не работает» (таймаут — тоже проблема, но иной причины).
_BROKEN_STATUSES = frozenset({CheckStatus.BROKEN, CheckStatus.TIMEOUT})


@dataclass(slots=True)
class MdFileResult:
    """Носитель данных от разбора до отчёта.

    Изменяемый: воркер наполняет его по шагам (чтение → извлечение → проверка).
    После `put()` в очередь объект не изменяется — копий и `freeze()` не нужно (D15.2).
    Ошибка любого шага не теряется: она попадает в `error`, результат публикуется всё равно.
    """

    repo: RepoInfo
    md_file: Path
    rel_path: str
    links: list[MdLink] = field(default_factory=list)
    error: str = ""
    seconds: float = 0.0
    thread_name: str = ""

    @property
    def ok(self) -> bool:
        """Файл обработан без исключения (битые ссылки внутри — не ошибка файла)."""
        return self.error == ""

    @property
    def broken_count(self) -> int:
        """Сколько ссылок не работают: `BROKEN` + `TIMEOUT`."""
        return sum(1 for link in self.links if link.status in _BROKEN_STATUSES)
