"""Одна ссылка из Markdown-файла — единственный носитель её состояния."""

from __future__ import annotations

from dataclasses import dataclass

from core.mdscan.enums.check_status import CheckStatus
from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.enums.link_origin import LinkOrigin


@dataclass(slots=True)
class MdLink:
    """Ссылка: извлекается парсером, дозаполняется классификатором и чекером.

    Изменяемый намеренно (в отличие от `RepoInfo`/`MdTask`): чекер пишет
    `status`/`detail`/`http_code` прямо сюда, копий объекта в конвейере нет (D15.1).
    Владелец — поток-обработчик своего файла; после публикации результата
    объект больше не меняется (D15.2).
    """

    target: str
    origin: LinkOrigin
    line: int
    kind: LinkKind = LinkKind.UNKNOWN
    status: CheckStatus = CheckStatus.SKIPPED
    detail: str = ""
    http_code: int = 0
