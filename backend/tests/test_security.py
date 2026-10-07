"""
Security camera, backend side (tools/security_vision is replaced by calls).

Tested: the service registers itself and gets its zones and who is inside
per the door; state reports reach the monitor tile; an event keeps its
snapshot, raises one alert (not one per repeat) and notifies staff;
acknowledging closes the alert; zones are staff-only and moving a box makes
the camera relearn it; the live frame comes through the portal.
"""
import json
from datetime import datetime, timezone

import httpx

from app.api.routes import security
from app.models import (AccessSession, Alert, AuthMethod, Device, DeviceType, Notification,
                        SecurityEvent)
from tests.conftest import auth_headers

JPEG = b"\xff\xd8\xff\xe0" + b"1" * 200


def _register(client, device_headers, lab):
    r = client.get("/api/security/config", headers=device_headers,
                   params={"device_uid": "SECCAM_LAB01", "lab_id": lab.code, "port": 5100})
    assert r.status_code == 200, r.text
    return r.json()


def _event(client, device_headers, kind="EQUIPMENT_CHANGED", zone_id=None, snapshot=True):
    meta = {"device_uid": "SECCAM_LAB01", "kind": kind, "detail": "test", "people_seen": 1,
            "people_inside": 0, "zone_id": zone_id}
    files = {"snapshot": ("s.jpg", JPEG, "image/jpeg")} if snapshot else None
    return client.post("/api/security/events", headers=device_headers,
                       data={"meta": json.dumps(meta)}, files=files)


def test_service_registers_and_sees_occupants(client, db, lab, alice, device_headers):
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, entry_method=AuthMethod.QR))
    db.commit()
    cfg = _register(client, device_headers, lab)
    d = db.query(Device).filter_by(device_uid="SECCAM_LAB01").one()
    assert d.device_type == DeviceType.SECURITY_CAMERA and cfg["device_id"] == d.id
    assert cfg["zones"] == [] and cfg["door"] is None
    assert [o["name"] for o in cfg["occupants"]] == ["Alice"]


def test_zones_staff_only_and_relearn(client, db, lab, staff, alice, device_headers):
    cid = _register(client, device_headers, lab)["device_id"]
    box = {"name": "PC-01", "x": 0.1, "y": 0.2, "w": 0.2, "h": 0.2}
    assert client.post(f"/api/security/cameras/{cid}/zones", headers=auth_headers(client, alice.email),
                       json=box).status_code == 403
    h = auth_headers(client, staff.email)
    z = client.post(f"/api/security/cameras/{cid}/zones", headers=h, json=box).json()
    assert z["ref_version"] == 1
    assert client.post(f"/api/security/cameras/{cid}/zones", headers=h,
                       json={**box, "x": 0.9}).status_code == 422          # outside the picture
    moved = client.put(f"/api/security/cameras/{cid}/zones/{z['id']}", headers=h,
                       json={**box, "x": 0.15}).json()
    assert moved["ref_version"] == 2
    same = client.put(f"/api/security/cameras/{cid}/zones/{z['id']}", headers=h,
                      json={**box, "x": 0.15, "name": "PC-01 (left)"}).json()
    assert same["ref_version"] == 2                     # renaming does not reset the reference
    assert client.post(f"/api/security/cameras/{cid}/zones/{z['id']}/accept", headers=h).json()["ref_version"] == 3
    door = {"name": "Door", "kind": "DOOR", "x": 0.7, "y": 0.1, "w": 0.2, "h": 0.6}
    assert client.post(f"/api/security/cameras/{cid}/zones", headers=h, json=door).status_code == 201
    assert client.post(f"/api/security/cameras/{cid}/zones", headers=h, json=door).status_code == 409
    cfg = _register(client, device_headers, lab)
    assert [x["name"] for x in cfg["zones"]] == ["PC-01 (left)"] and cfg["door"]["name"] == "Door"


