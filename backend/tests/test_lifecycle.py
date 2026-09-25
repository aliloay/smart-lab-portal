"""
Asset lifecycle, access-session detail, the operational notifications, and
the session/heartbeat edges added for the final pass.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.models import (AccessSession, Asset, AssetStatus, Device, DeviceType,
                        Notification)
from app.services.booking import create_booking
from tests.conftest import auth_headers


@pytest.fixture
def arm(db, lab) -> Asset:
    a = Asset(asset_tag="UR5E-ROBOT-01", name="UR5e Robot", category="Manipulator",
              lab_id=lab.id, status=AssetStatus.AVAILABLE, serial_number="20235500123")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def H(client, u):
    return auth_headers(client, u.email)


# ===========================================================================
# Asset lifecycle
# ===========================================================================
def test_checkout_records_holder_visible_to_staff_only(client, db, alice, bob,
                                                      staff, arm):
    assert client.post(f"/api/assets/{arm.id}/checkout",
                       headers=H(client, alice)).status_code == 200
    as_staff = client.get(f"/api/assets/{arm.id}", headers=H(client, staff)).json()
    assert as_staff["asset"]["holder_name"] == "Alice"
    assert as_staff["asset"]["checked_out_at"] is not None
    as_bob = client.get(f"/api/assets/{arm.id}", headers=H(client, bob)).json()
    assert as_bob["asset"]["holder_name"] is None
    assert as_bob["asset"]["holder_id"] is None


def test_only_the_borrower_or_staff_can_return(client, db, alice, bob, staff, arm):
    client.post(f"/api/assets/{arm.id}/checkout", headers=H(client, alice))
    assert client.post(f"/api/assets/{arm.id}/return",
                       headers=H(client, bob)).status_code == 403
    r = client.post(f"/api/assets/{arm.id}/return", headers=H(client, staff))
    assert r.status_code == 200
    db.refresh(arm)
    assert arm.holder_id is None and arm.status == AssetStatus.AVAILABLE


def test_inspection_sets_dates_and_is_staff_only(client, db, alice, staff, arm):
    nxt = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    assert client.post(f"/api/assets/{arm.id}/inspect", headers=H(client, alice),
                       json={"note": "looks fine"}).status_code == 403
    r = client.post(f"/api/assets/{arm.id}/inspect", headers=H(client, staff),
                    json={"note": "Joint torque check passed",
                          "next_maintenance_at": nxt})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_inspected_at"] is not None
    assert body["next_maintenance_at"] is not None
    assert body["maintenance_due"] is False


def test_next_maintenance_must_be_in_the_future(client, staff, arm):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = client.post(f"/api/assets/{arm.id}/inspect", headers=H(client, staff),
                    json={"next_maintenance_at": past})
    assert r.status_code == 422


def test_overdue_maintenance_is_flagged_and_filterable(client, db, staff, arm, lab):
    other = Asset(asset_tag="PSU-01", name="Bench supply", lab_id=lab.id)
    db.add(other)
    arm.next_maintenance_at = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()
    rows = client.get("/api/assets?due=true", headers=H(client, staff)).json()
    assert [r["asset_tag"] for r in rows] == ["UR5E-ROBOT-01"]
    assert rows[0]["maintenance_due"] is True


def test_asset_details_are_editable_by_staff_only(client, alice, staff, arm):
    body = {"serial_number": "SN-NEW", "name": "UR5e Robot Arm"}
    assert client.patch(f"/api/assets/{arm.id}", headers=H(client, alice),
                        json=body).status_code == 403
    r = client.patch(f"/api/assets/{arm.id}", headers=H(client, staff), json=body)
    assert r.json()["serial_number"] == "SN-NEW"
    assert r.json()["name"] == "UR5e Robot Arm"


def test_lifecycle_timeline_combines_issues_inspections_and_loans(
        client, db, alice, staff, arm, lab):
    ah, sh = H(client, alice), H(client, staff)
    iid = client.post("/api/issues", headers=ah, json={
        "lab_id": lab.id, "asset_id": arm.id, "category": "MALFUNCTION",
        "severity": "HIGH", "title": "Joint 3 noise",
        "description": "Grinding noise from joint 3 at speed."}).json()["id"]
    client.post(f"/api/issues/{iid}/resolve", headers=sh,
                json={"resolution_notes": "Gearbox re-greased."})
    client.post(f"/api/assets/{arm.id}/inspect", headers=sh, json={"note": "OK"})
    client.post(f"/api/assets/{arm.id}/checkout", headers=ah)

    staff_view = client.get(f"/api/assets/{arm.id}", headers=sh).json()["lifecycle"]
    kinds = [e["kind"] for e in staff_view]
    for k in ("ISSUE_REPORTED", "ISSUE_RESOLVED", "INSPECTION", "CHECKOUT"):
        assert k in kinds
    times = [e["at"] for e in staff_view]
    assert times == sorted(times, reverse=True)          # newest first

    # A student sees the item's history, not who borrowed it.
    student_view = client.get(f"/api/assets/{arm.id}", headers=ah).json()["lifecycle"]
    assert "CHECKOUT" not in [e["kind"] for e in student_view]
    assert all(e["actor"] is None for e in student_view)


# ===========================================================================
# Access session detail
# ===========================================================================
def grant(client, device_headers, lab, device, booking_id=None, method="QR",
          subject="USER1"):
    body = {"lab_id": lab.code, "device_uid": device.device_uid,
            "event_type": "ACCESS_GRANTED", "auth_subject": subject, "method": method}
    if booking_id:
        body["booking_id"] = booking_id
    assert client.post("/api/access/grant", headers=device_headers,
                       json=body).status_code == 200


def test_session_detail_for_owner_and_staff_only(client, db, alice, bob, staff,
                                                  lab, device, device_headers,
                                                  now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    client.post("/api/access/events", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "FACE_ACCEPTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "FACE"})
    grant(client, device_headers, lab, device, b.id)
    sid = db.query(AccessSession).one().id

    r = client.get(f"/api/access-sessions/{sid}", headers=H(client, alice))
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["summary"]["result"] == "GRANTED"
    assert t["summary"]["second_factor"] == "FACE"
    assert t["booking"]["id"] == b.id
    assert t["user"]["auth_subject"] == "USER1"
    assert "ACCESS_GRANTED" in [e["event_type"] for e in t["events"]]

    assert client.get(f"/api/access-sessions/{sid}",
                      headers=H(client, bob)).status_code == 404
    assert client.get(f"/api/access-sessions/{sid}",
                      headers=H(client, staff)).status_code == 200


def test_rfid_entry_without_booking_is_traceable(client, db, alice, staff, lab,
                                                 device, device_headers):
    grant(client, device_headers, lab, device, None, method="RFID")
    sid = db.query(AccessSession).one().id
    t = client.get(f"/api/access-sessions/{sid}", headers=H(client, staff)).json()
    assert t["booking"] is None
    assert t["session"]["entry_method"] == "RFID"
    assert t["summary"]["entry_at"] is not None


def test_event_links_to_its_session(client, db, alice, bob, lab, device,
                                    device_headers):
    grant(client, device_headers, lab, device, None, method="RFID")
    s = db.query(AccessSession).one()
    q = {"user_id": alice.id, "lab_id": lab.id,
         "at": datetime.now(timezone.utc).isoformat()}
    r = client.get("/api/access-sessions/lookup", params=q, headers=H(client, alice))
    assert r.json() == {"session_id": s.id}
    # Nobody else can probe someone's sessions.
    assert client.get("/api/access-sessions/lookup", params=q,
                      headers=H(client, bob)).status_code == 404


# ===========================================================================
# Notifications added in the final pass
# ===========================================================================
def test_pending_booking_notifies_staff(client, db, alice, staff, lab, now, hour,
                                        monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "BOOKING_AUTO_APPROVE", False)
    create_booking(db, alice, lab, now + hour, now + 2 * hour, "x")
    n = db.query(Notification).filter_by(user_id=staff.id, kind="BOOKING_PENDING").one()
    assert n.link == "/admin/bookings"


def test_security_event_notifies_staff_once_per_burst(client, db, staff, admin,
                                                      lab, device, device_headers):
    for _ in range(4):   # someone tries an unknown card four times
        client.post("/api/access/deny", headers=device_headers, json={
            "lab_id": lab.code, "device_uid": device.device_uid,
            "event_type": "ACCESS_DENIED", "method": "RFID",
            "reason": "UNKNOWN_CREDENTIAL"})
    for u in (staff, admin):
        assert db.query(Notification).filter_by(
            user_id=u.id, kind="SECURITY_EVENT").count() == 1


def test_honest_mistakes_are_not_security_events(client, db, staff, lab, device,
                                                 device_headers):
    client.post("/api/access/deny", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_DENIED", "method": "QR",
        "reason": "BOOKING_NOT_STARTED"})
    assert db.query(Notification).filter_by(kind="SECURITY_EVENT").count() == 0


def test_identity_mismatch_is_a_critical_security_event(client, db, staff, lab,
                                                        device, device_headers):
    client.post("/api/access/events", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "IDENTITY_MISMATCH", "auth_subject": "USER1",
        "message": "QR was USER1 but face matched USER2"})
    n = db.query(Notification).filter_by(user_id=staff.id, kind="SECURITY_EVENT").one()
    assert n.severity == "critical"


# ===========================================================================
# Session expiry and device liveness
# ===========================================================================
def test_expired_token_is_rejected(client, alice):
    stale = create_access_token(alice.id, "STUDENT", expires_minutes=-1)
    r = client.get("/api/bookings", headers={"Authorization": f"Bearer {stale}"})
    assert r.status_code == 401


def test_heartbeat_brings_a_never_seen_device_online(client, db, staff, lab,
                                                     device_headers):
    d = Device(device_uid="CAM_T", name="Test camera",
               device_type=DeviceType.CAMERA, lab_id=lab.id)
    db.add(d)
    db.commit()
    h = H(client, staff)
    before = {x["device_uid"]: x["state"] for x in client.get("/api/devices", headers=h).json()}
    assert before["CAM_T"] == "NO_DATA"
    client.post("/api/access/heartbeat", headers=device_headers,
                json={"device_uid": "CAM_T", "lab_id": lab.code})
    after = {x["device_uid"]: x["state"] for x in client.get("/api/devices", headers=h).json()}
    assert after["CAM_T"] == "ONLINE"
