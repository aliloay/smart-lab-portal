"""Compose start-up order and the backend readiness check (2026-11-16 pre-lab hardening).

Run: py -m pytest -q tools/ops/test_compose_startup.py
The healthcheck command is taken from docker-compose.yml itself and run against a stub server, so what is tested is
what Docker will run. `docker compose config` is checked only when docker is installed.
"""
import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def _health_command():
    t = COMPOSE["services"]["backend"]["healthcheck"]["test"]
    assert t[0] == "CMD" and t[1] == "python" and t[2] == "-c"
    return t[3]


class _Stub(BaseHTTPRequestHandler):
    reply = (200, {"status": "ok", "database": True})

    def do_GET(self):
        code, body = type(self).reply
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def _run_check(reply):
    """Run the compose healthcheck command with the port swapped for a stub server's; returns the exit code."""
    _Stub.reply = reply
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code = _health_command().replace("127.0.0.1:8000", f"127.0.0.1:{srv.server_port}")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20).returncode
    finally:
        srv.shutdown()


def test_ready_only_when_status_ok_and_database_true():
    assert _run_check((200, {"status": "ok", "database": True})) == 0


def test_a_degraded_database_is_not_ready_even_though_http_is_200():
    # /api/health answers 200 + "degraded" when the database is down; a status-code-only check would pass this
    assert _run_check((200, {"status": "degraded", "database": False})) == 1
    assert _run_check((200, {"status": "ok", "database": False})) == 1


def test_http_errors_and_a_missing_server_are_not_ready():
    assert _run_check((500, {"detail": "boom"})) == 1
    code = _health_command().replace("127.0.0.1:8000", "127.0.0.1:1")          # nothing listens there
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20).returncode == 1


def test_the_check_prints_nothing_and_reads_no_environment():
    cmd = _health_command()
    assert "environ" not in cmd and "getenv" not in cmd and "print" not in cmd


def test_backend_healthcheck_timing():
    h = COMPOSE["services"]["backend"]["healthcheck"]
    assert (h["interval"], h["timeout"], h["retries"], h["start_period"]) == ("10s", "5s", 5, "20s")


def test_frontend_waits_for_a_ready_backend_and_there_is_no_cycle():
    deps = COMPOSE["services"]["frontend"]["depends_on"]
    assert deps["backend"]["condition"] == "service_healthy"
    graph = {n: list((s.get("depends_on") or {}).keys() if isinstance(s.get("depends_on"), dict) else (s.get("depends_on") or []))
             for n, s in COMPOSE["services"].items()}
    seen, stack = set(), set()

    def visit(n):
        assert n not in stack, f"dependency cycle through {n}"
        if n in seen:
            return
        stack.add(n)
        for m in graph.get(n, []):
            visit(m)
        stack.discard(n)
        seen.add(n)

    for n in graph:
        visit(n)


def test_n8n_is_not_blocked_on_backend_readiness():
    # n8n runs by itself and only calls the API when a workflow fires: a started backend is enough
    assert COMPOSE["services"]["n8n"]["depends_on"] == ["backend"]


def test_lan_access_to_the_api_is_kept_for_the_esp32_nodes():
    ports = COMPOSE["services"]["backend"]["ports"]
    assert any(str(p).endswith(":8000") and "127.0.0.1" not in str(p) for p in ports)


def test_shared_device_key_stays_on_until_every_node_has_its_own():
    assert "DEVICE_SHARED_KEY:-true" in COMPOSE["services"]["backend"]["environment"]["DEVICE_SHARED_KEY"]


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.parametrize("profile", [[], ["--profile", "automation"]])
def test_compose_config_is_valid(profile):
    r = subprocess.run(["docker", "compose", *profile, "config", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-300:]
