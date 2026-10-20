"""Reliability centre (2026-10-18): dependency graph + impact + sandboxed what-if, investigation, action
policy, request timing + regressions + objectives, configuration drift (+ accepted deviations, never
secret values), operator briefing, API access rules. Deterministic fixtures; nothing physical."""
import time
from datetime import datetime, timedelta, timezone

from app.models import Alert, AlertSeverity, AuditLog, Device, DeviceType
from app.services import dependency_graph as dg
from app.services import drift, perfmon, policy
from tests.conftest import auth_headers

SERVICES = [
    {"key": "database", "name": "PostgreSQL", "state": "ONLINE"},
    {"key": "backend", "name": "Backend API", "state": "ONLINE"},
    {"key": "face", "name": "Face server", "state": "ONLINE"},
    {"key": "ai", "name": "Ollama", "state": "OFFLINE", "detail": "ConnectError"},
    {"key": "knowledge", "name": "Knowledge", "state": "ONLINE"},
    {"key": "door:1", "group": "door", "name": "Master", "device_uid": "MASTER_LAB01", "device_id": 1, "state": "OFFLINE"},
    {"key": "environment:2", "group": "environment", "name": "Bin", "device_uid": "BIN_NODE_1", "device_id": 2, "state": "OFFLINE"},
    {"key": "security_camera:3", "group": "security_camera", "name": "Cam 2", "device_uid": "SECCAM_LAB02", "device_id": 3,
     "state": "ONLINE"},
    {"key": "robot:4", "group": "robot", "name": "UR5e", "device_uid": "UR5E_01", "device_id": 4, "state": "DEGRADED"},
    {"key": "robot:5", "group": "robot", "name": "UR5e sim", "device_uid": "UR5E_SIM", "device_id": 5, "state": "SIMULATION"},
]


def test_graph_states_edges_and_evidence():
    g = dg.build(SERVICES)
    by = {n["key"]: n for n in g["nodes"]}
    assert by["ai"]["state"] == "OFFLINE" and by["ai"]["evidence"] == "live"
    assert by["router"]["state"] == "HEALTHY"                       # camera 2 reports through it
    assert {"node": "router", "inferred": False} in by["door:1"]["needs"]
    assert by["controller:UR5E_01"]["state"] == "OFFLINE"           # collector runs, no joint data
    assert by["robot:5"]["evidence"] == "simulated" and "DRY RUN" in by["robot:4"]["control"]
    assert "knowledge" in by["ai"]["needed_by"]


def test_impact_and_whatif_change_nothing():
    g = dg.build(SERVICES)
    hit = dg.impact(g, "router")
    assert "door:1" in hit and "environment:2" in hit and "security_camera:3" in hit
    w = dg.whatif(g, "router")
    assert w["kind"].startswith("SIMULATED") and w["recovery_order"][0] == "router"
    assert any("Master offline" == a for a in w["expected_alerts"])
    assert dg.whatif(g, "nope")["error"]
    assert dg.build(SERVICES)["nodes"] == g["nodes"]                # the live model is unchanged


def test_likely_roots_prefers_the_failing_dependency():
    g = dg.build(SERVICES)
    roots = {r["node"] for r in dg.likely_roots(g)}
    assert "ai" in roots and "controller:UR5E_01" in roots
    assert "knowledge" not in roots


def test_policy_results():
    assert policy.evaluate("robot.home")["result"] == policy.DRY
    assert policy.evaluate("robot.home", {"robot_control": "live"})["result"] == policy.APPROVAL
    assert policy.evaluate("robot.home", {"automatic": True})["result"] == policy.PROHIBITED
    assert policy.evaluate("door.open")["result"] == policy.PROHIBITED
    assert policy.evaluate("health.recheck", {"automatic": True})["result"] == policy.ALLOWED
    assert policy.evaluate("firmware.flash", {"automatic": True})["result"] == policy.PROHIBITED
    assert policy.evaluate("launch.rockets")["result"] == policy.UNKNOWN
    assert "not a safety-rated" in policy.evaluate("robot.stop")["reason"].lower() or "NOT a safety-rated" in policy.evaluate("robot.stop")["reason"]


