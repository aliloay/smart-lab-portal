"""Robot control requests (Home / routines / stop): ownership, checks, audit. Mocked adapters only -
nothing is ever sent to a controller, and every real adapter is UNAVAILABLE until commissioned."""
import pytest

from app.models import AuditLog, Device
from app.services import robot_control as rctl
from app.services.ur_dashboard import Dashboard as _RealDashboard
from tests.conftest import auth_headers
from tests.test_robots import tele


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    rctl.reset()
    # These tests cover the REMOTE-mode Dashboard path; the Local-mode agent path has its own file
    # (tests/test_robot_control_local.py).
    monkeypatch.setattr(rctl, "UR_PATH", "dashboard")
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
    # Default HOME = the pendant's validated Home program (not a direct joint move), target from feedback.
    assert r["status"] == "DRY_RUN" and "load home.urp" in r["reason"] and "'play'" in r["reason"]         and "[-15.00, -126.00, 117.03, -80.00, 91.00, 95.27]" in r["reason"] and "nothing sent" in r["reason"]
    assert rctl.FanucAdapter().execute("home", None).status == "UNAVAILABLE"


class FakeDashboard:
    """Stands in for the UR5e's Dashboard Server - records what would be sent."""
    sent = []
    def __init__(self, host, timeout=2.0): pass
    def ask(self, c):
        FakeDashboard.sent.append(c)
        # Real UR Dashboard Server replies (UR e-Series dashboard documentation).
        if c.startswith("load "):
            return f"Loading program: /programs/{c[5:]}"
        return {"is in remote control": "true", "safetystatus": "Safetystatus: NORMAL", "robotmode": "Robotmode: RUNNING",
                "programState": "STOPPED home.urp", "play": "Starting program", "stop": "Stopped"}.get(c, f"{c} ok")
    def mode(self):
        return _RealDashboard.mode(self)


def test_live_mode_movej_method_sends_only_the_home_movej(monkeypatch, client, staff, ur):
    """The direct joint move is only used when the operator chose UR5E_HOME_METHOD=movej."""
    from app.services import ur_dashboard, ur_script
    monkeypatch.setattr(rctl, "MODE", "live")
    monkeypatch.setattr(rctl, "UR_HOME_METHOD", "movej")
    monkeypatch.setattr(ur_dashboard, "Dashboard", FakeDashboard)
    scripts = []
    monkeypatch.setattr(ur_script, "send", lambda host, sc: scripts.append(sc))
    FakeDashboard.sent = []
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "REQUESTED" and "joint feedback" in r["reason"]
    assert len(scripts) == 1 and scripts[0].startswith("def smartlab_home():\n  movej([-0.26180, -2.19911, 2.04256")
    assert "play" not in FakeDashboard.sent and not any(c.startswith("load") for c in FakeDashboard.sent)


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


def test_script_sender_refuses_anything_but_home_and_stop():
    from app.services import ur_script
    assert ur_script.allowed(ur_script.home_script(rctl.UR_HOME_Q_DEG)) and ur_script.allowed(ur_script.STOP_SCRIPT)
    for bad in ("set_digital_out(0, True)",
                "def smartlab_home():\n  movej([0,0,0,0,0,0])\n  movel(p[0,0,0,0,0,0])\nend\n"):
        with pytest.raises(ValueError):
            ur_script.send("192.0.2.1", bad)


def test_global_stop_needs_no_ownership_latches_and_blocks_home(client, staff, admin, ur):
    hs, ha = auth_headers(client, staff.email), auth_headers(client, admin.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=hs)          # staff owns the robot
    r = client.post(f"/api/robots/{ur.id}/control/stop", headers=ha, json={"command_id": "stop-0001"}).json()
    assert r["status"] == "DRY_RUN" and "stopj" in r["reason"]              # admin stops it anyway
    # Feedback from the test telemetry shows the arm still: STOPPED (never from the command reply); motion blocked.
    assert r["master"]["phase"] == "STOPPED" and r["master"]["stop_latched"] is True
    assert r["master"]["readiness"] == "BLOCKED"
    assert "NOT a safety-rated" in r["master"]["estop_note"]
    h = cmd(client, hs, ur.id, cid="cmd-0100").json()
    assert h["status"] == "REJECTED" and "STOP is latched" in h["reason"]   # STOP wins over Home
    again = client.post(f"/api/robots/{ur.id}/control/stop", headers=ha, json={"command_id": "stop-0001"}).json()
    assert again["status"] == "DUPLICATE"


def test_only_admin_recovers_and_nothing_restarts(client, db, staff, admin, ur):
    hs, ha = auth_headers(client, staff.email), auth_headers(client, admin.email)
    client.post(f"/api/robots/{ur.id}/control/stop", headers=hs, json={"command_id": "stop-0002"})
    assert client.post(f"/api/robots/{ur.id}/control/recover", headers=hs).status_code == 403
    r = client.post(f"/api/robots/{ur.id}/control/recover", headers=ha)
    assert r.status_code == 200 and "nothing was restarted" in r.json()["message"]
    assert r.json()["master"]["stop_latched"] is False
    assert db.query(AuditLog).filter_by(action="ROBOT_GLOBAL_STOP").count() == 1
    assert db.query(AuditLog).filter_by(action="ROBOT_STOP_RECOVERY").count() == 1


