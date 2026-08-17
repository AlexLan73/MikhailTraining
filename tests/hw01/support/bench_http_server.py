"""Локальный HTTP-сервер с фиксированной задержкой — инструмент таска H-07, не тест.

`tests/hw01/support/http_server.py` (этап 1) моделирует **исходы** проверки
(`/ok`, `/missing`, `/hang`, …) и знает всего один медленный адрес `/slow`.
Для замера `speedup` нужно другое: **много разных** адресов, каждый отвечает
`200` через одну и ту же задержку — тогда время прогона линейно по числу
запросов и `speedup` считается воспроизводимо, без интернета и флаки.

Класс намеренно назван **не** `Test*`: pytest собирает такие классы как тесты.
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: Задержка ответа по умолчанию — как в спеке этапа 2, §2.5 (локальный сервер 30 мс).
DEFAULT_DELAY_MS = 30


class DelayHttpServer:
    """`ThreadingHTTPServer` на `127.0.0.1`: любой адрес → `200` через `delay_ms`.

    Поток на запрос (`ThreadingHTTPServer`), поэтому сервер сам параллелизм
    клиента не ограничивает — узкое место остаётся на стороне сканера
    (`workers.parse` × семафор `http.workers`), что и требуется замеру.
    """

    def __init__(self, delay_ms: int = DEFAULT_DELAY_MS) -> None:
        self.delay_sec = max(int(delay_ms), 0) / 1000.0
        self._lock = threading.Lock()
        self._hits = 0
        self._active = 0
        self._peak = 0
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # --- жизненный цикл -------------------------------------------------

    def start(self) -> None:
        """Поднять сервер на свободном порту в отдельном потоке."""
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _DelayHandler)
        httpd.daemon_threads = True
        httpd.owner = self  # type: ignore[attr-defined]
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, name="bench-http", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Погасить сервер и дождаться его потока."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    # --- адреса и счётчики ----------------------------------------------

    @property
    def base_url(self) -> str:
        """Базовый адрес вида `http://127.0.0.1:<порт>`."""
        if self._httpd is None:
            raise RuntimeError("сервер не запущен: сначала start()")
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    @property
    def hits(self) -> int:
        """Сколько запросов обработано с момента запуска."""
        with self._lock:
            return self._hits

    @property
    def peak_concurrency(self) -> int:
        """Максимум одновременно обрабатываемых запросов за время жизни сервера."""
        with self._lock:
            return self._peak

    def reset(self) -> None:
        """Обнулить счётчики перед очередным прогоном."""
        with self._lock:
            self._hits = 0
            self._peak = 0

    def enter_hit(self) -> None:
        """Учесть вход в обработку запроса (обновляет пик одновременности)."""
        with self._lock:
            self._hits += 1
            self._active += 1
            self._peak = max(self._peak, self._active)

    def leave_hit(self) -> None:
        """Учесть выход из обработки запроса."""
        with self._lock:
            self._active -= 1


class _DelayHandler(BaseHTTPRequestHandler):
    """Обработчик: любой путь, `HEAD`/`GET` → `200 ok` после задержки."""

    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802 — имя задано BaseHTTPRequestHandler
        """GET: заголовки и тело."""
        self._serve(with_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 — имя задано BaseHTTPRequestHandler
        """HEAD: те же заголовки, без тела (сканер по умолчанию ходит HEAD)."""
        self._serve(with_body=False)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — сигнатура базового класса
        """Тишина: вывод сервера засоряет таблицу замера."""

    def _serve(self, with_body: bool) -> None:
        owner: DelayHttpServer = self.server.owner  # type: ignore[attr-defined]
        owner.enter_hit()
        try:
            time.sleep(owner.delay_sec)
            self._send(with_body)
        finally:
            owner.leave_hit()

    def _send(self, with_body: bool) -> None:
        """Ответ; клиент мог отвалиться по таймауту — это не ошибка замера."""
        payload = b"ok"
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if with_body:
                self.wfile.write(payload)
        except OSError:
            return
