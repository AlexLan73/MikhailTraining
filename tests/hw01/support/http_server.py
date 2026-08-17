"""Локальный HTTP-сервер для тестов проверки ссылок (спека разработки, §3.5).

Реальная сеть в тестах запрещена (D11), поэтому все исходы `HttpChecker`
моделируются здесь, на `127.0.0.1` со случайным портом:

| адрес     | ответ                                                        |
|-----------|--------------------------------------------------------------|
| `/ok`     | 200                                                          |
| `/moved`  | 301 → `/ok`                                                  |
| `/missing`| 404                                                          |
| `/boom`   | 500                                                          |
| `/hang`   | молчит, пока сервер не остановят (проверка `TIMEOUT`)         |
| `/slow`   | отвечает через `hold_sec` (проверка семафора)                 |

Плюс режимы «405 на HEAD» (откат на GET) и «403 без нужного `User-Agent`»,
счётчик запросов по адресу (кэш) и пик одновременных запросов (семафор).

Класс намеренно назван **не** `Test*`: pytest собирает такие классы как тесты.
"""

from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

#: Сколько ждёт `/hang`, если сервер забыли остановить (страховка от вечного потока).
_HANG_LIMIT_SEC = 30.0


class LocalHttpServer:
    """Фасад над `ThreadingHTTPServer`: запуск, режимы, счётчики, остановка."""

    def __init__(self, hold_sec: float = 0.25) -> None:
        self.hold_sec = hold_sec
        self.head_405 = False
        self.expected_user_agent: str | None = None
        self.release = threading.Event()
        self._lock = threading.Lock()
        self._hits: Counter[str] = Counter()
        self._active = 0
        self._peak = 0
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # --- жизненный цикл -------------------------------------------------

    def start(self) -> None:
        """Поднять сервер на свободном порту `127.0.0.1` в отдельном потоке."""
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.daemon_threads = True
        httpd.owner = self  # type: ignore[attr-defined]
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, name="test-http", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Отпустить `/hang`, затем погасить сервер (иначе тест повиснет)."""
        self.release.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    # --- адреса ---------------------------------------------------------

    @property
    def base_url(self) -> str:
        """Базовый адрес вида `http://127.0.0.1:<порт>`."""
        if self._httpd is None:
            raise RuntimeError("сервер не запущен: сначала start()")
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def url(self, path: str) -> str:
        """Полный адрес эндпоинта (`/ok`, `/hang`, …)."""
        return f"{self.base_url}{path}"

    # --- счётчики (зовёт обработчик из своего потока) --------------------

    def hits(self, path: str) -> int:
        """Сколько запросов пришло на адрес (без учёта query)."""
        with self._lock:
            return self._hits[path]

    @property
    def peak_concurrency(self) -> int:
        """Максимум одновременно обрабатываемых запросов за время жизни сервера."""
        with self._lock:
            return self._peak

    def record_hit(self, path: str) -> None:
        """Учесть запрос и вход в обработку (обновляет пик одновременности)."""
        with self._lock:
            self._hits[path] += 1
            self._active += 1
            self._peak = max(self._peak, self._active)

    def finish_hit(self) -> None:
        """Учесть выход из обработки запроса."""
        with self._lock:
            self._active -= 1


class _Handler(BaseHTTPRequestHandler):
    """Обработчик: маршрут по пути, режимы берёт у `LocalHttpServer`."""

    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802 — имя задано BaseHTTPRequestHandler
        """GET: заголовки и тело."""
        self._serve(with_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 — имя задано BaseHTTPRequestHandler
        """HEAD: те же заголовки, без тела."""
        self._serve(with_body=False)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — сигнатура базового класса
        """Тишина: вывод сервера засоряет отчёт pytest."""

    def _serve(self, with_body: bool) -> None:
        owner: LocalHttpServer = self.server.owner  # type: ignore[attr-defined]
        path = urlsplit(self.path).path
        owner.record_hit(path)
        try:
            self._route(owner, path, with_body)
        finally:
            owner.finish_hit()

    def _route(self, owner: LocalHttpServer, path: str, with_body: bool) -> None:
        """Режимы важнее маршрута: сначала `User-Agent`, потом «405 на HEAD»."""
        expected = owner.expected_user_agent
        if expected is not None and self.headers.get("User-Agent") != expected:
            self._send(403, with_body, b"forbidden")
            return
        if owner.head_405 and self.command == "HEAD":
            self._send(405, with_body, b"method not allowed")
            return
        if path == "/ok":
            self._send(200, with_body, b"ok")
        elif path == "/moved":
            self._send(301, with_body, b"", extra={"Location": "/ok"})
        elif path == "/missing":
            self._send(404, with_body, b"missing")
        elif path == "/boom":
            self._send(500, with_body, b"boom")
        elif path == "/hang":
            owner.release.wait(timeout=_HANG_LIMIT_SEC)
            self._send(200, with_body, b"late")
        elif path == "/slow":
            owner.release.wait(timeout=owner.hold_sec)
            self._send(200, with_body, b"slow")
        else:
            self._send(404, with_body, b"unknown endpoint")

    def _send(
        self,
        code: int,
        with_body: bool,
        payload: bytes,
        extra: dict[str, str] | None = None,
    ) -> None:
        """Ответ; клиент мог уже отвалиться по таймауту (`/hang`) — это не ошибка."""
        try:
            self.send_response(code)
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if with_body and payload:
                self.wfile.write(payload)
        except OSError:
            return
