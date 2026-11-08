"""Hardware stop relay (ESP32 -> UR5e safeguard stop input) and the automatic Home countdown (2026-10-26).
Nothing reaches a robot: the relay is a polled HTTP state, the UR agent is faked."""
import pytest

from app.api.deps import hash_device_key
from app.models import Device, DeviceType
from app.services import robot_control as rctl
from app.services import stop_relay, ur_agent
from tests.conftest import auth_headers
from tests.test_robot_control import ur  # noqa: F401  (fixture)
from tests.test_robot_control_local import agent_state, fake

KEY = "relay-test-key-0123456789"


@pytest.fixture(autouse=True)
def _relay(monkeypatch):
    rctl.reset(); stop_relay.reset()
    monkeypatch.setattr(rctl, "UR_PATH", "local_agent")
    monkeypatch.setattr(stop_relay, "RELAY_UID", "UR5E_STOP_RELAY")
    monkeypatch.setattr(stop_relay, "ROBOT_UID", "UR5E_TEST")
    ur_agent._cache.update(t=0.0, v=None)
    yield
    rctl.reset(); stop_relay.reset()


@pytest.fixture
def relay(db, lab):
    d = Device(device_uid="UR5E_STOP_RELAY", name="UR5e stop relay", device_type=DeviceType.OTHER, lab_id=lab.id,
               key_hash=hash_device_key(KEY))
    db.add(d); db.commit()
    return d


def poll(client, key=KEY, **q):
    return client.get("/api/robots/stop-relay/poll", headers={"X-Device-Key": key}, params=q)


def test_relay_needs_its_own_key(client, relay, ur, device_headers):
    assert poll(client, key="wrong").status_code == 401
    assert poll(client, key=device_headers["X-Device-Key"]).status_code == 403     # the shared door key: refused
    r = poll(client, relay="RUN")
    assert r.status_code == 200 and r.json()["stop"] is False


def test_portal_stop_opens_relay_and_reports_latency(monkeypatch, client, staff, relay, ur):
    fake(monkeypatch, agent_state(), {"status": "DRY_RUN", "reason": "x"})
    seq0 = poll(client, relay="RUN").json()["seq"]
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-relay-1"})
    r = poll(client, relay="RUN").json()
    assert r["stop"] is True and r["seq"] == seq0 + 1
    poll(client, relay="STOP", applied_seq=r["seq"])
    m = client.get(f"/api/robots/{ur.id}/control", headers=h).json()["master"]
    assert m["relay"]["online"] and m["relay"]["relay"] == "STOP" and m["relay"]["in_sync"]
    assert m["relay"]["latency_ms"] is not None


def test_recovery_refused_while_a_program_is_paused(monkeypatch, client, admin, relay, ur):
    st = agent_state(); st["state"]["program_state"] = "PAUSED pick.urp"
    a = fake(monkeypatch, st, {"ok": True, "reason": "cleared"})
    h = auth_headers(client, admin.email)
    client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-relay-2"})
    r = client.post(f"/api/robots/{ur.id}/control/recover", headers=h)
    assert r.status_code == 409 and "Stop on the teach pendant" in r.json()["detail"]
    assert poll(client).json()["stop"] is True                         # still stopped
    st["state"]["program_state"] = "STOPPED"; ur_agent._cache.update(t=0.0, v=None)
    r = client.post(f"/api/robots/{ur.id}/control/recover", headers=h)
    assert r.status_code == 200 and poll(client).json()["stop"] is False
    assert ("/recover", {}) in a.posts                                  # the agent's latch is cleared too


def test_relay_unknown_program_state_blocks_release():
    assert "unknown" in stop_relay.release_blocker(None)
    assert stop_relay.release_blocker("STOPPED") is None
    assert "PLAYING" in stop_relay.release_blocker("PLAYING portal_control.urp")


def test_auto_home_countdown_is_shown_and_cancellable(monkeypatch, client, staff, ur):
    st = agent_state()
    st["auto_home"] = {"enabled": True, "phase": "COUNTDOWN", "remaining_s": 12.0, "idle_s": 120, "countdown_s": 20}
    a = fake(monkeypatch, st, {"ok": True, "was": "COUNTDOWN", "reason": "automatic Home cancelled by Staff"})
    h = auth_headers(client, staff.email)
    m = client.get(f"/api/robots/{ur.id}/control", headers=h).json()["master"]
    assert m["auto_home"]["phase"] == "COUNTDOWN" and m["auto_home"]["remaining_s"] == 12.0
    r = client.post(f"/api/robots/{ur.id}/control/auto-home/cancel", headers=h)
    assert r.status_code == 200 and "cancelled" in r.json()["message"]
    assert a.posts[-1][0] == "/auto_home/cancel"


def test_relay_not_configured_is_invisible(monkeypatch, client, staff, ur):
    monkeypatch.setattr(stop_relay, "RELAY_UID", "")
    fake(monkeypatch, agent_state())
    m = client.get(f"/api/robots/{ur.id}/control", headers=auth_headers(client, staff.email)).json()["master"]
    assert m["relay"] is None
