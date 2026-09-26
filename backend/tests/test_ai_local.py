"""
Free local AI (Ollama) and the student helper.

Ollama is never contacted: httpx is replaced by a fake that replays scripted
/api/chat replies, so these tests check what the portal controls - the tool
loop, what data reaches the model, access and limits.
"""
from datetime import timedelta

import httpx
import pytest

from app.core.config import settings
from app.models import Booking, BookingStatus, Issue, IssueCategory, IssueSeverity, IssueStatus
from app.services import ai
from tests.conftest import auth_headers


class FakeOllama:
    def __init__(self, replies, models=("qwen2.5:3b", "qwen2.5:1.5b")):
        self.replies = list(replies)
        self.models = models
        self.bodies = []

    def post(self, url, json=None, timeout=None):
        assert url.endswith("/api/chat")
        self.bodies.append({**json, "messages": list(json["messages"])})
        return httpx.Response(200, json={"message": self.replies.pop(0)},
                              request=httpx.Request("POST", url))

    def get(self, url, timeout=None):
        return httpx.Response(200, json={"models": [{"name": m} for m in self.models]},
                              request=httpx.Request("GET", url))


@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama:11434")
    ai._health.update(at=0.0, value=None)

    def install(replies, **kw):
        fake = FakeOllama(replies, **kw)
        monkeypatch.setattr(ai.httpx, "post", fake.post)
        monkeypatch.setattr(ai.httpx, "get", fake.get)
        return fake
    yield install
    ai._health.update(at=0.0, value=None)


def test_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_URL", "")
    assert ai.provider() is None
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://x:11434")
    assert ai.provider() == "ollama"
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "k")
    assert ai.provider() == "anthropic"
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    assert ai.provider() == "ollama"


def test_ollama_tool_loop(db, lab, ollama):
    fake = ollama([
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "get_lab_readiness",
                                      "arguments": {"lab_code": "lab_test"}}}]},
        {"role": "assistant", "content": "LAB_TEST is ready."},
    ])
    out = ai.ask(db, "Is LAB_TEST ready?")
    assert out == {"answer": "LAB_TEST is ready.", "tools_used": ["get_lab_readiness"],
                   "model": "qwen2.5:3b"}
    first, second = fake.bodies
    assert first["model"] == "qwen2.5:3b" and first["stream"] is False
    assert {t["function"]["name"] for t in first["tools"]} == set(ai.HANDLERS)
    tool_msg = second["messages"][-1]
    assert tool_msg["role"] == "tool" and "LAB_TEST" in tool_msg["content"]


def test_ollama_down_is_readable(db, monkeypatch, ollama):
    ollama([])

    def boom(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(ai.httpx, "post", boom)
    monkeypatch.setattr(ai.httpx, "get", boom)
    with pytest.raises(ai.AIUnavailable, match="Ollama is not running"):
        ai.ask(db, "q")
    assert ai.health()["reachable"] is False


def test_status_reports_missing_models(client, staff, ollama):
    ollama([], models=("qwen2.5:3b",))
    s = client.get("/api/ai/status", headers=auth_headers(client, staff.email)).json()
    assert s["provider"] == "ollama" and s["reachable"] is True
    assert s["missing_models"] == ["qwen2.5:1.5b"]


def test_student_context_is_private(db, alice, bob, lab, now):
    db.add_all([
        Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                reason="thesis", start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=3)),
        Booking(user_id=bob.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                reason="bob secret", start_time=now + timedelta(hours=5),
                end_time=now + timedelta(hours=6)),
        Issue(reporter_id=bob.id, lab_id=lab.id, title="bob report", description="d",
              category=IssueCategory.MALFUNCTION, severity=IssueSeverity.LOW,
              status=IssueStatus.OPEN, ticket_number="ISS-B"),
        Issue(reporter_id=alice.id, lab_id=lab.id, title="alice report", description="d",
              category=IssueCategory.MALFUNCTION, severity=IssueSeverity.LOW,
              status=IssueStatus.OPEN, ticket_number="ISS-A"),
    ])
    db.commit()
    ctx = ai.student_context(db, alice)
    text = ai._json(ctx)
    assert [b["reason"] for b in ctx["upcoming_bookings"]] == ["thesis"]
    assert [i["ticket"] for i in ctx["my_issue_reports"]] == ["ISS-A"]
    assert "bob" not in text.lower()
    # Bob's booking still shows as a busy slot for the lab - time only.
    assert len(ctx["labs"][0]["booked_slots_next_3_days"]) == 2


