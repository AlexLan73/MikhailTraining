"""Организация GitHub как источник: список репозиториев → `RemoteRepoSource` на каждый.

Внешние вызовы (`gh`, REST API) инжектируются в конструктор (спека разработки §3.3),
поэтому тесты подменяют их обычными функциями, без глобального `monkeypatch`.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config.scan_config import SourceConfig
from ..errors import GitHubDiscoveryError, GitUnavailableError
from ..models.repo_info import RepoInfo
from .git_adapter import GitAdapter
from .remote_repo_source import RemoteRepoSource

logger = logging.getLogger("core.mdscan.source")

#: Запуск `gh` с аргументами → stdout.
RunGh = Callable[[Sequence[str]], str]
#: GET по URL с заголовками → (код, тело, заголовки ответа).
HttpGet = Callable[[str, Mapping[str, str]], tuple[int, str, Mapping[str, str]]]

_API_ROOT = "https://api.github.com"
_USER_AGENT = "mdscan"
_GH_FIELDS = "name,url,sshUrl,isFork,isArchived,visibility"
#: Префикс имён потоков клонирования — он же идёт в лог (D2.1).
CLONE_PREFIX = "clone"
_MAX_PAGES = 1000  # страховка от бесконечного листания при некорректном заголовке Link
_ADVICE = "перечисли репозитории в source.repositories и запусти с целью `yaml`"


def _org_name(org_url: str) -> str:
    """Имя организации из её URL: `https://github.com/dsp-gpu` → `dsp-gpu`."""
    return org_url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _from_gh(item: Mapping[str, Any]) -> dict[str, Any]:
    """Запись `gh repo list --json ...` → нормализованный вид."""
    web_url = str(item.get("url", ""))
    return {
        "name": str(item.get("name", "")),
        "web_url": web_url,
        "ssh_url": str(item.get("sshUrl", "")),
        "https_url": f"{web_url}.git" if web_url else "",
        "is_fork": bool(item.get("isFork", False)),
        "is_archived": bool(item.get("isArchived", False)),
        "visibility": str(item.get("visibility", "")).lower(),
    }


def _from_api(item: Mapping[str, Any]) -> dict[str, Any]:
    """Запись REST API `GET /orgs/{org}/repos` → нормализованный вид."""
    private = bool(item.get("private", False))
    return {
        "name": str(item.get("name", "")),
        "web_url": str(item.get("html_url", "")),
        "ssh_url": str(item.get("ssh_url", "")),
        "https_url": str(item.get("clone_url", "")),
        "is_fork": bool(item.get("fork", False)),
        "is_archived": bool(item.get("archived", False)),
        "visibility": str(item.get("visibility", "private" if private else "public")).lower(),
    }


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Заголовки ответа с ключами в нижнем регистре (HTTP регистронезависим)."""
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _reset_hint(headers: Mapping[str, str]) -> str:
    """Время сброса лимита из заголовка X-RateLimit-Reset (epoch → UTC)."""
    raw = headers.get("x-ratelimit-reset", "")
    try:
        moment = datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError):
        return "время сброса не указано"
    return f"сброс в {moment.strftime('%Y-%m-%d %H:%M:%S')} UTC"


def _check_status(status: int, headers: Mapping[str, str], org: str) -> None:
    """Не-200 от API → `GitHubDiscoveryError`; 429/403 по лимиту — со временем сброса."""
    if status == 200:
        return
    exhausted = status == 429 or (status == 403 and headers.get("x-ratelimit-remaining") == "0")
    if exhausted:
        raise GitHubDiscoveryError(
            f"GitHub API rate limit исчерпан ({status}) для организации {org}: "
            f"{_reset_hint(headers)}; авторизуйтесь (GITHUB_TOKEN) или {_ADVICE}"
        )
    raise GitHubDiscoveryError(f"GitHub API ответил {status} для организации {org}; {_ADVICE}")


def _has_next(headers: Mapping[str, str]) -> bool:
    """Есть ли следующая страница: заголовок Link с rel=next."""
    return 'rel="next"' in headers.get("link", "")