def test_home_reached_only_from_joint_feedback(monkeypatch):
    rctl._state.homing[7] = {"t": rctl.time.time(), "command_id": "x", "dry_run": False}
    far = [0, -90, 0, -90, 0, 0]
    assert rctl.master_state(7, far, True, True)["phase"] == "HOMING"
    near = [v + 0.2 for v in rctl.UR_HOME_Q_DEG]
    assert rctl.master_state(7, near, True, True)["phase"] == "HOMING"       # still moving
    assert rctl.master_state(7, near, False, True)["phase"] == "HOME_REACHED"
    rctl._state.homing[7] = {"t": rctl.time.time() - 999, "command_id": "y", "dry_run": False}
    assert rctl.master_state(7, far, False, True)["phase"] == "FAILED"
    rctl._state.homing[7] = {"t": rctl.time.time(), "command_id": "z", "dry_run": False}
    assert rctl.master_state(7, far, False, False)["phase"] == "FAILED"       # telemetry lost


def test_fresh_heartbeat_without_joints_is_blocked_not_ready():
    s = rctl.master_state(8, None, False, True)
    assert s["phase"] == "BLOCKED" and "no joint feedback" in s["detail"]


def test_live_default_home_runs_the_pendants_validated_program_not_a_joint_move(monkeypatch, client, staff, ur):
    from app.services import ur_dashboard, ur_script
    monkeypatch.setattr(rctl, "MODE", "live")
    monkeypatch.setattr(ur_dashboard, "Dashboard", FakeDashboard)
    scripts = []
    monkeypatch.setattr(ur_script, "send", lambda host, sc: scripts.append(sc))
    FakeDashboard.sent = []
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "REQUESTED" and "Loading program: /programs/home.urp" in r["reason"] and "joint feedback" in r["reason"]
    assert [c for c in FakeDashboard.sent if c.startswith("load") or c == "play"] == ["load home.urp", "play"]
    assert scripts == []                                             # no URScript joint move
    # a second Home while the first is in progress is refused (conflicting request)
    r2 = cmd(client, h, ur.id, cid="cmd-0201").json()
    assert r2["status"] == "REJECTED" and "already in progress" in r2["reason"]


def test_missing_home_program_is_refused_and_nothing_starts(monkeypatch, client, staff, ur):
    from app.services import ur_dashboard
    class NoProgram(FakeDashboard):
        def ask(self, c):
            FakeDashboard.sent.append(c)
            return "File not found: /programs/home.urp" if c.startswith("load ") else super().ask(c)
    monkeypatch.setattr(rctl, "MODE", "live")
    monkeypatch.setattr(ur_dashboard, "Dashboard", NoProgram)
    FakeDashboard.sent = []
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id).json()
    assert r["status"] == "REJECTED" and "File not found" in r["reason"] and "play" not in FakeDashboard.sent


GOOD = {"safety_mode": 1, "robot_mode": 7, "remote_control": True, "program_state": "STOPPED"}


def test_readiness_ready_for_physical_test_only_when_every_controller_check_passes():
    q = [-15.0, -126.0, 117.03, -80.0, 91.0, 95.27]
    s = rctl.master_state(21, q, False, True, GOOD)
    assert s["readiness"] == "READY_FOR_PHYSICAL_TEST"                  # dry run: all checks but sign-off
    assert [c["key"] for c in s["checks"] if not c["ok"]] == ["signoff"]
    for bad, key in (({**GOOD, "safety_mode": 3}, "safety"), ({**GOOD, "robot_mode": 5}, "power"),
                     ({**GOOD, "remote_control": False}, "remote"), ({**GOOD, "program_state": "PLAYING x.urp"}, "program"),
                     ({}, "safety")):
        s = rctl.master_state(21, q, False, True, bad)
        assert s["readiness"] == "BLOCKED" and key in [c["key"] for c in s["checks"] if not c["ok"]], (bad, key)
    s = rctl.master_state(21, None, False, True, GOOD)                    # no joints
    assert s["readiness"] == "BLOCKED" and s["phase"] == "BLOCKED"
    s = rctl.master_state(21, q, False, False, GOOD)                      # stale telemetry
    assert s["readiness"] == "BLOCKED"
    safety = next(c for c in rctl.master_state(21, q, False, True, {**GOOD, "safety_mode": 3})["checks"] if c["key"] == "safety")
    assert safety["detail"] == "PROTECTIVE STOP"


