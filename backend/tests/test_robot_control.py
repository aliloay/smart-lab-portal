"""Robot control requests (Home / routines / stop): ownership, checks, audit. Mocked adapters only -
nothing is ever sent to a controller, and every real adapter is UNAVAILABLE until commissioned."""
import pytest

from app.models import AuditLog, Device
from app.services import robot_control as rctl
from app.services.ur_dashboard import Dashboard as _RealDashboard
from tests.conftest import auth_headers
from tests.test_robots import tele


@pytest.fixture(autouse=True)
def _fresh():
    rctl.reset()
    yield
    rctl.reset()


@pytest.fixture
def ur(client, db, lab, device_headers):
    tele(client, device_headers)
    return db.query(Device).filter_by(device_uid="UR5E_TEST").one()


def cmd(client, h, rid, action="home", cid="cmd-0001", confirmed=True, routine=None):
    return client.post(f"/api/robots/{rid}/control/command", headers=h,
                       json={"action": action, "command_id": cid, "confirmed": confirmed, "routine": routine})


class ReadyMock(rctl.Adapter):
    """A commissioned, ready controller - tests only."""
    name = "MOCK"
    def capabilities(self):
        return {"home": True, "routines": ["PICK_DEMO"], "stop": True, "interface": "mock", "unavailable_reason": None}
    def controller_mode(self):
        return "REMOTE_READY"
    def execute(self, action, routine):
        return rctl.Result("REQUESTED", "sent to mock")


def test_students_cannot_see_or_take_control(client, alice, ur):
    h = auth_headers(client, alice.email)
    assert client.get(f"/api/robots/{ur.id}/control", headers=h).status_code == 403
    assert client.post(f"/api/robots/{ur.id}/control/request", headers=h).status_code == 403
    assert cmd(client, h, ur.id).status_code == 403


def test_ur5e_home_is_a_dry_run_by_default_and_fanuc_is_unavailable(client, db, staff, ur, device_headers):
    h = auth_headers(client, staff.email)
    st = client.get(f"/api/robots/{ur.id}/control", headers=h).json()
    assert st["adapter"] == "UR5e" and st["capabilities"]["home"] is True and "DRY RUN" in st["capabilities"]["interface"]
    assert st["controller_mode"] == "DRY_RUN_SIMULATED"          # never shown as a real ready controller
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "DRY_RUN" and "load home.urp ; play" in r["reason"] and "nothing sent" in r["reason"]
    assert rctl.FanucAdapter().execute("home", None).status == "UNAVAILABLE"


class FakeDashboard:
    """Stands in for the UR5e's Dashboard Server - records what would be sent."""
    sent = []
    def __init__(self, host, timeout=2.0): pass
    def ask(self, c):
        FakeDashboard.sent.append(c)
        return {"is in remote control": "true", "safetystatus": "Safetystatus: NORMAL", "robotmode": "Robotmode: RUNNING",
                "programState": "STOPPED home.urp"}.get(c, f"{c} ok")
    def mode(self):
        return _RealDashboard.mode(self)


def test_live_mode_sends_only_load_home_and_play(monkeypatch, client, staff, ur):
    from app.services import ur_dashboard
    monkeypatch.setattr(rctl, "MODE", "live")
    monkeypatch.setattr(ur_dashboard, "Dashboard", FakeDashboard)
    FakeDashboard.sent = []
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "REQUESTED" and "watch the twin" in r["reason"]
    assert [c for c in FakeDashboard.sent if c in ("load home.urp", "play", "stop")] == ["load home.urp", "play"]


def test_live_mode_refuses_when_the_pendant_is_in_local(monkeypatch, client, staff, ur):
    from app.services import ur_dashboard
    class Local(FakeDashboard):
        def ask(self, c):
            FakeDashboard.sent.append(c)
            return "false" if c == "is in remote control" else super().ask(c)
    monkeypatch.setattr(rctl, "MODE", "live")
    monkeypatch.setattr(ur_dashboard, "Dashboard", Local)
    FakeDashboard.sent = []
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    assert cmd(client, h, ur.id).json()["status"] == "UNAVAILABLE"
    assert "play" not in FakeDashboard.sent


