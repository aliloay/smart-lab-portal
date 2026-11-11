"""Streamed assistant answers (2026-11-11): POST /api/ai/ask/stream and /api/ai/student/ask/stream.
The model is faked - these tests are about the protocol, the checks and the fall-backs, not about Ollama."""
import json

import pytest

from app.core.config import settings
from app.models import AuditLog
from app.services import ai
from tests.conftest import auth_headers


def events(r):
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(x) for x in r.text.splitlines() if x.strip()]


@pytest.fixture
def local_model(monkeypatch):
    """A configured local model whose answer the test chooses."""
    said = {"pieces": ["The lab ", "is quiet ", "today."], "calls": []}
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setattr(settings, "AI_ROUTER", False)
    monkeypatch.setattr(ai, "provider", lambda: "ollama")
    monkeypatch.setattr(ai, "configured", lambda: True)

    def fake(model, messages, num_predict=None):
        said["calls"].append({"model": model, "messages": messages})
        yield from said["pieces"]
    monkeypatch.setattr(ai, "_ollama_stream", fake)
    return said


Q = {"question": "Give me a short written opinion about how this month went overall"}


def test_staff_answer_arrives_in_pieces_and_ends_with_the_whole_answer(client, db, staff, lab, local_model):
    ev = events(client.post("/api/ai/ask/stream", json=Q, headers=auth_headers(client, staff.email)))
    assert [e["type"] for e in ev][0] == "meta" and ev[-1]["type"] == "final"
    assert "".join(e["text"] for e in ev if e["type"] == "token") == "The lab is quiet today."
    assert ev[-1]["answer"] == "The lab is quiet today." and ev[-1]["model"] == settings.OLLAMA_MODEL
    assert db.query(AuditLog).filter_by(action="AI_QUESTION").count() == 1       # audited like /ask


def test_the_marker_for_the_tool_loop_is_never_shown(client, staff, lab, local_model, monkeypatch):
    local_model["pieces"] = ["NEED", "_TOOLS"]
    monkeypatch.setattr(ai, "_ask_tools", lambda db, q, h, m: {"answer": "From the tools.", "tools_used": ["get_report"],
                                                                "model": m})
    ev = events(client.post("/api/ai/ask/stream", json=Q, headers=auth_headers(client, staff.email)))
    assert not [e for e in ev if e["type"] == "token"]                           # nothing of the marker reached the page
    assert ev[-1] == {"type": "final", "answer": "From the tools.", "tools_used": ["get_report"],
                      "model": settings.OLLAMA_MODEL}


def test_a_model_failure_is_an_error_event_not_a_broken_stream(client, staff, lab, local_model, monkeypatch):
    def down(model, messages, num_predict=None):
        raise ai.AIUnavailable("Ollama is not running.")
        yield ""                                                                 # pragma: no cover
    monkeypatch.setattr(ai, "_ollama_stream", down)
    ev = events(client.post("/api/ai/ask/stream", json=Q, headers=auth_headers(client, staff.email)))
    assert ev[-1] == {"type": "error", "detail": "Ollama is not running."}


def test_instant_answers_come_as_one_final_event_without_a_model(client, staff, lab, monkeypatch):
    monkeypatch.setattr(ai, "configured", lambda: False)                         # no model at all
    ev = events(client.post("/api/ai/ask/stream", json={"question": "which devices are offline?"},
                            headers=auth_headers(client, staff.email)))
    assert len(ev) == 1 and ev[0]["type"] == "final" and ev[0]["instant"] is True


def test_same_door_as_the_plain_endpoint(client, alice, staff, lab, local_model, monkeypatch):
    assert client.post("/api/ai/ask/stream", json=Q).status_code == 401
    assert client.post("/api/ai/ask/stream", json=Q, headers=auth_headers(client, alice.email)).status_code == 403
    monkeypatch.setattr(settings, "AI_QUESTIONS_PER_HOUR", 1)
    h = auth_headers(client, staff.email)
    assert client.post("/api/ai/ask/stream", json=Q, headers=h).status_code == 200
    assert client.post("/api/ai/ask/stream", json=Q, headers=h).status_code == 429


def test_student_stream_uses_only_that_students_data(client, db, alice, bob, lab, local_model):
    ev = events(client.post("/api/ai/student/ask/stream", json={"question": "Please explain what my next steps are"},
                            headers=auth_headers(client, alice.email)))
    assert ev[-1]["type"] == "final" and ev[-1]["answer"] == "The lab is quiet today."
    prompt = local_model["calls"][0]["messages"][0]["content"]
    assert local_model["calls"][0]["model"] == settings.ollama_student_model
    assert bob.email not in prompt and (bob.full_name or "?") not in prompt
    assert db.query(AuditLog).filter_by(action="AI_STUDENT_QUESTION").count() == 1