def test_student_endpoint(client, db, alice, lab, ollama, monkeypatch):
    fake = ollama([{"role": "assistant", "content": "You have no bookings."}] * 3)
    monkeypatch.setattr(settings, "AI_STUDENT_QUESTIONS_PER_HOUR", 2)
    h = auth_headers(client, alice.email)
    st = client.get("/api/ai/student/status", headers=h).json()
    assert st["configured"] and st["model"] == "qwen2.5:1.5b"
    for _ in range(2):
        r = client.post("/api/ai/student/ask", headers=h,
                        json={"question": "what are my bookings?"})
        assert r.status_code == 200 and r.json()["answer"] == "You have no bookings."
    assert client.post("/api/ai/student/ask", headers=h,
                       json={"question": "again?"}).status_code == 429
    body = fake.bodies[0]
    assert body["model"] == "qwen2.5:1.5b" and "tools" not in body
    assert alice.full_name in body["messages"][0]["content"]
    # Students still cannot use the staff assistant.
    assert client.post("/api/ai/ask", headers=h,
                       json={"question": "how busy?"}).status_code == 403


def test_student_helper_can_be_disabled(client, alice, ollama, monkeypatch):
    ollama([])
    monkeypatch.setattr(settings, "AI_STUDENT_ENABLED", False)
    h = auth_headers(client, alice.email)
    assert client.get("/api/ai/student/status", headers=h).json()["configured"] is False
    assert client.post("/api/ai/student/ask", headers=h,
                       json={"question": "hi there"}).status_code == 503


def test_student_helper_on_claude(db, alice, monkeypatch):
    from types import SimpleNamespace as NS
    seen = {}

    def create(**kw):
        seen.update(kw)
        return NS(model=kw["model"], content=[NS(type="text", text="Hi Alice.")])
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "k")
    out = ai.ask_student(db, alice, "hello", client=NS(messages=NS(create=create)))
    assert out["answer"] == "Hi Alice." and seen["model"] == settings.AI_STUDENT_MODEL
    assert "tools" not in seen and "DATA:" in seen["system"]


def test_ollama_crash_retries_with_smaller_context(db, monkeypatch, ollama):
    ollama([])
    seen = []

    def post(url, json=None, timeout=None):
        seen.append(json["options"]["num_ctx"])
        req = httpx.Request("POST", url)
        if len(seen) == 1:
            return httpx.Response(500, request=req, json={
                "error": "llama-server process has terminated: exit status 0xc0000409"})
        return httpx.Response(200, request=req,
                              json={"message": {"role": "assistant", "content": "ok"}})
    monkeypatch.setattr(ai.httpx, "post", post)
    assert ai.ask(db, "q")["answer"] == "ok"
    assert seen == [settings.OLLAMA_NUM_CTX, ai.OLLAMA_FALLBACK_CTX]

    def always_crash(url, json=None, timeout=None):
        return httpx.Response(500, request=httpx.Request("POST", url), json={
            "error": "llama-server process has terminated"})
    monkeypatch.setattr(ai.httpx, "post", always_crash)
    with pytest.raises(ai.AIUnavailable, match="crashed on this computer"):
        ai.ask(db, "q")


def test_ollama_cuda_failure_falls_back_to_processor(db, monkeypatch, ollama):
    ollama([])
    seen = []

    def post(url, json=None, timeout=None):
        seen.append(json["options"].get("num_gpu"))
        req = httpx.Request("POST", url)
        if json["options"].get("num_gpu") != 0:
            return httpx.Response(500, request=req, json={
                "error": "llama-server process has terminated: CUDA error: "
                         "device kernel image is invalid"})
        return httpx.Response(200, request=req,
                              json={"message": {"role": "assistant", "content": "cpu ok"}})
    monkeypatch.setattr(ai.httpx, "post", post)
    assert ai.ask(db, "q")["answer"] == "cpu ok"
    assert seen == [None, None, 0]

    seen.clear()
    monkeypatch.setattr(settings, "OLLAMA_CPU_ONLY", True)
    assert ai.ask(db, "q")["answer"] == "cpu ok"
    assert seen == [0]                       # straight to the processor
