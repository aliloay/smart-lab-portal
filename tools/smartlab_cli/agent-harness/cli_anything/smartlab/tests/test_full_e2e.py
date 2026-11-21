"""E2E: the INSTALLED command as a subprocess (upstream _resolve_cli pattern, no cwd).

Two layers:
  * TestCLISubprocess - against a local fake portal (stdlib HTTP server on a random port): real HTTP, real JSON,
    deterministic auth / error / timeout cases.
  * TestLiveReadOnly - against this laptop's REAL Smart Lab services (read-only). These FAIL (not skip) when a
    service is down, so an unavailable backend is never counted as a pass. Set SMARTLAB_REPO to the repo.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

GOOD, SLOW = "good-token-abcdef", "slow-token-abcdef"
NOW = datetime.now(timezone.utc).isoformat()
DEVICES = [
    {"id": 1, "device_uid": "MASTER_LAB01", "name": "Door", "device_type": "MASTER_CONTROLLER", "lab_id": 1,
     "ip_address": "192.168.1.151", "firmware_version": "portal-1.2", "last_seen_at": NOW, "is_online": True,
     "state": "ONLINE", "seconds_since_seen": 4, "lab_code": "LAB_01", "component_state": {"rfid": "ok"}},
    {"id": 2, "device_uid": "BIN_NODE_1", "name": "Bin", "device_type": "SENSOR_NODE", "lab_id": 1,
     "ip_address": "192.168.1.153", "firmware_version": "bin-0.6", "last_seen_at": NOW, "is_online": False,
     "state": "OFFLINE", "seconds_since_seen": 4000, "lab_code": "LAB_01"},
    {"id": 3, "device_uid": "PC-02", "name": "PC-02", "device_type": "PC", "lab_id": 1, "ip_address": None,
     "firmware_version": None, "last_seen_at": None, "is_online": False, "state": "NO_DATA",
     "seconds_since_seen": None, "lab_code": "LAB_01"},
]
SEEN: list[tuple[str, str]] = []


class FakePortal(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        SEEN.append(("GET", self.path))
        auth = self.headers.get("Authorization", "")
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._send(200, {"status": "ok", "database": True, "version": {"id": "test-build"}})
        if auth == f"Bearer {SLOW}":
            time.sleep(3)
        if auth not in (f"Bearer {GOOD}", f"Bearer {SLOW}"):
            return self._send(401, {"detail": "Not authenticated"})
        if path == "/api/devices":
            return self._send(200, DEVICES)
        if path == "/api/auth/me":
            return self._send(200, {"id": 7, "role": "ADMIN"})
        return self._send(404, {"detail": "nope"})

    def do_POST(self):
        SEEN.append(("POST", self.path))
        self._send(405, {})


@pytest.fixture(scope="module")
def portal():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakePortal)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-smartlab")

    @pytest.fixture(autouse=True)
    def _env(self, portal, tmp_path):
        self.env = {**os.environ, "SMARTLAB_API": portal, "SMARTLAB_HOME": str(tmp_path / "home"),
                    "SMARTLAB_TIMEOUT": "2", "PYTHONIOENCODING": "utf-8"}
        self.env.pop("SMARTLAB_TOKEN", None)

    def _run(self, args, token=None, check=False):
        env = dict(self.env)
        if token:
            env["SMARTLAB_TOKEN"] = token
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, env=env, check=check,
                              encoding="utf-8")

    def _json(self, args, token=None, code=0):
        r = self._run(["--json", *args], token)
        assert r.returncode == code, (r.returncode, r.stdout, r.stderr)
        e = json.loads(r.stdout)
        assert {"success", "command", "timestamp", "source", "freshness", "data", "warnings", "errors"} <= set(e)
        return e

    def test_help(self):
        r = self._run(["--help"])
        assert r.returncode == 0 and "read-only" in r.stdout.lower()

    def test_version(self):
        r = self._run(["--version"])
        assert r.returncode == 0 and "smartlab" in r.stdout

    def test_health_json(self):
        e = self._json(["health"])
        assert e["success"] and e["data"]["status"] == "ok" and e["source"].startswith("smartlab-api")

    def test_devices_need_sign_in(self):
        e = self._json(["devices", "list"], code=3)
        assert not e["success"] and e["errors"][0]["code"] == "AUTH_REQUIRED"

    def test_devices_list_labels(self):
        e = self._json(["devices", "list"], token=GOOD)
        st = {r["uid"]: r["status"] for r in e["data"]["rows"]}
        assert st == {"MASTER_LAB01": "ONLINE", "BIN_NODE_1": "OFFLINE", "PC-02": "UNKNOWN"}
        assert all(r["status"] != "ONLINE" or r["age_s"] is not None for r in e["data"]["rows"])

    def test_devices_offline_and_esp32(self):
        off = self._json(["devices", "offline"], token=GOOD)["data"]["rows"]
        assert {r["uid"] for r in off} == {"BIN_NODE_1", "PC-02"}
        esp = self._json(["esp32", "list"], token=GOOD)["data"]["rows"]
        assert {r["uid"] for r in esp} == {"MASTER_LAB01", "BIN_NODE_1"}

    def test_inspect_known_and_unknown(self):
        d = self._json(["devices", "inspect", "master_lab01"], token=GOOD)["data"]
        assert d["components"] == {"rfid": "ok"}
        e = self._json(["devices", "inspect", "NOPE"], token=GOOD, code=1)
        assert e["errors"][0]["code"] == "NOT_FOUND"

    def test_bad_token_is_auth_error(self):
        e = self._json(["devices", "list"], token="expired-xyz", code=3)
        assert e["errors"][0]["code"] == "AUTH_REQUIRED"

    def test_timeout_is_unavailable(self):
        e = self._json(["devices", "list"], token=SLOW, code=4)
        assert e["errors"][0]["code"] == "UNAVAILABLE"

    def test_api_down(self):
        env_api = self.env["SMARTLAB_API"]
        self.env["SMARTLAB_API"] = "http://127.0.0.1:9/api"
        try:
            e = self._json(["health"], code=4)
            assert e["errors"][0]["code"] == "UNAVAILABLE"
        finally:
            self.env["SMARTLAB_API"] = env_api

    def test_unknown_command(self):
        r = self._run(["unlock", "door"])
        assert r.returncode == 2

    def test_token_never_printed(self):
        r = self._run(["--json", "devices", "list"], token=GOOD)
        assert GOOD not in r.stdout and GOOD not in r.stderr

    def test_repl_with_piped_input(self):
        """Agents drive the REPL through a pipe (no console): it must work and exit cleanly."""
        r = subprocess.run(self.CLI_BASE, input="health\nunlock door\nexit\n", capture_output=True, text=True,
                           env=self.env, encoding="utf-8", timeout=60)
        assert r.returncode == 0, r.stderr[-600:]
        assert "status: ok" in r.stdout and "Goodbye" in r.stdout
        assert "No such command" in r.stdout + r.stderr       # dangerous words are simply not commands

    def test_only_gets_reached_the_portal(self):
        SEEN.clear()
        self._run(["--json", "devices", "list"], token=GOOD)
        self._run(["--json", "esp32", "list"], token=GOOD)
        assert SEEN and all(m == "GET" for m, _ in SEEN)


@pytest.mark.skipif(os.environ.get("SMARTLAB_LIVE") != "1", reason="live tests need SMARTLAB_LIVE=1 on the lab laptop")
class TestLiveReadOnly:
    """Real backends on this laptop. Run with SMARTLAB_LIVE=1 SMARTLAB_REPO=<repo>. A down service FAILS."""
    CLI_BASE = _resolve_cli("cli-anything-smartlab")

    def _json(self, *args, code=0):
        r = subprocess.run(self.CLI_BASE + ["--json", *args], capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert r.returncode == code, (args, r.returncode, r.stdout[-800:], r.stderr[-800:])
        return json.loads(r.stdout)

    def test_services_real(self):
        rows = {r["service"]: r["status"] for r in self._json("system", "services")["data"]["rows"]}
        assert rows["portal"] == "ONLINE" and rows["ollama"] == "ONLINE" and rows["knowledge"] == "ONLINE"

    def test_ai_models_real(self):
        d = self._json("ai", "models")["data"]
        names = {r["model"] for r in d["rows"]}
        assert "nomic-embed-text:latest" in names and d["ollama_version"]

    def test_knowledge_search_finds_relock_guard_without_model(self):
        d = self._json("knowledge", "search", "relock", "guard", "PN532")["data"]
        assert d["route"] == "lookup"
        assert any("SmartLab_Master_Portal" in (r["source"] or "") for r in d["rows"])

    def test_firmware_inventory_real(self):
        v = {r["folder"]: r["version"] for r in self._json("firmware", "inventory")["data"]["rows"]}
        assert v["SmartLab_Master_Portal"].startswith("portal-") and v["SmartLab_Consumable_Bin"].startswith("bin-")

    def test_automation_definitions_real(self):
        rows = self._json("automation", "list")["data"]["rows"]
        assert len(rows) >= 20 and all(r["name"] for r in rows)

    def test_github_status_real(self):
        d = self._json("github", "status")["data"]
        assert d["branch"] and isinstance(d["ahead_of_origin_main"], int)

    def test_doctor_real_no_fail_on_core_services(self):
        d = self._json("doctor")["data"]
        res = {r["check"]: r["result"] for r in d["rows"]}
        assert res["portal API"] == "PASS" and res["service ollama"] == "PASS"
        assert all(r["result"] in ("PASS", "WARN", "FAIL", "SKIP") for r in d["rows"])

    def test_cameras_status_real(self):
        rows = self._json("cameras", "status")["data"]["rows"]
        assert len(rows) == 2 and all(r["picture"] in ("ONLINE", "OFFLINE", "NOT_ACCESSIBLE", "UNKNOWN") for r in rows)
