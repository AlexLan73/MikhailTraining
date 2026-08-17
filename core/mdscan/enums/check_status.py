"""Итог проверки одной ссылки — одно и то же значение в логе, отчёте и метриках."""

from __future__ import annotations

from enum import Enum


class CheckStatus(Enum):
    """Три различимых исхода проверки плюс «не проверяли»."""

    OK = "ok"            # цель существует / ответ 2xx-3xx
    BROKEN = "broken"    # цели нет / 4xx-5xx / DNS
    TIMEOUT = "timeout"  # ответа не дождались (отдельно от BROKEN — разная причина)
    SKIPPED = "skipped"  # проверка отключена конфигом или категория не проверяется
