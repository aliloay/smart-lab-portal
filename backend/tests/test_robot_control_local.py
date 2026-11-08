"""UR5e Home / Stop with the robot in LOCAL mode, through the Local-mode agent (2026-10-26). The agent is faked:
nothing reaches a robot. Official UR reference: the Dashboard's load/play/stop/pause are Remote-only, so in Local mode
only a program started on the pendant (External Control) can carry the portal's Home / Stop."""
import pytest

from app.services import robot_control as rctl
from app.services import ur_agent
from tests.conftest import auth_headers
from tests.test_robot_control import cmd, ur  # noqa: F401  (fixture)


def agent_state(mode="dry_run", control="LOCAL", driver="PORTAL_PROGRAM"):
    return {"mode": mode, "program": "portal_control.urp", "latched": False,
            "controller": {"control_mode": control, "driver": driver, "playing": driver != "IDLE", "moving": False},
            "state": {"remote": control == "REMOTE", "robot_mode": "RUNNING", "safety": "NORMAL"},
            "home_checks": [{"key": "program", "name": "Pendant program playing", "ok": driver == "PORTAL_PROGRAM",
                             "detail": driver}]}


class FakeAgent:
    def __init__(self, st, answer=None):
        self.st, self.answer, self.posts = st, answer, []

    def __call__(self, method, path, body=None, timeout=2.0):
        if method == "GET":
            return self.st
        self.posts.append((path, body))
        return self.answer


@pytest.fixture(autouse=True)
def _local(monkeypatch):
    rctl.reset()
    monkeypatch.setattr(rctl, "UR_PATH", "local_agent")
    ur_agent._cache.update(t=0.0, v=None)
    yield
    rctl.reset()


def fake(monkeypatch, st, answer=None):
    a = FakeAgent(st, answer)
    monkeypatch.setattr(ur_agent, "call", a)
    ur_agent._cache.update(t=0.0, v=None)
    return a


def take(client, staff, rid):
    h = auth_headers(client, staff.email)
    assert client.post(f"/api/robots/{rid}/control/request", headers=h).status_code == 200
    return h


def test_agent_not_running_sends_nothing_and_says_so(monkeypatch, client, staff, ur):
    a = fake(monkeypatch, None)
    h = take(client, staff, ur.id)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "UNAVAILABLE" and "agent" in r["reason"] and a.posts == []
    s = client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-0001"}).json()
    assert s["status"] == "UNAVAILABLE" and a.posts == []
    checks = {c["key"]: c for c in s["master"]["checks"]}
    assert checks["agent"]["ok"] is False and "not running" in checks["agent"]["detail"]


def test_local_mode_home_goes_through_the_agent_in_dry_run(monkeypatch, client, staff, ur):
    a = fake(monkeypatch, agent_state(), {"status": "DRY_RUN", "reason": "checks passed - would send: moveJ ... (nothing sent)"})
    h = take(client, staff, ur.id)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "DRY_RUN" and "nothing sent" in r["reason"]
    assert a.posts == [("/command", {"action": "home", "command_id": "portal", "confirmed": True})]
    st = client.get(f"/api/robots/{ur.id}/control", headers=h).json()
    assert st["controller_mode"] == "LOCAL:PORTAL_PROGRAM"
    m = st["master"]
    assert m["path"] == "local_agent" and m["local"]["controller"]["control_mode"] == "LOCAL"
    assert "Remote mode" in m["local_limits"] and "NOT a safety-rated" in m["estop_note"]
    keys = {c["key"]: c["ok"] for c in m["checks"]}
    assert keys["agent"] and keys["program"] and keys["remote"]          # Local mode is fine on this path


def test_backend_and_agent_must_agree_on_the_mode(monkeypatch, client, staff, ur):
    a = fake(monkeypatch, agent_state(mode="live"), {"status": "REQUESTED", "reason": "sent"})
    h = take(client, staff, ur.id)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "REJECTED" and "both must agree" in r["reason"] and a.posts == []


def test_stop_of_another_program_in_local_mode_is_reported_unsupported_not_stopped(monkeypatch, client, staff, ur):
    a = fake(monkeypatch, agent_state(driver="OTHER_PROGRAM"),
             {"status": "UNSUPPORTED", "reason": "Local mode: another program ... only in Remote mode",
              "class": {"control_mode": "LOCAL", "driver": "OTHER_PROGRAM"}})
    h = auth_headers(client, staff.email)
    s = client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-0002"}).json()
    assert s["status"] == "UNSUPPORTED" and "Remote mode" in s["reason"]
    assert s["master"]["stop_latched"] is True                          # Home stays blocked anyway
    assert a.posts[0][1]["action"] == "stop"


def test_remote_mode_stop_falls_back_to_the_dashboard_path(monkeypatch, client, staff, ur):
    fake(monkeypatch, agent_state(control="REMOTE", driver="OTHER_PROGRAM"),
         {"status": "UNSUPPORTED", "reason": "Remote mode: the backend's Dashboard 'stop' path applies",
          "class": {"control_mode": "REMOTE", "driver": "OTHER_PROGRAM"}})
    h = auth_headers(client, staff.email)
    s = client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-0003"}).json()
    assert s["status"] == "DRY_RUN" and "Dashboard 'stop'" in s["reason"]       # dry run: nothing sent


def test_home_still_needs_portal_ownership_and_confirmation(monkeypatch, client, staff, ur):
    a = fake(monkeypatch, agent_state(), {"status": "DRY_RUN", "reason": "x"})
    h = auth_headers(client, staff.email)
    assert cmd(client, h, ur.id).json()["status"] == "REJECTED"           # no ownership
    take(client, staff, ur.id)
    assert cmd(client, h, ur.id, cid="cmd-0002", confirmed=False).status_code == 422
    assert a.posts == []