def test_stop_phase_is_requested_until_feedback_shows_the_arm_still():
    q = [0.0] * 6
    rctl._state.stops[22] = {"t": rctl.time.time(), "by": "Staff"}
    assert rctl.master_state(22, q, True, True, GOOD)["phase"] == "STOP_REQUESTED"       # still moving
    assert rctl.master_state(22, q, False, False, GOOD)["phase"] == "STOP_REQUESTED"     # no fresh feedback
    assert rctl.master_state(22, q, False, True, {**GOOD, "program_state": "PLAYING home.urp"})["phase"] == "STOP_REQUESTED"
    s = rctl.master_state(22, q, False, True, GOOD)
    assert s["phase"] == "STOPPED" and s["readiness"] == "BLOCKED"                       # latched blocks motion
    ok, _ = rctl.recover(22, moving=False)
    assert ok and rctl.master_state(22, q, False, True, GOOD)["phase"] in ("READY", "HOME_REACHED")
    assert 22 not in rctl._state.homing                                                  # nothing restarted


def test_fanuc_is_blocked_with_its_own_dependencies_and_no_ur_commands(client, staff, db, lab, device_headers):
    from tests.test_robots import tele
    tele(client, device_headers, uid="FANUC_TEST")
    f = db.query(Device).filter_by(device_uid="FANUC_TEST").one()
    f.component_state = {**(f.component_state or {}), "model": "FANUC ER-4iA"}
    db.commit()
    h = auth_headers(client, staff.email)
    st = client.get(f"/api/robots/{f.id}/control", headers=h).json()
    assert st["adapter"] == "FANUC" and st["master"] is None
    assert st["readiness"]["readiness"] == "BLOCKED" and len(st["readiness"]["dependencies"]) == 5
    assert any("R648" in d for d in st["readiness"]["dependencies"])
    checks = {c["key"]: c for c in st["readiness"]["checks"]}
    assert checks["identity"]["ok"] and "ER-4iA" in checks["identity"]["detail"]       # verified from SUMMARY.DG
    assert not checks["interface"]["ok"] and not checks["home_program"]["ok"] and not checks["stop"]["ok"]
    assert st["simulated"] is False and checks["source"]["ok"]


def test_a_simulated_robot_never_counts_as_physical_evidence(client, staff, db, lab, device_headers):
    from tests.test_robots import tele
    tele(client, device_headers, uid="UR5E_SIMX", source="SIMULATION")
    tele(client, device_headers, uid="FANUC_SIMX", source="SIMULATION")
    f = db.query(Device).filter_by(device_uid="FANUC_SIMX").one()
    f.component_state = {**(f.component_state or {}), "model": "FANUC ER-4iA"}
    db.commit()
    h = auth_headers(client, staff.email)
    for uid in ("UR5E_SIMX", "FANUC_SIMX"):
        d = db.query(Device).filter_by(device_uid=uid).one()
        st = client.get(f"/api/robots/{d.id}/control", headers=h).json()
        checks = {c["key"]: c for c in st["readiness"]["checks"]}
        assert st["simulated"] is True and not checks["source"]["ok"], uid
        assert st["readiness"]["readiness"] == "BLOCKED", uid
        if uid == "FANUC_SIMX":                       # the real controller's identity is not shown as the simulator's
            assert not checks["identity"]["ok"] and "ER-4iA" not in checks["identity"]["detail"]
    client.post(f"/api/robots/{f.id}/control/request", headers=h)
    r = cmd(client, h, f.id, cid="cmd-0301").json()
    assert r["status"] == "UNAVAILABLE"                                   # no FANUC home command exists
    stop = client.post(f"/api/robots/{f.id}/control/stop", headers=h, json={"command_id": "stop-0301"}).json()
    assert stop["status"] == "UNAVAILABLE"                                # honest: no stop interface yet



def test_a_latched_stop_survives_a_backend_restart_until_an_admin_recovers(client, staff, admin, db, ur):
    """2026-10-18: the latch is rebuilt from the audit log at start-up - a restart is not a recovery."""
    from app.api.routes.robots import restore_stop_latches
    h = auth_headers(client, staff.email)
    client.post(f"/api/robots/{ur.id}/control/stop", headers=h, json={"command_id": "stop-restart-1"})
    rctl._state.stops.clear()                                   # what a restart does to memory
    rctl._state.homing.clear()
    assert restore_stop_latches(db) == [ur.id]
    st = client.get(f"/api/robots/{ur.id}/control", headers=h).json()
    assert st["master"]["stop_latched"] is True and st["master"]["stop"]["restored"] is True
    client.post(f"/api/robots/{ur.id}/control/request", headers=h)
    r = cmd(client, h, ur.id, cid="cmd-after-restart").json()
    assert r["status"] == "REJECTED" and "STOP" in r["reason"]   # no Home while latched
    ra = client.post(f"/api/robots/{ur.id}/control/recover", headers=auth_headers(client, admin.email))
    assert ra.status_code == 200
    rctl._state.stops.clear()
    assert restore_stop_latches(db) == []                       # recovered: not latched after a restart