def test_event_snapshot_alert_once_and_ack(client, db, lab, staff, device_headers):
    cid = _register(client, device_headers, lab)["device_id"]
    h = auth_headers(client, staff.email)
    z = client.post(f"/api/security/cameras/{cid}/zones", headers=h,
                    json={"name": "UR5e", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}).json()
    assert _event(client, device_headers, zone_id=z["id"]).status_code == 201
    assert _event(client, device_headers, zone_id=z["id"]).status_code == 201
    alerts = db.query(Alert).filter(Alert.dedupe_key.like("sec:%")).all()
    assert len(alerts) == 1 and "UR5e" in alerts[0].title
    assert db.query(Notification).filter_by(user_id=staff.id, kind="SECURITY_CAMERA").count() == 1
    evs = client.get("/api/security/events", headers=h).json()
    assert len(evs) == 2 and evs[0]["zone_name"] == "UR5e" and evs[0]["has_snapshot"]
    snap = client.get(f"/api/security/events/{evs[0]['id']}/snapshot.jpg", headers=h)
    assert snap.status_code == 200 and snap.content == JPEG
    client.post(f"/api/security/events/{evs[0]['id']}/ack", headers=h)
    db.refresh(alerts[0])
    assert alerts[0].is_resolved is False               # one still open
    client.post(f"/api/security/events/{evs[1]['id']}/ack", headers=h)
    db.refresh(alerts[0])
    assert alerts[0].is_resolved is True


def test_unknown_kind_rejected(client, db, lab, device_headers):
    _register(client, device_headers, lab)
    assert _event(client, device_headers, kind="LOOKS_SUSPICIOUS", snapshot=False).status_code == 422


def test_state_reaches_monitor_tile(client, db, lab, staff, device_headers):
    _register(client, device_headers, lab)
    r = client.post("/api/security/state", headers=device_headers, json={
        "device_uid": "SECCAM_LAB01", "fps": 3.2, "people": 2, "unknown": 1,
        "named": [{"label": "USER1", "name": "Alice", "role": "STUDENT"}],
        "zones": [{"id": 1, "name": "PC-01", "status": "OK", "score": 0.1}]})
    assert r.status_code == 200
    tile = next(t for t in client.get("/api/monitor", headers=auth_headers(client, staff.email)).json()["labs"]
                if t["code"] == lab.code)
    cam = tile["security_camera"]
    assert cam["online"] is True and cam["people"] == 2 and cam["unknown"] == 1
    assert cam["named"][0]["name"] == "Alice"


def test_frame_comes_through_the_portal(client, db, lab, staff, alice, device_headers, monkeypatch):
    cid = _register(client, device_headers, lab)["device_id"]
    h = auth_headers(client, staff.email)
    calls = []

    class R:
        status_code, content = 200, JPEG

    def get(url, headers=None, timeout=None):
        calls.append((url, headers))
        return R()

    monkeypatch.setattr(security.httpx, "get", get)
    r = client.get(f"/api/security/cameras/{cid}/frame.jpg", headers=h)
    assert r.status_code == 200 and r.content == JPEG
    assert calls[0][0].endswith(":5100/frame.jpg") and "X-Device-Key" in calls[0][1]

    def down(url, headers=None, timeout=None):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(security.httpx, "get", down)
    assert client.get(f"/api/security/cameras/{cid}/frame.jpg", headers=h).status_code == 503
    assert client.get(f"/api/security/cameras/{cid}/frame.jpg",
                      headers=auth_headers(client, alice.email)).status_code == 403


def test_state_pushed_only_when_it_changes(client, db, lab, device_headers, monkeypatch):
    """The service reports every 2 s; every staff page refetches on a push, so
    only a real change (people, names, zone states, picture) is pushed - and
    as its own message type, not a general 'staff' refresh."""
    from app.ws.manager import manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    _register(client, device_headers, lab)

    def report(people, fps, score=0.1, status="OK"):
        r = client.post("/api/security/state", headers=device_headers, json={
            "device_uid": "SECCAM_LAB01", "fps": fps, "people": people, "unknown": people,
            "named": [], "zones": [{"id": 1, "name": "PC-01", "status": status, "score": score}]})
        assert r.status_code == 200

    report(1, 3.0)
    report(1, 2.7, score=0.2)            # only fps / score moved: nothing to show
    report(1, 3.1, score=0.15)
    assert [m["type"] for m in sent] == ["security_state"]
    report(2, 3.0)                       # someone else came into view
    report(2, 3.0, status="CHANGED")     # a box changed state
    assert [m["type"] for m in sent] == ["security_state"] * 3
    assert all(m["type"] != "staff" for m in sent)


