"""Проверка внешней ссылки: HEAD с откатом на GET, семафор, кэш URL, таймаут."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock, Semaphore

from ..enums.check_status import CheckStatus
from ..models.md_link import MdLink
from ..runtime.notifier import Notifier

_log = logging.getLogger("core.mdscan.checking")

#: Коды, которыми сервер отвечает «этот метод нельзя» — повторяем через GET.
_METHOD_NOT_ALLOWED = frozenset({405, 501})
_HEAD_THEN_GET = "head_then_get"
#: Исход одной проверки: статус, HTTP-код (0 — ответа не было), пояснение.
_Outcome = tuple[CheckStatus, int, str]


class HttpChecker:
    """Один экземпляр на прогон: общий семафор и общий кэш (инвариант 22).

    Отдельного пула потоков у HTTP нет — проверка идёт внутри parse-потока
    (C2, вариант A), параллелизм ограничен семафором `http.workers`. Иначе
    одновременных запросов было бы `workers.parse × http.workers`.

    Ретраев нет намеренно (D11): повтор мёртвого адреса удваивает время прогона,
    а `TIMEOUT` отделён от `BROKEN` как раз затем, чтобы поднимать таймаут
    осознанно, а не гадать «ссылка битая или медленная».
    """

    def __init__(
        self,
        timeout_ms: int,
        workers: int,
        user_agent: str,
        method: str,
        cache_enabled: bool,
        notifier: Notifier,
    ) -> None:
        self._timeout_sec = max(int(timeout_ms), 1) / 1000.0
        self._slots = Semaphore(max(int(workers), 1))
        self._user_agent = user_agent
        self._head_first = method == _HEAD_THEN_GET
        self._cache_enabled = cache_enabled
        self._cache: dict[str, _Outcome] = {}
        self._lock = Lock()
        self._notifier = notifier

    def check(self, link: MdLink, md_file: Path) -> None:
        """Заполнить статус и `http_code` ссылки по ответу сервера."""
        url = link.target
        outcome = self._cached(url)
        from_cache = outcome is not None
        if outcome is None:
            outcome = self._probe(url)
            self._remember(url, outcome)
        status, code, detail = outcome
        link.status = status
        link.http_code = code
        link.detail = detail
        self._notifier.show(f"[http] {code} {url}")
        self._log_outcome(url, md_file, outcome, from_cache=from_cache)

    @staticmethod
    def _log_outcome(url: str, md_file: Path, outcome: _Outcome, *, from_cache: bool) -> None:
        """Исход ссылки — только `DEBUG`; попадание в кэш отличимо от сетевого вызова.

        `WARNING` на битую ссылку пишет `MarkdownWorker._log_link` — один раз и с
        полями `repo`/`file`; дублировать его здесь значило бы две строки на ссылку (H-06).
        Отдельная строка `http cache` нужна, чтобы по логу было видно, что второй
        такой же адрес сети не касался (инвариант 22).
        """
        if not _log.isEnabledFor(logging.DEBUG):
            return
        status, code, detail = outcome
        prefix = "http cache" if from_cache else "http"
        if status is CheckStatus.OK:
            _log.debug("%s %s %s (из %s)", prefix, code, url, md_file.name)
        else:
            _log.debug("%s %s %s: %s (из %s)", prefix, status.value, url, detail or code, md_file)

    def _cached(self, url: str) -> _Outcome | None:
        """Готовый исход для адреса, если кэш включён и адрес уже проверялся."""
        if not self._cache_enabled:
            return None
        with self._lock:
            return self._cache.get(url)

    def _remember(self, url: str, outcome: _Outcome) -> None:
        """Запомнить исход: один адрес — один сетевой вызов за прогон."""
        if not self._cache_enabled:
            return
        with self._lock:
            self._cache.setdefault(url, outcome)

    def _probe(self, url: str) -> _Outcome:
        """HEAD (дёшево), при 405/501 — повтор того же адреса через GET."""
        method = "HEAD" if self._head_first else "GET"
        status, code, detail = self._request(url, method)
        if method == "HEAD" and code in _METHOD_NOT_ALLOWED:
            _log.debug("HEAD не поддержан (%s), повтор через GET: %s", code, url)
            return self._request(url, "GET")
        return status, code, detail

    def _request(self, url: str, method: str) -> _Outcome:
        """Один сетевой вызов под семафором; любая ошибка → исход, не исключение."""
        request = urllib.request.Request(url, method=method)
        request.add_header("User-Agent", self._user_agent)
        try:
            with self._slots, urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                return CheckStatus.OK, int(response.status), ""
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            exc.close()
            return CheckStatus.BROKEN, code, f"HTTP {code}"
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                return self._timed_out(url)
            return CheckStatus.BROKEN, 0, f"адрес недоступен: {exc.reason}"
        except TimeoutError:
            return self._timed_out(url)
        except OSError as exc:
            return CheckStatus.BROKEN, 0, f"ошибка сети: {type(exc).__name__}: {exc}"
        except Exception as exc:
            _log.exception("непредвиденная ошибка при запросе %s", url)
            return CheckStatus.BROKEN, 0, f"{type(exc).__name__}: {exc}"

    def _timed_out(self, url: str) -> _Outcome:
        """`TIMEOUT` отделён от `BROKEN`: по нему видно, не мал ли `http.timeout_ms`."""
        _log.debug("нет ответа за %.0f мс: %s", self._timeout_sec * 1000, url)
        return CheckStatus.TIMEOUT, 0, f"нет ответа за {self._timeout_sec * 1000:.0f} мс"
