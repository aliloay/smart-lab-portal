"""
Issue reporting and the maintenance workflow.

The rules under test are the ones the frontend cannot be trusted to enforce:
who can see a report, who can move it, what an upload is allowed to be, and
that every change leaves a history row behind.
"""
import io
import re

import pytest
from PIL import Image

from app.models import (Asset, AssetStatus, Device, DeviceType, Issue,
                        IssueHistory, IssuePhoto, Notification)
from tests.conftest import auth_headers, image_bytes


@pytest.fixture
def robot(db, lab) -> Asset:
    a = Asset(asset_tag="ROB-UR5E-001", name="UR5e Robot", category="Manipulator",
              lab_id=lab.id, status=AssetStatus.AVAILABLE)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@pytest.fixture
def foreign_asset(db, other_lab) -> Asset:
    a = Asset(asset_tag="OSC-9", name="Oscilloscope", category="Instrument",
              lab_id=other_lab.id, status=AssetStatus.AVAILABLE)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def report(client, headers, lab, **over):
    body = {"lab_id": lab.id, "category": "MALFUNCTION", "severity": "HIGH",
            "title": "PLC not powering on",
            "description": "The trainer bench PLC shows no status LEDs at all."}
    body.update(over)
    return client.post("/api/issues", headers=headers, json=body)


@pytest.fixture
def alice_h(client, alice):
    return auth_headers(client, alice.email)


@pytest.fixture
def bob_h(client, bob):
    return auth_headers(client, bob.email)


@pytest.fixture
def staff_h(client, staff):
    return auth_headers(client, staff.email)


@pytest.fixture
def admin_h(client, admin):
    return auth_headers(client, admin.email)


