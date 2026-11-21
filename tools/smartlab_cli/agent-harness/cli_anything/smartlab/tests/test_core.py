"""Unit tests - synthetic data only, no network, no real repo needed."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli_anything.smartlab.core import devices as dev
from cli_anything.smartlab.core import repo as repo_core
from cli_anything.smartlab.utils import api_client, config as cfgmod
from cli_anything.smartlab.utils.api_client import Client
from cli_anything.smartlab.utils.config import Config
from cli_anything.smartlab.utils.errors import (AuthRequired, Forbidden, InvalidInput, NotFound, SmartlabError,
                                                Unavailable)
from cli_anything.smartlab.utils.freshness import OFFLINE, ONLINE, STALE, UNKNOWN, device_status, human_age
from cli_anything.smartlab.utils.output import envelope, human, table
from cli_anything.smartlab.utils.redaction import redact, redact_text


# ------------------------------------------------------------------------------------- fixtures ---
@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("FOO=1\nDEVICE_API_KEY=devkey-abcdef123\n")
    kd = tmp_path / "tools" / "knowledge"
    kd.mkdir(parents=True)
    (kd / "config.json").write_text(json.dumps({"model": "qwen3:1.7b", "service_key": "kbkey-zyx987654",
                                                "redact_literals": ["Hunter2!"], "vault": "C:/v"}))
    fw = tmp_path / "firmware"
    (fw / "Node_A").mkdir(parents=True)
    (fw / "Node_A" / "cfg.h").write_text('#define FIRMWARE_VERSION "0.1.1"\n')
    (fw / "Node_B").mkdir()
    (fw / "Node_B" / "b.ino").write_text('const char *FIRMWARE = "bin-0.6";\n')
    (fw / "Node_B" / "build").mkdir()
    (fw / "Node_B" / "build" / "x.ino").write_text('const char *FIRMWARE = "bin-9.9";\n')
    (fw / "Master").mkdir()
    (fw / "Master" / "m.ino").write_text('body += "\\"firmware_version\\":\\"portal-1.2\\"";\n')
    n8 = tmp_path / "automation" / "n8n" / "json"
    n8.mkdir(parents=True)
    (n8 / "01.json").write_text(json.dumps({"id": "abc", "name": "Smart Lab 01 - Test", "active": True, "nodes": [
        {"name": "Hook", "type": "n8n-nodes-base.webhook", "parameters": {"path": "smartlab-x"}},
        {"name": "Every day", "type": "n8n-nodes-base.scheduleTrigger",
         "parameters": {"rule": {"interval": [{"field": "days", "triggerAtHour": 20}]}}},
        {"name": "Call", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://backend:8000/api/x?token=SECRET123456"}},
    ], "connections": {}}))
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "docs" / "reports" / "R1.md").write_text("# Report\npassword=topsecret99\nok\n")
    return tmp_path


@pytest.fixture
def cfg(fake_repo, monkeypatch, tmp_path_factory) -> Config:
    monkeypatch.setenv("SMARTLAB_REPO", str(fake_repo))
    for k in ("SMARTLAB_KB_KEY", "SMARTLAB_DEVICE_KEY", "SMARTLAB_TOKEN", "SMARTLAB_API"):
        monkeypatch.delenv(k, raising=False)
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(cfgmod, "USER_CONFIG", home / "config.json")
    monkeypatch.setattr(api_client, "TOKEN_FILE", home / "token.json")
    monkeypatch.setattr(api_client, "USER_DIR", home)
    return Config.load()


# --------------------------------------------------------------------------------------- config ---
def test_config_finds_repo_from_env(cfg, fake_repo):
    assert cfg.repo == fake_repo


def test_config_env_overrides(monkeypatch, cfg):
    monkeypatch.setenv("SMARTLAB_API", "http://x:1/api/")
    monkeypatch.setenv("SMARTLAB_TIMEOUT", "2.5")
    c = Config.load()
    assert c.api == "http://x:1/api" and c.timeout == 2.5


def test_find_repo_walks_up(tmp_path, monkeypatch, fake_repo):
    monkeypatch.delenv("SMARTLAB_REPO", raising=False)
    monkeypatch.setattr(cfgmod, "USER_CONFIG", tmp_path / "none.json")
    sub = fake_repo / "docs" / "reports"
    assert cfgmod.find_repo(sub) == fake_repo


def test_secret_readers(cfg):
    assert cfg.kb_key() == "kbkey-zyx987654"
    assert cfg.device_key() == "devkey-abcdef123"


def test_knowledge_config_has_no_secrets(cfg):
    k = cfg.knowledge_config()
    assert k["model"] == "qwen3:1.7b"
    assert "service_key" not in k and "redact_literals" not in k


def test_missing_repo_files(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTLAB_REPO", str(tmp_path))
    c = Config.load()
    assert c.kb_key() == "" and c.device_key() == "" and c.knowledge_config() == {}


# ------------------------------------------------------------------------------------ redaction ---
@pytest.mark.parametrize("raw,leak", [
    ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
    ("token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlMTIz", "eyJhbGciOiJIUzI1NiJ9"),
    ("password: hunter22", "hunter22"),
    ("rtsp://admin:pw@192.168.1.60/stream", "admin:pw"),
    ("http://user:secretpw@host/x", "secretpw"),
    ("qr SLB:~AbCdEfGhIjKlMnOp", "AbCdEfGhIjKlMnOp"),
    ("service_key = 'abc123456'", "abc123456"),
])
def test_redact_text(raw, leak):
    assert leak not in redact_text(raw)


def test_redact_keys_but_keep_lookalikes():
    out = redact({"password": "x1", "access_token": "t", "X-KB-Key": "k", "PASS": 3, "prompt_tokens": 120,
                  "has_own_key": True, "nested": [{"service_key": "s"}]})
    assert out["password"] == out["access_token"] == out["X-KB-Key"] == "[REDACTED]"
    assert out["nested"][0]["service_key"] == "[REDACTED]"
    assert out["PASS"] == 3 and out["prompt_tokens"] == 120 and out["has_own_key"] is True


def test_redact_extra_literals():
    assert "Hunter2!" not in redact_text("pw is Hunter2! ok", ("Hunter2!",))


# ------------------------------------------------------------------------------------ freshness ---
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("online,seen,expect", [
    (True, NOW - timedelta(seconds=30), ONLINE),
    (True, NOW - timedelta(seconds=900), STALE),
    (False, NOW - timedelta(seconds=10), OFFLINE),
    (True, None, UNKNOWN),
    (False, None, OFFLINE),
    (None, NOW - timedelta(seconds=10), UNKNOWN),
])
def test_device_status(online, seen, expect):
    assert device_status(online, seen.isoformat() if seen else None, 300, NOW) == expect


def test_naive_timestamp_is_utc():
    assert device_status(True, "2026-11-21T11:59:30", 300, NOW) == ONLINE


def test_human_age():
    assert human_age(None) == "never" and human_age(30) == "30s ago" and human_age(7200) == "2h ago"


# -------------------------------------------------------------------------------------- devices ---
def _d(uid, state, age, typ="SENSOR_NODE"):
    return {"device_uid": uid, "name": uid, "device_type": typ, "state": state, "seconds_since_seen": age,
            "lab_code": "LAB_01", "ip_address": "192.168.1.9", "firmware_version": "x"}


@pytest.mark.parametrize("state,age,expect", [
    ("ONLINE", 10, ONLINE), ("ONLINE", 1000, STALE), ("OFFLINE", 10, OFFLINE),
    ("NO_DATA", None, UNKNOWN), ("DEGRADED", 5, "DEGRADED"), ("weird", 5, UNKNOWN),
])
def test_label(state, age, expect):
    assert dev.label(_d("A", state, age), 300) == expect


def test_unknown_is_never_online():
    assert dev.label({"state": None}, 300) != ONLINE


def test_filters_and_summary():
    rows = [dev.shape(_d("A", "ONLINE", 5), 300), dev.shape(_d("B", "OFFLINE", 5000), 300),
            dev.shape(_d("P1", "OFFLINE", 9, "PC"), 300)]
    assert [r["uid"] for r in dev.filtered(rows, dev.ESP32_TYPES)] == ["A", "B"]
    assert [r["uid"] for r in dev.filtered(rows, None, "offline")] == ["B", "P1"]
    s = dev.summary(rows)
    assert s["total"] == 3 and s["online"] == 1 and set(s["not_online"]) == {"B", "P1"}


# ------------------------------------------------------------------------------------------ repo ---
def test_workflows_parse_triggers_and_redact(fake_repo):
    w = repo_core.workflows(fake_repo)
    assert w[0]["name"] == "Smart Lab 01 - Test" and w[0]["nodes"] == 3 and w[0]["http_calls"] == 1
    assert "webhook /smartlab-x" in w[0]["triggers"] and "triggerAtHour=20" in w[0]["triggers"]
    detail = repo_core.workflow(fake_repo, "01 - test")
    assert all("SECRET123456" not in u for u in detail["endpoints_called"])


def test_workflow_not_found(fake_repo):
    with pytest.raises(NotFound):
        repo_core.workflow(fake_repo, "nope")


def test_firmware_versions_ignore_build(fake_repo):
    v = {r["folder"]: r["version"] for r in repo_core.firmware(fake_repo)}
    assert v == {"Master": "portal-1.2", "Node_A": "0.1.1", "Node_B": "bin-0.6"}


def test_firmware_compare_normalises_prefix(fake_repo):
    out = repo_core.firmware_compare(fake_repo, [{"uid": "ENV", "type": "SENSOR_NODE", "firmware": "env-0.1.1"},
                                                 {"uid": "BIN", "type": "SENSOR_NODE", "firmware": "bin-0.5"},
                                                 {"uid": "X", "type": "CAMERA", "firmware": None}])
    assert [o["matches_source"] for o in out] == [True, False, None]


def test_logs_tail_filters_and_redacts(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("ok line\n[RFID] FAIL token=abc123456\nfine\n[WIFI] offline\n")
    assert repo_core.logs_tail(p, 10, errors_only=True) == ["[RFID] FAIL token=[REDACTED]", "[WIFI] offline"]
    with pytest.raises(InvalidInput):
        repo_core.logs_tail(p, 0)


def test_report_read_guards_path(fake_repo):
    r = repo_core.report_read(fake_repo, "docs/reports/R1.md")
    assert "topsecret99" not in r["text"]
    for bad in ("../outside.md", "docker-compose.yml", "..\\..\\x.md"):
        with pytest.raises((InvalidInput, NotFound)):
            repo_core.report_read(fake_repo, bad)


def test_git_compare_rejects_bad_ref(fake_repo):
    with pytest.raises(InvalidInput):
        repo_core.git_compare(fake_repo, "main; rm -rf /")


def test_need_repo():
    with pytest.raises(SmartlabError):
        repo_core.workflows(None)


# ------------------------------------------------------------------------------------ api client ---
def test_token_expiry_and_api_binding(cfg):
    c = Client(cfg)
    c.save_token("tok123", 3600, {"role": "ADMIN"})
    assert c.token() == "tok123"
    c.save_token("tok123", 1, {})
    assert c.token() is None                      # expires within 30 s -> treated as expired
    c.save_token("tok123", 3600, {})
    cfg.api = "http://elsewhere/api"
    assert Client(cfg).token() is None            # a token for another portal is never sent


def test_portal_requires_token(cfg):
    with pytest.raises(AuthRequired):
        Client(cfg).portal("/devices")


def test_unreachable_is_unavailable(cfg):
    cfg.api = "http://127.0.0.1:9/api"            # discard port: nothing listens
    cfg.timeout = 1
    with pytest.raises(Unavailable):
        Client(cfg, retries=0).portal("/health", auth=False)


@pytest.mark.parametrize("path", ["/devices/1", "/access/commands/next", "/emergency/activate", "/users"])
def test_portal_allow_list(cfg, path):
    with pytest.raises(Forbidden):
        Client(cfg).portal(path)


def test_probe_only_configured_urls(cfg):
    with pytest.raises(Forbidden):
        Client(cfg).probe("http://127.0.0.1:5678/rest/workflows/1/run")


# --------------------------------------------------------------------------------------- output ---
def test_envelope_schema_and_redaction():
    e = envelope("x", {"token": "abc", "n": 1}, "unit")
    assert set(e) == {"success", "command", "timestamp", "source", "freshness", "data", "warnings", "errors"}
    assert e["data"]["token"] == "[REDACTED]" and e["data"]["n"] == 1
    datetime.fromisoformat(e["timestamp"])


def test_human_rendering():
    e = envelope("x", {"rows": [{"a": 1, "b": None}], "columns": ["a", "b"]}, "unit", warnings=["w"])
    txt = human(e)
    assert "A" in txt and "WARNING: w" in txt and "[source: unit" in txt
    assert table([], ["a"]) == "(none)"
