"""Answer feedback (2026-10-27): stored locally, anonymised in the review, staff-only review."""
from tests.conftest import auth_headers


def test_feedback_is_stored_and_reviewed_anonymised(client, staff, alice):
    h = auth_headers(client, alice.email)
    for rating, route in (("down", "routed"), ("up", "instant"), ("down", "routed")):
        r = client.post("/api/ai/feedback", headers=h, json={
            "question": "is USER1 inside? mail ali@giu-uni.de id 12345678", "answer": "no", "rating": rating,
            "route": route, "intent": "inside"})
        assert r.status_code == 200
    assert client.get("/api/ai/feedback/review", headers=h).status_code == 403
    rv = client.get("/api/ai/feedback/review", headers=auth_headers(client, staff.email)).json()
    assert rv["routes"]["routed"]["down"] == 2 and rv["routes"]["instant"]["up"] == 1
    q = rv["routes"]["routed"]["examples"][0]["question"]
    assert "<user>" in q and "<email>" in q and "<id>" in q and "giu-uni" not in q and "12345678" not in q
    assert client.post("/api/ai/feedback", headers=h, json={"question": "x", "answer": "y", "rating": "meh"}).status_code == 422
