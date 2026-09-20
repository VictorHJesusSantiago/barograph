"""Tests for the serving module (HTTP server and scheduler)."""

from __future__ import annotations

import json
import time

from barograph.serving import (
    BarographHTTPServer,
    RouteTable,
    Scheduler,
)


def test_route_table_match():
    table = RouteTable()

    def handler(params):
        return {"echo": params.get("name")}

    table.register("GET", "/weather/{name}", handler)
    result = table.route("GET", "/weather/sao_paulo")
    assert result is not None
    fn, params = result
    assert params == {"name": "sao_paulo"}
    assert fn(params)["echo"] == "sao_paulo"


def test_route_table_unknown_method():
    table = RouteTable()
    with __import__("pytest").raises(ValueError):
        table.register("PATCH", "/x", lambda p: {})


def test_server_dispatch():
    server = BarographHTTPServer()
    server.routes.register("GET", "/health", lambda p: {"status": "ok"})
    server.routes.register("POST", "/submit", lambda p: {"got": p.get("body")})
    status, payload = server.handle_request("GET", "/health")
    assert status == 200
    assert payload["status"] == "ok"
    status, payload = server.handle_request("POST", "/submit", {"x": 1})
    assert payload["got"] == {"x": 1}


def test_server_404():
    server = BarographHTTPServer()
    status, payload = server.handle_request("GET", "/missing")
    assert status == 404
    assert payload["error"] == "not_found"


def test_server_handler_error_500():
    server = BarographHTTPServer()
    server.routes.register("GET", "/boom", lambda p: 1 / 0)
    status, payload = server.handle_request("GET", "/boom")
    assert status == 500
    assert "error" in payload


def _pick_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_server_over_http():
    import urllib.request

    from barograph.serving.server import background_server

    port = _pick_port()
    server = BarographHTTPServer(port=port)
    server.routes.register("GET", "/ping", lambda p: {"pong": True})
    thread = background_server(server)

    url = f"http://127.0.0.1:{port}/ping"
    payload = None
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                payload = json.loads(resp.read().decode())
                break
        except Exception:
            time.sleep(0.05)
    thread.join(timeout=0.5)
    assert payload == {"pong": True}


def test_scheduler_runs_job():
    scheduler = Scheduler(tick_seconds=0.01)
    calls = {"n": 0}

    def job():
        calls["n"] += 1

    scheduler.add("job1", job, interval_seconds=0.02)
    scheduler.start()
    time.sleep(0.1)
    scheduler.stop()
    assert calls["n"] >= 1
    assert scheduler.stats["job1"] == calls["n"]


def test_scheduler_job_error_does_not_stop():
    scheduler = Scheduler(tick_seconds=0.01)
    errs = {"n": 0}
    runs = {"n": 0}

    def bad():
        errs["n"] += 1
        raise RuntimeError("job failed")

    def good():
        runs["n"] += 1

    bad_job = scheduler.add("bad", bad, interval_seconds=0.02)
    scheduler.add("good", good, interval_seconds=0.02)
    scheduler.start()
    time.sleep(0.1)
    scheduler.stop()
    assert bad_job.failures >= 1
    assert runs["n"] >= 1


def test_scheduler_stop_idempotent():
    scheduler = Scheduler()
    scheduler.stop()
    scheduler.stop()