def _payload(raw: str, source: str) -> list[Mapping[str, Any]]:
    """Тело ответа → список записей; не список / не JSON → ошибка раскрытия."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise GitHubDiscoveryError(f"{source}: ответ не разобран как JSON: {exc}") from exc
    if not isinstance(data, list):
        raise GitHubDiscoveryError(
            f"{source}: ожидался список репозиториев, получено {type(data).__name__}"
        )
    return data


def _discover_gh(org: str, page_size: int, run_gh: RunGh) -> list[dict[str, Any]]:
    """`gh repo list <org> --json ...`; любая неудача → `GitHubDiscoveryError`."""
    args = ["repo", "list", org, "--json", _GH_FIELDS, "--limit", str(page_size)]
    try:
        raw = run_gh(args)
    except Exception as exc:
        raise GitHubDiscoveryError(f"gh repo list {org} не выполнен: {exc}") from exc
    records = [_from_gh(item) for item in _payload(raw, f"gh repo list {org}")]
    logger.info("gh вернул %d репозиториев организации %s", len(records), org)
    return records


def _discover_api(org: str, page_size: int, http_get: HttpGet) -> list[dict[str, Any]]:
    """REST API `GET /orgs/{org}/repos` с пагинацией до конца (инвариант 21)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"  # значение в лог не пишем
    records: list[dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        url = f"{_API_ROOT}/orgs/{org}/repos?per_page={page_size}&page={page}"
        try:
            status, body, raw_headers = http_get(url, headers)
        except Exception as exc:
            raise GitHubDiscoveryError(f"REST API {org}: запрос не выполнен: {exc}") from exc
        response_headers = _lower_headers(raw_headers)
        _check_status(status, response_headers, org)
        page_items = _payload(body, f"REST API {org}")
        logger.debug("страница %d организации %s: %d записей", page, org, len(page_items))
        records.extend(_from_api(item) for item in page_items)
        if not page_items or not _has_next(response_headers):
            break
    logger.info("REST API вернул %d репозиториев организации %s", len(records), org)
    return records


class GitHubOrgSource:
    """Раскрывает организацию в репозитории и отдаёт их клонами (`RemoteRepoSource`).

    Организация — **один** источник, поэтому пул обхода (`workers.discover`) её не
    параллелит: он раскладывает по потокам источники, а не репозитории внутри одного.
    Клонирование ведётся собственным пулом на `clone_workers` потоков (H-13, дефект D-2
    прогона H-01: 10 репозиториев клонировались последовательно — 72.5 с из 103 с).
    """

    def __init__(
        self,
        org_url: str,
        config: SourceConfig,
        run_gh: RunGh,
        http_get: HttpGet,
        git: GitAdapter,
        clone_workers: int = 1,
    ) -> None:
        self._org = _org_name(org_url)
        self._config = config
        self._run_gh = run_gh
        self._http_get = http_get
        self._git = git
        self._clone_workers = max(1, clone_workers)
        self._children: list[RemoteRepoSource] = []

    def repositories(self) -> Iterable[RepoInfo]:
        """Репозитории организации после фильтров, каждый — склонированный локально.

        Возвращается **ленивая** последовательность: репозиторий отдаётся сразу, как
        только склонирован (`as_completed`), — стадия 2 начинает разбирать первый
        репозиторий, пока остальные ещё клонируются. Порядок поэтому не совпадает
        с порядком выдачи GitHub (при `clone_workers=1` — совпадает).
        """
        records = [record for record in self._discover() if self._accepted(record)]
        logger.info(
            "организация %s: репозиториев к обходу %d, потоков клонирования %d",
            self._org,
            len(records),
            min(self._clone_workers, len(records)) or 1,
        )
        children = [(record, self._child(record)) for record in records]
        self._children.extend(child for _, child in children)
        return self._cloned(children)

    def _child(self, record: Mapping[str, Any]) -> RemoteRepoSource:
        """Дочерний источник-клон одного репозитория организации."""
        return RemoteRepoSource(
            self._clone_url(record),
            Path(self._config.clone_dir),
            self._config.clone_depth,
            self._config.keep_clones,
            self._git,
        )

    def _cloned(
        self, children: Sequence[tuple[Mapping[str, Any], RemoteRepoSource]]
    ) -> Iterator[RepoInfo]:
        """Клонировать в `clone_workers` потоков и отдавать по мере готовности."""
        if not children:
            return
        workers = min(self._clone_workers, len(children))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=CLONE_PREFIX) as pool:
            futures = [pool.submit(self._clone_one, record, child) for record, child in children]
            for future in as_completed(futures):
                yield from future.result()

    def _clone_one(
        self, record: Mapping[str, Any], child: RemoteRepoSource
    ) -> list[RepoInfo]:
        """Один репозиторий: клон + `RepoInfo`; ошибка клона не роняет остальные (правило 11)."""
        try:
            return [
                replace(info, remote_url=record["ssh_url"], web_url=record["web_url"])
                for info in child.repositories()
            ]
        except GitUnavailableError:
            raise  # нет git — продолжать бессмысленно, ошибку видит весь прогон
        except Exception:  # noqa: BLE001 — репозиторий пропускаем, организация обходится дальше
            logger.exception("репозиторий %s организации %s пропущен", record["name"], self._org)
            return []

    def cleanup(self) -> None:
        """Убрать клоны всех дочерних источников; падение одного не мешает остальным."""
        for child in self._children:
            try:
                child.cleanup()
            except Exception as exc:  # noqa: BLE001 — cleanup обязан пройти по всем клонам
                logger.error("cleanup клона не выполнен: %s", exc, exc_info=True)

    def _discover(self) -> list[dict[str, Any]]:
        """Раскрытие организации по `source.discovery` (таблица вместо if/elif)."""
        modes: dict[str, Callable[[], list[dict[str, Any]]]] = {
            "gh": self._by_gh,
            "api": self._by_api,
            "auto": self._by_auto,
        }
        discover = modes.get(self._config.discovery)
        if discover is None:
            raise GitHubDiscoveryError(
                f"неизвестный source.discovery: {self._config.discovery!r} (ожидалось auto|gh|api)"
            )
        return discover()

    def _by_gh(self) -> list[dict[str, Any]]:
        """Строгий режим `gh`: тихого перехода на API нет."""
        return _discover_gh(self._org, self._config.page_size, self._run_gh)

    def _by_api(self) -> list[dict[str, Any]]:
        """Строгий режим `api`: только REST по `GITHUB_TOKEN`."""
        return _discover_api(self._org, self._config.page_size, self._http_get)

    def _by_auto(self) -> list[dict[str, Any]]:
        """auto: сначала `gh`, при неудаче — REST API (жёсткие режимы не подменяются)."""
        try:
            return self._by_gh()
        except GitHubDiscoveryError as exc:
            logger.warning("gh не сработал (%s) → перехожу на REST API", exc)
            return self._by_api()

    def _accepted(self, record: Mapping[str, Any]) -> bool:
        """Фильтры `visibility` / `include_forks` / `include_archived`."""
        visibility = self._config.visibility
        if visibility != "all" and record["visibility"] != visibility:
            return False
        if record["is_fork"] and not self._config.include_forks:
            return False
        return not (record["is_archived"] and not self._config.include_archived)

    def _clone_url(self, record: Mapping[str, Any]) -> str:
        """Адрес клонирования по `source.auth` (таблица стратегий вместо if/elif)."""
        table: dict[str, Callable[[Mapping[str, Any]], str]] = {
            "ssh": self._ssh_url,
            "https": self._https_url,
            "token": self._token_url,
            "auto": self._auto_url,
        }
        return table.get(self._config.auth, self._auto_url)(record)

    @staticmethod
    def _ssh_url(record: Mapping[str, Any]) -> str:
        """Адрес для `auth: ssh`."""
        return str(record["ssh_url"])

    @staticmethod
    def _https_url(record: Mapping[str, Any]) -> str:
        """Адрес для `auth: https` (чужие публичные организации — без ключей)."""
        return str(record["https_url"])

    def _token_url(self, record: Mapping[str, Any]) -> str:
        """HTTPS с `GITHUB_TOKEN` из окружения; токена нет → обычный HTTPS + `WARNING`."""
        token = os.environ.get("GITHUB_TOKEN", "")
        https_url = self._https_url(record)
        if not token:
            logger.warning("source.auth: token, но GITHUB_TOKEN не задан → клонирую по https")
            return https_url
        return https_url.replace("https://", f"https://x-access-token:{token}@", 1)

    def _auto_url(self, record: Mapping[str, Any]) -> str:
        """auto: приватные — по SSH, публичные — по HTTPS (ключи не нужны)."""
        if record["visibility"] == "private" and record["ssh_url"]:
            return self._ssh_url(record)
        return self._https_url(record) or self._ssh_url(record)
