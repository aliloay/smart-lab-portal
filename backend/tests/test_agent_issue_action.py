"""Maintenance reports through the assistant (2026-11-11): a PROPOSAL the page confirms; nothing is filed by the
assistant itself. Confirm = the normal POST /api/issues as the signed-in user."""
from app.models import Device, DeviceType, Issue
from app.services import agent_actions as aa
from tests.conftest import auth_headers


def test_a_report_becomes_a_proposal_with_lab_device_category(db, alice, lab):
    db.add(Device(device_uid="PC_04", name="PC-04", lab_id=lab.id, device_type=DeviceType.PC))
    db.commit()
    p = aa.propose(db, alice, f"report a network problem on PC-04 in {lab.code}, it won't connect")
    act = p["actions"][0]
    assert p["intent"] == "create_issue" and act["type"] == "create_issue"
    assert act["lab_id"] == lab.id and act["category"] == "NETWORK" and act["severity"] == "MEDIUM"
    assert act["device_id"] == db.query(Device).filter_by(device_uid="PC_04").one().id
    assert db.query(Issue).count() == 0                                    # proposed, not filed


def test_safety_words_raise_the_severity_and_questions_are_not_reports(db, alice, lab):
    p = aa.propose(db, alice, f"there is smoke near the 3D printer in {lab.code}, it is broken")
    assert p["actions"][0]["category"] == "SAFETY" and p["actions"][0]["severity"] == "HIGH"
    for q in ("which issues are open?", "show me broken devices", "how many problems were reported this week?"):
        assert aa.propose(db, alice, q) is None or aa.propose(db, alice, q).get("intent") != "create_issue", q


def test_booking_sentences_still_go_to_bookings(db, alice, lab):
    p = aa.propose(db, alice, f"book {lab.code} tomorrow 10-12")
    assert p is not None and p["intent"] == "create_booking"


def test_confirming_files_it_through_the_normal_endpoint(client, db, alice, lab):
    act = aa.propose(db, alice, f"the oscilloscope in {lab.code} is broken")["actions"][0]
    r = client.post("/api/issues", headers=auth_headers(client, alice.email),
                    json={k: act[k] for k in ("lab_id", "device_id", "category", "severity", "title", "description")})
    assert r.status_code in (200, 201), r.text
    assert db.query(Issue).count() == 1 and db.query(Issue).one().category.value == "DAMAGED"