@pytest.fixture
def issue(client, alice_h, lab, robot):
    r = report(client, alice_h, lab, asset_id=robot.id)
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# Creating and seeing
# ===========================================================================
def test_student_creates_issue_with_ticket_number(client, db, alice_h, lab,
                                                  robot, staff):
    r = report(client, alice_h, lab, asset_id=robot.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert re.fullmatch(r"ISS-\d{4}-\d{6}", body["ticket_number"])
    assert body["status"] == "OPEN"
    assert body["asset_name"] == "UR5e Robot"
    assert body["lab_code"] == lab.code
    assert [h["event_type"] for h in body["history"]] == ["ISSUE_CREATED"]

    # Staff hear about it; the reporter is not notified of their own report.
    kinds = {(n.user_id, n.kind) for n in db.query(Notification).all()}
    assert (staff.id, "ISSUE_REPORTED") in kinds
    assert not any(uid == body["reporter_id"] for uid, _ in kinds)


def test_critical_issue_raises_critical_notification(client, db, alice_h, lab,
                                                     staff):
    r = report(client, alice_h, lab, severity="CRITICAL", category="SAFETY",
               title="Exposed mains wiring", description="Cable insulation "
               "melted behind bench 3, conductor visible.")
    assert r.status_code == 201
    n = db.query(Notification).filter_by(user_id=staff.id).one()
    assert n.kind == "ISSUE_CRITICAL"
    assert n.severity == "critical"


def test_student_sees_own_issue(client, alice_h, issue):
    r = client.get("/api/issues", headers=alice_h)
    assert [i["id"] for i in r.json()] == [issue["id"]]
    assert client.get(f"/api/issues/{issue['id']}",
                      headers=alice_h).status_code == 200


def test_student_cannot_see_another_students_issue(client, bob_h, issue):
    # Not in the list, and a direct read is a 404 - not a 403 that would
    # confirm the report exists.
    assert client.get("/api/issues", headers=bob_h).json() == []
    assert client.get(f"/api/issues/{issue['id']}",
                      headers=bob_h).status_code == 404
    # Asking for "not mine" does not widen the scope either.
    r = client.get("/api/issues?mine=false", headers=bob_h)
    assert r.json() == []


def test_staff_and_admin_see_all_issues(client, staff_h, admin_h, issue):
    for h in (staff_h, admin_h):
        assert [i["id"] for i in client.get("/api/issues", headers=h).json()] \
            == [issue["id"]]


def test_asset_from_another_lab_is_rejected(client, alice_h, lab,
                                            foreign_asset):
    r = report(client, alice_h, lab, asset_id=foreign_asset.id)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "ASSET_LAB_MISMATCH"


def test_device_from_another_lab_is_rejected(client, db, alice_h, lab,
                                             other_lab):
    d = Device(device_uid="CAM_OTHER", name="Other cam",
               device_type=DeviceType.CAMERA, lab_id=other_lab.id)
    db.add(d)
    db.commit()
    r = report(client, alice_h, lab, device_id=d.id, category="ACCESS_CONTROL")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DEVICE_LAB_MISMATCH"


def test_unknown_lab_is_rejected(client, alice_h, lab):
    r = client.post("/api/issues", headers=alice_h, json={
        "lab_id": 999999, "category": "OTHER", "severity": "LOW",
        "title": "Something odd", "description": "A description long enough."})
    assert r.status_code == 422


@pytest.mark.parametrize("field,value", [
    ("title", "Hi"),                      # too short
    ("title", "x" * 141),                 # too long
    ("description", "short"),             # too short
    ("category", "EXPLODED"),             # not a category
    ("severity", "APOCALYPTIC"),          # not a severity
])
def test_issue_fields_are_validated(client, alice_h, lab, field, value):
    assert report(client, alice_h, lab, **{field: value}).status_code == 422


def test_general_lab_issue_needs_no_asset(client, alice_h, lab):
    r = report(client, alice_h, lab, category="SAFETY", severity="MEDIUM",
               title="Emergency exit blocked",
               description="Boxes are stacked in front of the rear exit.")
    assert r.status_code == 201
    assert r.json()["asset_id"] is None


def test_student_cannot_link_someone_elses_access_event(client, db, alice_h,
                                                        bob, lab):
    from app.models import AccessEvent, EventType
    ev = AccessEvent(event_type=EventType.ACCESS_DENIED, lab_id=lab.id,
                     user_id=bob.id, message="denied")
    db.add(ev)
    db.commit()
    r = report(client, alice_h, lab, access_event_id=ev.id,
               category="ACCESS_CONTROL")
    assert r.status_code == 422


# ===========================================================================
# Photos
# ===========================================================================
def upload(client, headers, issue_id, files, stage=None):
    data = {"stage": stage} if stage else None
    return client.post(f"/api/issues/{issue_id}/photos", headers=headers,
                       files=[("files", f) for f in files], data=data)


def test_multiple_photos_upload(client, db, alice_h, issue, _tmp_storage):
    files = [("a.jpg", image_bytes("JPEG"), "image/jpeg"),
             ("b.png", image_bytes("PNG"), "image/png"),
             ("c.webp", image_bytes("WEBP"), "image/webp")]
    r = upload(client, alice_h, issue["id"], files)
    assert r.status_code == 201, r.text
    assert [p["content_type"] for p in r.json()] == \
        ["image/jpeg", "image/png", "image/webp"]

    rows = db.query(IssuePhoto).filter_by(issue_id=issue["id"]).all()
    assert len(rows) == 3
    for p in rows:   # original and thumbnail both stored
        assert _tmp_storage.exists(p.storage_key)
        assert _tmp_storage.exists(p.thumb_key)

    detail = client.get(f"/api/issues/{issue['id']}", headers=alice_h).json()
    assert detail["photo_count"] == 3
    assert detail["history"][-1]["event_type"] == "ISSUE_PHOTO_ADDED"


def test_invalid_file_is_rejected_even_with_image_name(client, db, alice_h,
                                                       issue):
    r = upload(client, alice_h, issue["id"],
               [("evil.jpg", b"#!/bin/sh\nrm -rf /\n", "image/jpeg")])
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "INVALID_IMAGE"
    assert db.query(IssuePhoto).count() == 0


def test_disallowed_image_format_is_rejected(client, alice_h, issue):
    r = upload(client, alice_h, issue["id"],
               [("anim.gif", image_bytes("GIF"), "image/gif")])
    assert r.status_code == 422


def test_batch_with_one_bad_file_stores_nothing(client, db, alice_h, issue,
                                                _tmp_storage):
    r = upload(client, alice_h, issue["id"],
               [("ok.jpg", image_bytes("JPEG"), "image/jpeg"),
                ("bad.png", b"not an image", "image/png")])
    assert r.status_code == 422
    assert db.query(IssuePhoto).count() == 0
    assert not any((_tmp_storage.root).rglob("*.jpg"))


def test_oversized_file_is_rejected(client, alice_h, issue, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    r = upload(client, alice_h, issue["id"],
               [("big.jpg", image_bytes("JPEG"), "image/jpeg")])
    assert r.status_code == 422


def test_photo_metadata_and_location_are_stripped(client, db, alice_h, issue,
                                                  _tmp_storage):
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"          # Make
    exif[0x0112] = 6                     # Orientation: rotate 90
    raw = image_bytes("JPEG", size=(400, 200), exif=exif.tobytes())
    r = upload(client, alice_h, issue["id"], [("p.jpg", raw, "image/jpeg")])
    assert r.status_code == 201
    row = db.query(IssuePhoto).one()
    stored = b"".join(_tmp_storage.open(row.storage_key))
    img = Image.open(io.BytesIO(stored))
    assert not img.getexif()                         # EXIF gone
    assert (row.width, row.height) == (200, 400)     # rotated upright


def test_large_photo_is_scaled_down(client, db, alice_h, issue, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "IMAGE_MAX_DIMENSION", 300)
    r = upload(client, alice_h, issue["id"],
               [("big.png", image_bytes("PNG", size=(1200, 600)), "image/png")])
    assert r.status_code == 201
    row = db.query(IssuePhoto).one()
    assert max(row.width, row.height) == 300


def test_photo_file_is_private_to_the_issue(client, alice_h, bob_h, staff_h,
                                            issue):
    r = upload(client, alice_h, issue["id"],
               [("a.jpg", image_bytes("JPEG"), "image/jpeg")])
    pid = r.json()[0]["id"]
    url = f"/api/issues/{issue['id']}/photos/{pid}/file"
    ok = client.get(url, headers=alice_h)
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg"
    assert client.get(url + "?variant=thumb", headers=staff_h).status_code == 200
    assert client.get(url, headers=bob_h).status_code == 404
    assert client.get(url).status_code == 401


def test_student_cannot_add_maintenance_photos(client, alice_h, issue):
    r = upload(client, alice_h, issue["id"],
               [("a.jpg", image_bytes("JPEG"), "image/jpeg")], stage="BEFORE")
    assert r.status_code == 403


def test_staff_maintenance_photos_do_not_replace_report_photos(
        client, db, alice_h, staff_h, issue):
    upload(client, alice_h, issue["id"],
           [("report.jpg", image_bytes("JPEG"), "image/jpeg")])
    for stage in ("BEFORE", "AFTER"):
        r = upload(client, staff_h, issue["id"],
                   [(f"{stage}.jpg", image_bytes("JPEG"), "image/jpeg")],
                   stage=stage)
        assert r.status_code == 201, r.text
    stages = sorted(p.stage.value for p in db.query(IssuePhoto).all())
    assert stages == ["AFTER", "BEFORE", "REPORT"]


# ===========================================================================
# The staff workflow
# ===========================================================================
def test_staff_acknowledges_and_reporter_is_notified(client, db, staff_h,
                                                     alice, issue):
    r = client.post(f"/api/issues/{issue['id']}/acknowledge", headers=staff_h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ACKNOWLEDGED"
    assert body["acknowledged_at"] is not None
    assert db.query(Notification).filter_by(
        user_id=alice.id, kind="ISSUE_ACKNOWLEDGED").count() == 1


def test_student_cannot_run_the_staff_workflow(client, alice_h, staff, issue):
    iid = issue["id"]
    assert client.post(f"/api/issues/{iid}/acknowledge",
                       headers=alice_h).status_code == 403
    assert client.post(f"/api/issues/{iid}/assign", headers=alice_h,
                       json={"assignee_id": staff.id}).status_code == 403
    assert client.post(f"/api/issues/{iid}/resolve", headers=alice_h,
                       json={"resolution_notes": "fixed it myself"}).status_code == 403
    assert client.patch(f"/api/issues/{iid}", headers=alice_h,
                        json={"severity": "LOW"}).status_code == 403
    assert client.get("/api/issues/summary", headers=alice_h).status_code == 403


def test_assignment_acknowledges_and_notifies(client, db, staff_h, staff,
                                              alice, issue):
    r = client.post(f"/api/issues/{issue['id']}/assign", headers=staff_h,
                    json={"assignee_id": staff.id})
    assert r.status_code == 200
    body = r.json()
    assert body["assignee_name"] == "Lab Technician"
    assert body["status"] == "ACKNOWLEDGED"
    assert db.query(Notification).filter_by(
        user_id=alice.id, kind="ISSUE_ASSIGNED").count() == 1


def test_cannot_assign_to_a_student(client, staff_h, bob, issue):
    r = client.post(f"/api/issues/{issue['id']}/assign", headers=staff_h,
                    json={"assignee_id": bob.id})
    assert r.status_code == 422


def test_status_transitions_are_enforced(client, staff_h, issue):
    iid = issue["id"]

    def move(s, note=""):
        return client.post(f"/api/issues/{iid}/status", headers=staff_h,
                           json={"status": s, "note": note})

    assert move("IN_PROGRESS").status_code == 200
    # Backwards to ACKNOWLEDGED is not a transition the workflow allows.
    assert move("ACKNOWLEDGED").status_code == 409
    assert move("WAITING_FOR_PARTS", "Relay module ordered").status_code == 200
    assert move("IN_PROGRESS").status_code == 200
    # RESOLVED through the status endpoint still needs notes.
    assert move("RESOLVED").status_code == 422
    r = move("RESOLVED", "Replaced the 24V supply fuse.")
    assert r.status_code == 200
    assert r.json()["resolution_notes"] == "Replaced the 24V supply fuse."
    # Staff cannot close; that is an administrator's decision.
    assert move("CLOSED").status_code == 403


def test_resolution_requires_notes_and_notifies(client, db, staff_h, alice,
                                                issue):
    iid = issue["id"]
    assert client.post(f"/api/issues/{iid}/resolve", headers=staff_h,
                       json={"resolution_notes": ""}).status_code == 422
    r = client.post(f"/api/issues/{iid}/resolve", headers=staff_h,
                    json={"resolution_notes": "Reseated the joint 3 encoder."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "RESOLVED"
    assert body["resolved_at"] is not None
    assert db.query(Notification).filter_by(
        user_id=alice.id, kind="ISSUE_RESOLVED").count() == 1


def test_only_admin_closes_and_reopens(client, staff_h, admin_h, issue):
    iid = issue["id"]
    client.post(f"/api/issues/{iid}/resolve", headers=staff_h,
                json={"resolution_notes": "Replaced the cable."})
    assert client.post(f"/api/issues/{iid}/close",
                       headers=staff_h).status_code == 403
    r = client.post(f"/api/issues/{iid}/close", headers=admin_h)
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"
    r = client.post(f"/api/issues/{iid}/reopen", headers=admin_h,
                    json={"note": "Fault returned"})
    assert r.status_code == 200
    assert r.json()["status"] == "OPEN"
    assert r.json()["resolved_at"] is None


def test_escalation_notifies_staff(client, db, staff_h, admin, issue):
    iid = issue["id"]
    client.patch(f"/api/issues/{iid}", headers=staff_h,
                 json={"severity": "LOW"})
    r = client.patch(f"/api/issues/{iid}", headers=staff_h,
                     json={"severity": "CRITICAL"})
    assert r.status_code == 200
    assert db.query(Notification).filter_by(
        user_id=admin.id, kind="ISSUE_ESCALATED").count() == 1


def test_issue_audit_trail_records_every_change(client, db, staff_h, staff,
                                                admin_h, alice_h, issue):
    iid = issue["id"]
    client.post(f"/api/issues/{iid}/assign", headers=staff_h,
                json={"assignee_id": staff.id})
    client.post(f"/api/issues/{iid}/status", headers=staff_h,
                json={"status": "IN_PROGRESS"})
    client.post(f"/api/issues/{iid}/comments", headers=staff_h,
                json={"body": "Joint 3 encoder cable chafed."})
    client.post(f"/api/issues/{iid}/resolve", headers=staff_h,
                json={"resolution_notes": "Cable replaced and re-routed."})
    client.post(f"/api/issues/{iid}/close", headers=admin_h)

    rows = db.query(IssueHistory).filter_by(issue_id=iid) \
        .order_by(IssueHistory.id).all()
    assert [r.event_type.value for r in rows] == [
        "ISSUE_CREATED", "ISSUE_ACKNOWLEDGED", "ISSUE_ASSIGNED",
        "ISSUE_STATUS_CHANGED", "ISSUE_COMMENT_ADDED", "ISSUE_RESOLVED",
        "ISSUE_CLOSED"]
    transitions = [(r.old_status and r.old_status.value,
                    r.new_status and r.new_status.value)
                   for r in rows if r.new_status]
    assert transitions == [(None, "OPEN"), ("OPEN", "ACKNOWLEDGED"),
                           ("ACKNOWLEDGED", "IN_PROGRESS"),
                           ("IN_PROGRESS", "RESOLVED"), ("RESOLVED", "CLOSED")]
    assert all(r.actor_id is not None for r in rows)

    # The reporter sees the same timeline.
    seen = client.get(f"/api/issues/{iid}", headers=alice_h).json()["history"]
    assert len(seen) == len(rows)


# ===========================================================================
# Comments
# ===========================================================================
def test_internal_notes_are_hidden_from_the_reporter(client, staff_h, alice_h,
                                                     issue):
    iid = issue["id"]
    client.post(f"/api/issues/{iid}/comments", headers=staff_h,
                json={"body": "Probably misuse, check CCTV.", "is_internal": True})
    client.post(f"/api/issues/{iid}/comments", headers=staff_h,
                json={"body": "We are looking at it."})
    staff_view = client.get(f"/api/issues/{iid}", headers=staff_h).json()
    student_view = client.get(f"/api/issues/{iid}", headers=alice_h).json()
    assert len(staff_view["comments"]) == 2
    assert [c["body"] for c in student_view["comments"]] == ["We are looking at it."]
    assert all("Internal" not in h["message"] for h in student_view["history"])


def test_student_adds_information_only_while_open(client, alice_h, staff_h,
                                                  issue):
    iid = issue["id"]
    r = client.post(f"/api/issues/{iid}/comments", headers=alice_h,
                    json={"body": "It also smells of burnt plastic."})
    assert r.status_code == 201
    # Students cannot write internal notes.
    assert client.post(f"/api/issues/{iid}/comments", headers=alice_h,
                       json={"body": "x", "is_internal": True}).status_code == 403
    client.post(f"/api/issues/{iid}/resolve", headers=staff_h,
                json={"resolution_notes": "Replaced the power supply."})
    assert client.post(f"/api/issues/{iid}/comments", headers=alice_h,
                       json={"body": "Thanks!"}).status_code == 403


# ===========================================================================
# Connected to the rest of the system
# ===========================================================================
def test_issue_appears_in_asset_maintenance_history(client, staff_h, alice_h,
                                                    robot, issue):
    client.post(f"/api/issues/{issue['id']}/resolve", headers=staff_h,
                json={"resolution_notes": "Encoder recalibrated."})
    r = client.get(f"/api/assets/{robot.id}", headers=alice_h)
    assert r.status_code == 200
    hist = r.json()["maintenance"]
    assert [h["ticket_number"] for h in hist] == [issue["ticket_number"]]
    assert hist[0]["resolution_notes"] == "Encoder recalibrated."
    assert hist[0]["is_mine"] is True


def test_issue_appears_on_the_laboratory(client, bob_h, lab, issue):
    # Another student sees that the lab has a problem - but not who said so.
    r = client.get(f"/api/labs/{lab.id}", headers=bob_h).json()
    assert r["open_issues"] == 1
    assert r["high_priority_issues"] == 1
    brief = r["recent_issues"][0]
    assert brief["title"] == "PLC not powering on"
    assert "reporter_id" not in brief and "reporter_name" not in brief
    assert brief["is_mine"] is False


def test_asset_open_issue_count(client, staff_h, robot, issue):
    rows = client.get("/api/assets", headers=staff_h).json()
    assert next(a for a in rows if a["id"] == robot.id)["open_issues"] == 1


def test_summary_counts_real_rows(client, staff_h, alice_h, lab, issue):
    report(client, alice_h, lab, severity="CRITICAL", category="SAFETY",
           title="Sparks from socket", description="Sparking at bench socket 2.")
    s = client.get("/api/issues/summary", headers=staff_h).json()
    assert s["open"] == 2
    assert s["critical"] == 1 and s["high"] == 1
    assert s["unassigned"] == 2
    assert s["by_lab"][0] == {"key": str(lab.id), "label": lab.code, "count": 2}
    assert s["avg_resolution_hours"] is None      # nothing resolved yet


def test_overdue_follows_the_published_sla(client, db, staff_h, issue):
    from datetime import datetime, timedelta, timezone
    row = db.get(Issue, issue["id"])
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=73)  # HIGH: 72h
    db.commit()
    s = client.get("/api/issues/summary", headers=staff_h).json()
    assert s["overdue"] == 1
    assert client.get("/api/issues?overdue=true",
                      headers=staff_h).json()[0]["is_overdue"] is True