def test_perf_summary_regression_with_minimum_samples_and_cooldown():
    perfmon.reset()
    now = time.time()
    for i in range(40):                                              # baseline hour: ~20 ms
        perfmon.record("GET /api/x", 20 + (i % 3), 200, t=now - 1200 + i)
    for i in range(10):                                              # too few current samples: nothing
        perfmon.record("GET /api/x", 200, 200, t=now - 60 + i)
    assert perfmon.regressions(now) == []
    for i in range(20):
        perfmon.record("GET /api/x", 200, 200, t=now - 50 + i)
    r = perfmon.regressions(now)
    assert len(r) == 1 and r[0]["current_p95"] >= 150 and r[0]["new"]
    assert perfmon.regressions(now)[0]["new"] is False                # cooldown: not a new alert
    s = perfmon.summary()
    assert s["routes"][0]["route"] == "GET /api/x" and s["routes"][0]["n"] == 70
    obj = {o["key"]: o for o in perfmon.objectives()}
    assert obj["api_success"]["measured"] == 1.0 and obj["api_p95_ms"]["samples"] == 70
    perfmon.reset()


def test_timing_middleware_records_routes_by_template(client, staff):
    perfmon.reset()
    h = auth_headers(client, staff.email)
    client.get("/api/robots", headers=h)
    client.get("/api/incidents/999999", headers=h)                   # 404 still timed, by template
    routes = {r["route"] for r in perfmon.summary()["routes"]}
    assert "GET /api/robots" in routes and "GET /api/incidents/{incident_id}" in routes


def test_drift_never_shows_secrets_and_accepted_deviation_stays_visible(db, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "OLLAMA_NUM_THREAD", 8)
    r = drift.check(db)
    ids = {f["id"]: f for f in r["findings"]}
    assert ids["setting:OLLAMA_NUM_THREAD"]["actual"] == 8 and ids["setting:OLLAMA_NUM_THREAD"]["class"] == drift.APPROVAL
    blob = str(r)
    assert settings.SECRET_KEY not in blob and settings.DEVICE_API_KEY not in blob
    drift.accept(db, "setting:OLLAMA_NUM_THREAD", "testing more threads on the bench", "Admin", 1)
    db.commit()
    r2 = drift.check(db)
    f = next(x for x in r2["findings"] if x["id"] == "setting:OLLAMA_NUM_THREAD")
    assert f["accepted"]["reason"].startswith("testing") and f["expected"] == 4     # baseline unchanged
    assert drift.history(db)


def test_drift_reports_firmware_differences(db, lab):
    db.add(Device(device_uid="BIN_NODE_1", name="Bin", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                  firmware_version="bin-0.1"))
    db.commit()
    f = next(x for x in drift.check(db)["findings"] if x["id"] == "firmware:BIN_NODE_1")
    assert f["expected"] == "bin-0.3" and f["actual"] == "bin-0.1" and "no automatic flashing" in f["remediation"]


def test_investigation_ranks_a_shared_outage_when_devices_fail_together(client, db, lab, staff):
    now = datetime.now(timezone.utc)
    devs = []
    for i, uid in enumerate(("MASTER_X", "BIN_X", "REUSE_X")):
        d = Device(device_uid=uid, name=uid, device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                   last_seen_at=now - timedelta(hours=1))
        db.add(d)
        db.flush()
        devs.append(d)
        db.add(Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING, title=f"{uid} offline",
                     created_at=now - timedelta(minutes=30, seconds=i)))
    db.commit()
    a = db.query(Alert).filter_by(title="MASTER_X offline").one()
    h = auth_headers(client, staff.email)
    r = client.get(f"/api/reliability/incidents/{a.id}/investigate", headers=h).json()
    top = r["hypotheses"][0]
    assert top["id"] in ("shared_upstream", "portal_gap") and "2 other device(s)" in " ".join(
        next(x for x in r["hypotheses"] if x["id"] == "shared_upstream")["supporting"])
    own = next(x for x in r["hypotheses"] if x["id"] == "device_itself")
    assert own["contradicting"] and "correlation, not proof" in r["statement"]
    assert all("policy" in s for s in r["suggestions"])


