"""Assistant booking actions (2026-10-27): instant proposals, nothing changes until the user confirms through the
normal booking endpoints; questions about bookings stay questions."""
from datetime import datetime, timedelta, timezone

from app.models import Booking, BookingStatus
from app.services import agent_actions
from tests.conftest import auth_headers


def test_questions_are_not_actions():
    for q in ("which labs can I book?", "When is my next booking?", "show my bookings", "how many bookings are pending"):
        assert not agent_actions.wants_action(q), q
    for q in ("book LAB_01 tomorrow 10-12", "please reserve the robotics lab on friday 2-4pm", "cancel my booking"):
        assert agent_actions.wants_action(q), q


def test_book_proposal_then_confirm_through_the_normal_endpoint(client, db, alice, lab):
    h = auth_headers(client, alice.email)
    before = db.query(Booking).count()
    r = client.post("/api/ai/student/ask", headers=h, json={"question": f"book {lab.code} tomorrow 10-12"}).json()
    assert r["instant"] and r["tools_used"] == ["instant:create_booking"]
    a = r["actions"][0]
    assert a["type"] == "create_booking" and a["lab_id"] == lab.id and lab.code in r["answer"]
    assert db.query(Booking).count() == before                       # proposing changed nothing
    made = client.post("/api/bookings", headers=h, json={k: a[k] for k in ("lab_id", "start_time", "end_time", "reason")})
    assert made.status_code == 201
    r = client.post("/api/ai/student/ask", headers=h, json={"question": "cancel my booking"}).json()
    c = r["actions"][0]
    assert c["type"] == "cancel_booking" and c["booking_id"] == made.json()["id"]
    assert client.post(f"/api/bookings/{c['booking_id']}/cancel", headers=h).status_code == 200


def test_missing_parts_are_asked_for_and_past_times_refused(client, db, alice, lab):
    h = auth_headers(client, alice.email)
    r = client.post("/api/ai/student/ask", headers=h, json={"question": "book a lab tomorrow"}).json()
    assert "still need" in r["answer"] and "which lab" in r["answer"] and "time" in r["answer"] and not r.get("actions")
    p = agent_actions.propose(db, alice, f"book {lab.code} today 1-2am",
                              now=datetime.now(timezone.utc).replace(hour=23, minute=0))
    assert "already passed" in p["answer"] and not p.get("actions")


def test_cancel_only_offers_the_users_own_bookings(client, db, alice, staff, lab):
    start = datetime.now(timezone.utc) + timedelta(days=2)
    db.add(Booking(user_id=staff.id, lab_id=lab.id, start_time=start, end_time=start + timedelta(hours=1),
                   status=BookingStatus.CONFIRMED, reason="x"))
    db.commit()
    r = client.post("/api/ai/student/ask", headers=auth_headers(client, alice.email), json={"question": "cancel my booking"}).json()
    assert "no upcoming booking" in r["answer"] and not r.get("actions")