def test_dashboard_client_refuses_anything_but_its_allowlist():
    from app.services.ur_dashboard import Dashboard
    with pytest.raises(ValueError):
        Dashboard("192.0.2.1").ask("power on")


def test_fanuc_routes_to_its_own_adapter():
    assert rctl.adapter_for("FANUC").name == "FANUC" and rctl.adapter_for("UR5e").name == "UR5e"
    assert rctl.adapter_for("something").name == "none"


def test_only_one_owner_until_released(client, staff, admin, ur):
    hs, ha = auth_headers(client, staff.email), auth_headers(client, admin.email)
    assert client.post(f"/api/robots/{ur.id}/control/request", headers=hs).status_code == 200
    r = client.post(f"/api/robots/{ur.id}/control/request", headers=ha)
    assert r.status_code == 409 and "release" in r.json()["detail"]
    assert client.post(f"/api/robots/{ur.id}/control/release", headers=ha).json()["released"] is False
    assert client.post(f"/api/robots/{ur.id}/control/release", headers=hs).json()["released"] is True
    assert client.post(f"/api/robots/{ur.id}/control/request", headers=ha).status_code == 200


def test_ownership_expires(monkeypatch, client, staff, ur):
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    t = rctl.time.time()
    monkeypatch.setattr(rctl.time, "time", lambda: t + rctl.OWNERSHIP_S + 1)
    assert rctl.owner(ur.id) is None


def test_commands_need_ownership_confirmation_fresh_telemetry_and_an_allowlisted_action(monkeypatch, client, db, staff, ur):
    monkeypatch.setattr(rctl, "adapter_for", lambda m: ReadyMock())
    h = auth_headers(client, staff.email)
    assert cmd(client, h, ur.id).json()["status"] == "REJECTED"                       # no ownership
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    assert cmd(client, h, ur.id, confirmed=False, cid="cmd-0002").status_code == 422  # no confirmation
    assert cmd(client, h, ur.id, action="jog", cid="cmd-0003").json()["status"] == "REJECTED"
    assert cmd(client, h, ur.id, action="routine", routine="X", cid="cmd-0004").json()["status"] == "REJECTED"
    assert cmd(client, h, ur.id, cid="cmd-0005").json()["status"] == "REQUESTED"      # mock only
    from datetime import datetime, timedelta, timezone
    ur.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=10); db.commit()
    r = cmd(client, h, ur.id, cid="cmd-0006").json()
    assert r["status"] == "REJECTED" and "not fresh" in r["reason"]


def test_unknown_controller_mode_blocks_even_a_ready_owner(monkeypatch, client, staff, ur):
    class Pendant(ReadyMock):
        def controller_mode(self): return "LOCAL_PENDANT"
    monkeypatch.setattr(rctl, "adapter_for", lambda m: Pendant())
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    assert cmd(client, h, ur.id).json()["status"] == "UNAVAILABLE"


def test_duplicate_command_id_is_never_executed_twice(monkeypatch, client, db, staff, ur):
    calls = []
    class Counting(ReadyMock):
        def execute(self, a, r):
            calls.append(a); return super().execute(a, r)
    monkeypatch.setattr(rctl, "adapter_for", lambda m: Counting())
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    assert cmd(client, h, ur.id).json()["status"] == "REQUESTED"
    assert cmd(client, h, ur.id).json()["status"] == "DUPLICATE"
    assert calls == ["home"]
    assert db.query(AuditLog).filter_by(action="ROBOT_COMMAND").count() == 2


def test_a_restart_leaves_no_owner(client, staff, ur):
    client.post(f"/api/robots/{ur.id}/control/request", headers=auth_headers(client, staff.email))
    rctl.reset()                                      # what a backend restart does to memory
    assert rctl.owner(ur.id) is None