def test_config_lists_known_people_for_face_names(client, db, lab, alice, device_headers):
    """The camera may name someone by face before they enter: it needs who
    USERx is. Only active people with a door identity are listed."""
    alice.auth_subject = "USER9"
    db.commit()
    known = {k["auth_subject"]: k for k in _register(client, device_headers, lab)["known"]}
    assert known["USER9"]["name"] == alice.full_name and known["USER9"]["role"] == alice.role.value
    alice.is_active = False
    db.commit()
    assert "USER9" not in {k["auth_subject"] for k in _register(client, device_headers, lab)["known"]}


def test_equipment_suggestions_skip_items_already_boxed(client, db, lab, staff, device_headers, monkeypatch):
    """YOLO proposes a box per monitor/laptop; one already covered by a saved box is not proposed again."""
    cid = _register(client, device_headers, lab)["device_id"]
    h = auth_headers(client, staff.email)
    assert client.post(f"/api/security/cameras/{cid}/zones", headers=h, json={
        "name": "PC-01", "x": 0.10, "y": 0.10, "w": 0.20, "h": 0.20}).status_code == 201

    class R:
        status_code = 200

        @staticmethod
        def json():
            return {"items": [{"kind": "Monitor", "score": 0.9, "x": 0.11, "y": 0.11, "w": 0.19, "h": 0.19},
                              {"kind": "Monitor", "score": 0.8, "x": 0.60, "y": 0.20, "w": 0.15, "h": 0.15},
                              {"kind": "Laptop", "score": 0.7, "x": 0.40, "y": 0.60, "w": 0.10, "h": 0.10}]}

    monkeypatch.setattr(security.httpx, "get", lambda url, headers=None, timeout=None: R())
    r = client.get(f"/api/security/cameras/{cid}/suggestions", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()
    assert [i["kind"] for i in items] == ["Monitor", "Laptop"]        # the first is PC-01 already
    assert items[0]["name"] == "PC-02" and items[1]["name"] == "Laptop-01"
    assert client.get(f"/api/security/cameras/{cid}/suggestions",
                      headers=auth_headers(client, "alice@test.edu") if False else {}).status_code == 401


def test_recording_admin_only_audited_and_played_through_a_signed_link(client, db, lab, admin, staff,
                                                                         device_headers, monkeypatch):
    """Record / Stop: administrators only, each switch in the audit log; a
    recording plays through a short signed link (Range passed on), and a
    forged / foreign token or a path trick gets nothing."""
    from app.models import AuditLog
    cid = _register(client, device_headers, lab)["device_id"]
    name = "SECCAM_LAB01_2026-10-07_01-15-39.mp4"
    sent = []

    class J:
        def __init__(self, code, body):
            self.status_code, self._b = code, body
            self.headers = {"content-type": "application/json"}

        def json(self):
            return self._b

    def request(method, url, headers=None, timeout=None, json=None):
        sent.append((method, url.split(":5100")[1], json))
        if url.endswith("/record/start"):
            return J(200, {"ok": True, "file": name})
        if url.endswith("/record/stop"):
            return J(409, {"ok": False, "error": "not recording"})
        return J(200, {"items": [{"file": name, "size_bytes": 938918}], "free_gb": 129.4})

    monkeypatch.setattr(security.httpx, "request", request)
    h_admin, h_staff = auth_headers(client, admin.email), auth_headers(client, staff.email)
    assert client.post(f"/api/security/cameras/{cid}/recording/start", headers=h_staff).status_code == 403
    r = client.post(f"/api/security/cameras/{cid}/recording/start", headers=h_admin)
    assert r.status_code == 200 and r.json()["file"] == name
    assert sent[-1] == ("POST", "/record/start", {"by": admin.full_name})
    assert db.query(AuditLog).filter_by(action="SECURITY_RECORDING_START", actor_user_id=admin.id).count() == 1
    r = client.post(f"/api/security/cameras/{cid}/recording/stop", headers=h_admin)
    assert r.status_code == 409 and "not recording" in r.text
    assert client.get(f"/api/security/cameras/{cid}/recordings", headers=h_admin).json()["items"][0]["file"] == name

    # Playback: signed link, Range passed through, 206 back.
    assert client.post(f"/api/security/cameras/{cid}/recordings/..%2Fsecret.mp4/link",
                       headers=h_admin).status_code == 404
    url = client.post(f"/api/security/cameras/{cid}/recordings/{name}/link", headers=h_admin).json()["url"]
    seen = {}

    class Streamed:
        status_code = 206
        headers = {"content-type": "video/mp4", "content-range": "bytes 0-3/938918", "content-length": "4",
                   "accept-ranges": "bytes"}

        def iter_bytes(self, n):
            yield b"\x00\x00\x00\x18"

        def close(self):
            pass

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def build_request(self, method, url, headers=None):
            seen["url"], seen["headers"] = url, headers
            return None

        def send(self, req, stream=False):
            return Streamed()

        def close(self):
            pass

    monkeypatch.setattr(security.httpx, "Client", FakeClient)
    r = client.get(url, headers={"Range": "bytes=0-3"})            # no sign-in header: the link is the permission
    assert r.status_code == 206 and r.content == b"\x00\x00\x00\x18"
    assert r.headers["content-range"] == "bytes 0-3/938918"
    assert seen["url"].endswith(f"/recordings/{name}") and seen["headers"]["Range"] == "bytes=0-3"
    assert "attachment" in client.get(url + "&download=true").headers.get("content-disposition", "")
    assert client.get("/api/security/recordings/play?t=forged.token.value").status_code == 401
    from app.core.security import create_access_token
    login_token = create_access_token(admin.id, admin.role.value)      # a sign-in token is not a recording link
    assert client.get(f"/api/security/recordings/play?t={login_token}").status_code == 401


def test_camera_realigns_its_boxes_after_the_view_moved(client, db, lab, staff, device_headers):
    """The camera reports where each box went after its view moved: boxes move
    and relearn (ref_version up), boxes of another camera are untouched, lost
    boxes stay, the change is in the audit log (no person - the camera)."""
    from app.models import AuditLog, SecurityZone
    cid = _register(client, device_headers, lab)["device_id"]
    h = auth_headers(client, staff.email)
    z = client.post(f"/api/security/cameras/{cid}/zones", headers=h,
                    json={"name": "PC-01", "kind": "EQUIPMENT", "x": 0.35, "y": 0.26, "w": 0.13, "h": 0.2}).json()
    z2 = client.post(f"/api/security/cameras/{cid}/zones", headers=h,
                     json={"name": "PC-02", "kind": "EQUIPMENT", "x": 0.02, "y": 0.3, "w": 0.1, "h": 0.1}).json()
    r = client.post("/api/security/zones/realign", headers=device_headers, json={
        "device_uid": "SECCAM_LAB01", "boxes": [{"id": z["id"], "x": 0.39, "y": 0.26, "w": 0.13, "h": 0.2},
                                                {"id": 99999, "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}],
        "lost": [z2["id"]], "inliers": 1779, "shift": 0.039})
    assert r.status_code == 200 and r.json() == {"moved": 1, "lost": [z2["id"]]}
    db.expire_all()
    moved, left = db.get(SecurityZone, z["id"]), db.get(SecurityZone, z2["id"])
    assert (moved.x, moved.ref_version) == (0.39, 2) and (left.x, left.ref_version) == (0.02, 1)
    log = db.query(AuditLog).filter_by(action="SECURITY_ZONES_REALIGNED").one()
    assert log.actor_user_id is None and log.detail["moved"][0]["name"] == "PC-01"
    assert client.post("/api/security/zones/realign", headers=device_headers,
                       json={"device_uid": "NOT_A_CAMERA", "boxes": []}).status_code in (403, 404)
