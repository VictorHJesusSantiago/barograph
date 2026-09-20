"""A small dependency-free JSON HTTP server for exposing barograph results.

Built on :mod:`http.server` and :mod:`json`, this is intentionally minimal so
that it can run in reduced environments without FastAPI/Flask. Register
route handlers as ``{method: {(path_regex, callable)}}``.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from loguru import logger

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class RouteTable:
    """A tiny path router mapping ``(method, pattern) -> handler``."""

    def __init__(self) -> None:
        self._routes: dict[str, list[tuple[Any, Handler]]] = {
            "GET": [],
            "POST": [],
            "PUT": [],
            "DELETE": [],
        }

    def register(self, method: str, path: str, handler: Handler) -> None:
        """Register a handler for *method* / *path*.

        Paths support a trailing ``{name}`` capturing a single path segment.
        """
        if method.upper() not in self._routes:
            raise ValueError(f"Unsupported method {method}")
        import re

        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        pattern = f"^{pattern}$"
        self._routes[method.upper()].append((re.compile(pattern), handler))

    def route(self, method: str, path: str) -> tuple[Handler, dict[str, str]] | None:
        """Match *path*, returning ``(handler, path_params)`` or ``None``."""
        for compiled, handler in self._routes.get(method.upper(), []):
            match = compiled.match(path)
            if match:
                return handler, match.groupdict()
        return None


@dataclass
class BarographHTTPServer:
    """Configure and serve an HTTP API backed by :class:`RouteTable`."""

    routes: RouteTable = field(default_factory=RouteTable)
    port: int = 8080
    host: str = "127.0.0.1"

    def handle_request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        """Dispatch a request, returning ``(status, payload)``.

        This is used both by the HTTP handler and directly in tests.
        """
        matched = self.routes.route(method, path)
        if matched is None:
            return 404, {"error": "not_found"}
        handler, params = matched
        try:
            payload = handler({**params, **({"body": body} if body else {})})
        except Exception as exc:  # noqa: BLE001 - report as 500
            logger.exception("Handler error for {} {}", method, path)
            return 500, {"error": str(exc)}
        return 200, payload

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class _Handler(BaseHTTPRequestHandler):  # type: ignore[misc]
            def _respond(self) -> None:
                parsed = urlparse(self.path)
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b""
                body: dict[str, Any] = {}
                if raw:
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        body = {"error": "invalid_json"}
                status, payload = server.handle_request(self.command, parsed.path, body)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                self._respond()

            def do_POST(self) -> None:  # noqa: N802
                self._respond()

            def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
                logger.debug("HTTP: " + fmt, *args)

        return _Handler

    def serve_forever(self) -> None:
        """Block serving until interrupted."""
        handler = self._make_handler()
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        logger.info("Serving Barograph on {}:{}", self.host, self.port)
        httpd.serve_forever()


def start_server(
    routes: RouteTable, port: int = 8080, host: str = "127.0.0.1"
) -> BarographHTTPServer:
    """Return a configured :class:`BarographHTTPServer` (does not block)."""
    return BarographHTTPServer(routes=routes, port=port, host=host)


def background_server(server: BarographHTTPServer) -> threading.Thread:
    """Run *server* in a background daemon thread and return the thread."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
