"""V8 — цель внутри git; если нет — предупреждение, а не ошибка (D5).

Единственное правило цепочки, которое не может завершить прогон: сканировать обычную
папку с `.md` полезно и вне репозитория, просто список файлов берётся обходом, а не
`git ls-files`. Молчать при этом нельзя — иначе `respect_gitignore: true` тихо
не сработает, и человек будет гадать, почему в отчёте файлы из `node_modules`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .validation_context import ValidationContext
from .validation_result import ValidationResult

_LOG = logging.getLogger("core.mdscan.cli")

_GIT_ENTRY = ".git"


class GitRepositoryRule:
    """Предупреждает, если локальная цель не лежит внутри git-репозитория."""

    def validate(self, ctx: ValidationContext) -> ValidationResult:
        """Всегда `ok`: результат проверки уходит в лог уровнем `WARNING`."""
        for path in ctx.local_targets:
            if self._inside_git(path):
                _LOG.debug("цель внутри git-репозитория: %s", path)
                continue
            _LOG.warning(
                "цель «%s» вне git-репозитория — работаем как с обычной папкой", path
            )
        return ValidationResult(ok=True)

    def _inside_git(self, path: Path) -> bool:
        return any((candidate / _GIT_ENTRY).exists() for candidate in (path, *path.parents))
