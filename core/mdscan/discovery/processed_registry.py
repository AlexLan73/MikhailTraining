"""Реестр уже поставленных в очередь файлов — страховка от дублей (часть 1, D6.4)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from core.mdscan.discovery.resolved_path_cache import ResolvedPathCache

logger = logging.getLogger("core.mdscan.discovery")


class ProcessedRegistry:
    """Потокобезопасный набор пар «репозиторий → файл».

    Правило ближайшего корня (D6.2) не даёт дублю **появиться**, реестр не даёт
    ему **пройти дальше** там, где правила мало: симлинк на уже просмотренную
    папку, два worktree одного репозитория, один репозиторий в списке дважды.

    Ключ — пара `(repo_root, md_file)` после резолва: разные записи об одном
    файле схлопываются, а один и тот же файл в двух разных репозиториях (жёсткая
    ссылка) остаётся различим.

    **Инвариант вызывающего** (H-05, гипотеза G-D): пути приходят **абсолютные** —
    `MarkdownFileFinder` их уже резолвит, `RepoInfo.root` абсолютен по построению.
    Поэтому реестр не резолвит путь файла повторно: он приводит к каноническому виду
    только **каталог** пути, через общий `ResolvedPathCache` (одно обращение к ОС на
    каталог, а не на файл). Схлопывание псевдонимов при этом сохраняется: они всегда
    каталожные (симлинк на папку, второй worktree, репозиторий в списке дважды).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: set[tuple[Path, Path]] = set()
        self._paths = ResolvedPathCache()

    def add_if_absent(self, key: tuple[Path, Path]) -> bool:
        """`True` — ключ новый (задачу ставим), `False` — дубль (не ставим).

        Резолв каталогов делается **до** захвата блокировки: обращение к файловой
        системе под `Lock` тормозило бы все потоки обхода.
        """
        repo_root, md_file = key
        resolved = (self._paths.directory(Path(repo_root)), self._paths.file(Path(md_file)))
        with self._lock:
            if resolved in self._keys:
                logger.debug("дубль отсечён: repo=%s file=%s", resolved[0], resolved[1])
                return False
            self._keys.add(resolved)
        return True
