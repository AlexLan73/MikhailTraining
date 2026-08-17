"""Классификация ссылки цепочкой правил: первое сработавшее решает (D8.3)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from core.mdscan.enums.link_kind import LinkKind
from core.mdscan.models.md_link import MdLink
from core.mdscan.parsing.rules.link_rule import LinkRule
from core.mdscan.parsing.rules.rule_anchor import AnchorRule
from core.mdscan.parsing.rules.rule_file_url import FileUrlRule
from core.mdscan.parsing.rules.rule_footnote import FootnoteRule
from core.mdscan.parsing.rules.rule_github import GithubRule
from core.mdscan.parsing.rules.rule_http import HttpRule
from core.mdscan.parsing.rules.rule_local_path import LocalPathRule
from core.mdscan.parsing.rules.rule_mailto import MailtoRule
from core.mdscan.parsing.rules.rule_tel import TelRule
from core.mdscan.parsing.rules.rule_wikilink import WikilinkRule

logger = logging.getLogger("core.mdscan.parsing")


class LinkClassifier:
    """Chain of Responsibility: порядок правил задаётся списком и потому виден глазами.

    Ветки `if/elif` по виду ссылки запрещены (правило 09 п.7): новая категория —
    новый класс правила и одна строка в списке, старые файлы не трогаются.
    Не подошло ни одно правило → `UNKNOWN` (Null Object, «молчаливого else» нет).
    """

    def __init__(self, rules: Sequence[LinkRule]) -> None:
        self._rules: tuple[LinkRule, ...] = tuple(rules)

    @classmethod
    def default(cls) -> LinkClassifier:
        """Канонический порядок 9 правил (D8.3) — единственный источник истины.

        `WikilinkRule`/`FootnoteRule` — по синтаксису, раньше всех; `GithubRule`
        **строго до** `HttpRule`; `LocalPathRule` — последним, он тотальный.
        Composition Root (T-10/T-13) берёт цепочку отсюда и не собирает свою.
        """
        return cls(
            [
                WikilinkRule(),
                FootnoteRule(),
                AnchorRule(),
                MailtoRule(),
                TelRule(),
                GithubRule(),
                HttpRule(),
                FileUrlRule(),
                LocalPathRule(),
            ]
        )

    def classify(self, link: MdLink) -> LinkKind:
        """Категория ссылки; сам `link` не изменяется — его пишет вызывающий."""
        for rule in self._rules:
            if rule.matches(link):
                logger.debug(
                    "правило %s → %s для %s", type(rule).__name__, rule.kind.value, link.target
                )
                return rule.kind
        logger.warning("ссылка не подошла ни одному правилу: %s", link.target)
        return LinkKind.UNKNOWN