def test_api_access_briefing_and_whatif(client, db, staff, alice, admin):
    h = auth_headers(client, staff.email)
    for path in ("/api/reliability/graph", "/api/reliability/drift", "/api/reliability/performance",
                 "/api/reliability/policy", "/api/reliability/capacity", "/api/reliability/backups",
                 "/api/reliability/briefing", "/api/reliability/alert-quality"):
        assert client.get(path, headers=auth_headers(client, alice.email)).status_code == 403, path
        assert client.get(path, headers=h).status_code == 200, path
    b = client.get("/api/reliability/briefing", headers=h).json()
    assert any(i["kind"] == "physical" for i in b["items"])
    again = client.get("/api/reliability/briefing", headers=h).json()
    assert all(i["repeated"] for i in again["items"])                  # unchanged items are marked, not hidden
    w = client.post("/api/reliability/graph/whatif", headers=h, json={"node": "database"}).json()
    assert w["kind"].startswith("SIMULATED") and any(x["node"] == "backend" for x in w["affected"])
    assert client.post("/api/reliability/drift/accept", headers=h,
                       json={"id": "x", "reason": "because"}).status_code == 403          # admin only
    r = client.post("/api/reliability/policy/evaluate", headers=h, json={"action": "door.open"}).json()
    assert r["result"] == "PROHIBITED" and db.query(AuditLog).filter_by(action="POLICY_EVALUATED").count() == 1
    assert client.post("/api/reliability/performance/baseline", headers=auth_headers(client, admin.email)).status_code == 200



def test_global_search_is_staff_only_bounded_and_links(client, db, lab, staff, alice):
    a = Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="Camera 2 offline")
    db.add(a)
    db.add(Device(device_uid="SECCAM_LAB02", name="Security camera 2", device_type=DeviceType.SECURITY_CAMERA, lab_id=lab.id))
    db.commit()
    assert client.get("/api/search?q=camera", headers=auth_headers(client, alice.email)).status_code == 403
    h = auth_headers(client, staff.email)
    assert client.get("/api/search?q=c", headers=h).status_code == 422                 # at least 2 characters
    r = client.get("/api/search?q=camera", headers=h).json()["results"]
    types = {x["type"] for x in r}
    assert {"incident", "device"} <= types and len(r) <= 24
    assert any(x["to"] == f"/admin/incidents?open={a.id}" for x in r)
    byid = client.get(f"/api/search?q=INC-{a.id:06d}", headers=h).json()["results"]
    assert byid[0]["to"] == f"/admin/incidents?open={a.id}"


def test_search_lists_the_device_before_its_old_incidents(client, db, lab, staff):
    # 2026-10-18: "UR5" put a resolved "UR5e offline" incident above the robot itself.
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="UR5e (physical) offline", is_resolved=True))
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="UR5e (physical) offline again"))
    db.add(Device(device_uid="UR5E_01", name="UR5e (physical)", device_type=DeviceType.ROBOT, lab_id=lab.id))
    db.add(Device(device_uid="PC_LAB01_12", name="PC-12", device_type=DeviceType.PC, lab_id=lab.id))
    db.commit()
    h = auth_headers(client, staff.email)
    r = client.get("/api/search?q=UR5", headers=h).json()["results"]
    assert r[0]["type"] == "device"
    inc = [x for x in r if x["type"] == "incident"]
    assert inc[0]["subtitle"] != "resolved" and inc[-1]["subtitle"] == "resolved"
    pc = client.get("/api/search?q=PC-12", headers=h).json()["results"][0]
    assert pc["to"] == "/admin/equipment?tab=noncons"
