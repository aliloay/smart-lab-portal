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


@pytest.fixture(autouse=True)
def _pinned_models(monkeypatch):
    """These tests describe behaviour, not the lab's configuration: they must not follow the live .env
    (2026-10-19 the lab moved both assistants to qwen2.5:1.5b on the GPU and these tests broke)."""
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setattr(settings, "OLLAMA_STUDENT_MODEL", "qwen2.5:1.5b")
    monkeypatch.setattr(settings, "OLLAMA_CPU_ONLY", False)
    monkeypatch.setattr(settings, "OLLAMA_GPU_POLICY", "gpu")
    ai._gate_cache.update(at=0.0)


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
    monkeypatch.setattr(settings, "OLLAMA_STUDENT_MODEL", "qwen2.5:1.5b")
    monkeypatch.setattr(settings, "OLLAMA_NUM_CTX", 8192)     # these tests exercise the 8k -> 4k -> processor retries
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
    assert ai.provider() == "ollama"                 # 100 % local by default: a cloud key is ignored (2026-10-26)
    monkeypatch.setattr(settings, "AI_LOCAL_ONLY", False)
    assert ai.provider() == "anthropic"              # only with an explicit opt-in
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    assert ai.provider() == "ollama"


def test_ollama_answers_from_the_snapshot_in_one_call(db, lab, ollama):
    fake = ollama([{"role": "assistant", "content": "- 3 bookings this week"}])
    out = ai.ask(db, "How busy was it this week?")
    assert out == {"answer": "- 3 bookings this week", "tools_used": ["snapshot"], "model": "qwen2.5:3b"}
    (body,) = fake.bodies                                  # one call, no tools
    assert "tools" not in body and "SNAPSHOT" in body["messages"][0]["content"]


def test_ollama_tool_loop(db, lab, ollama, monkeypatch):
    monkeypatch.setattr(ai.settings, "AI_ROUTER", False)          # the model-driven loop (router: test_ai_router.py)
    fake = ollama([
        {"role": "assistant", "content": "NEED_TOOLS"},     # the snapshot does not cover it
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "get_lab_readiness",
                                      "arguments": {"lab_code": "lab_test"}}}]},
        {"role": "assistant", "content": "LAB_TEST is ready."},
    ])
    out = ai.ask(db, "Is LAB_TEST ready?")
    assert out == {"answer": "LAB_TEST is ready.", "tools_used": ["get_lab_readiness"],
                   "model": "qwen2.5:3b"}
    quick, first, second = fake.bodies
    assert "tools" not in quick
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
                        json={"question": "how does the door entry work?"})
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
    assert "tools" not in seen and "DATA (this student only)" in seen["system"]
    assert "HOW SMART LAB WORKS" in seen["system"]


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
    seen.clear()                             # remembered: no GPU retries now
    assert ai.ask(db, "q")["answer"] == "cpu ok"
    assert seen == [0]
    ai._ollama_state["cpu"] = False

    seen.clear()
    monkeypatch.setattr(settings, "OLLAMA_CPU_ONLY", True)
    assert ai.ask(db, "q")["answer"] == "cpu ok"
    assert seen == [0]                       # straight to the processor


def test_student_model_defaults_to_staff_model(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_STUDENT_MODEL", "")
    assert settings.ollama_student_model == settings.OLLAMA_MODEL


def test_warm_up_loads_both_models_with_their_own_context(monkeypatch, ollama):
    ollama([])
    loaded = []
    monkeypatch.setattr(ai.httpx, "post", lambda url, json=None, timeout=None: loaded.append(
        (url.rsplit("/", 1)[-1], json["model"], json["options"]["num_ctx"])))
    ai.warm_up()
    assert loaded == [("generate", "qwen2.5:3b", settings.OLLAMA_NUM_CTX),
                      ("generate", "qwen2.5:1.5b", settings.OLLAMA_STUDENT_NUM_CTX)]
    loaded.clear()                          # shared model: loaded once, staff size
    monkeypatch.setattr(settings, "OLLAMA_STUDENT_MODEL", "")
    ai.warm_up()
    assert loaded == [("generate", "qwen2.5:3b", settings.OLLAMA_NUM_CTX)]


def test_student_chat_uses_its_own_context_size(db, alice, ollama):
    fake = ollama([{"role": "assistant", "content": "hi"}])
    ai.ask_student(db, alice, "hello")
    assert fake.bodies[0]["options"]["num_ctx"] == settings.OLLAMA_STUDENT_NUM_CTX


def test_student_sees_own_door_refusals_in_plain_words(db, alice, bob, lab):
    from app.models import AccessEvent, AccessResult, AuthMethod, EventType
    db.add_all([
        AccessEvent(event_type=EventType.QR_REJECTED, user_id=alice.id, lab_id=lab.id,
                    method=AuthMethod.QR, result=AccessResult.DENIED,
                    reason="BOOKING_NOT_STARTED", message="x"),
        AccessEvent(event_type=EventType.QR_REJECTED, user_id=bob.id, lab_id=lab.id,
                    method=AuthMethod.QR, result=AccessResult.DENIED,
                    reason="WRONG_LAB", message="x"),
    ])
    db.commit()
    ctx = ai.student_context(db, alice)
    assert [a["why"] for a in ctx["my_recent_door_attempts"]] == [
        "The booking window has not opened yet."]
    assert ctx["lab_access_setup"]["setup_complete"] is True   # enrolled fixture


def test_guide_has_no_secrets():
    from app.services.ai_guide import guide
    text = guide().lower()
    for bad in ("api_key", "password", "token=", "http://", "https://", "192.168.", "secret"):
        assert bad not in text
    assert "enroll" not in text or "fingerprint" in text



def test_an_answer_uses_a_bounded_number_of_cpu_threads(db, lab, ollama, monkeypatch):
    """2026-10-18: Ollama's runner is above-normal priority and takes every core by default - one answer
    took camera 2 from 7 to 1.7 analyses/s. Answers carry num_thread (0 = Ollama's default)."""
    monkeypatch.setattr(settings, "OLLAMA_NUM_THREAD", 4)
    fake = ollama([{"role": "assistant", "content": "ok"}])
    ai.ask(db, "How busy was it this week?")
    assert fake.bodies[0]["options"]["num_thread"] == 4
    monkeypatch.setattr(settings, "OLLAMA_NUM_THREAD", 0)
    fake = ollama([{"role": "assistant", "content": "ok"}])
    ai.ask(db, "How busy was it this week?")
    assert "num_thread" not in fake.bodies[0]["options"]



def test_only_one_answer_is_generated_at_a_time(db, lab, ollama, monkeypatch):
    """2026-10-18: generations are bounded (OLLAMA_MAX_CONCURRENT); a second one waits, then says busy."""
    import threading as _th
    monkeypatch.setattr(settings, "OLLAMA_QUEUE_WAIT_S", 0.05)
    monkeypatch.setattr(ai, "_gen_slots", _th.BoundedSemaphore(1))
    ollama([{"role": "assistant", "content": "ok"}])
    ai._gen_slots.acquire()                                   # another answer is being generated
    try:
        import pytest
        with pytest.raises(ai.AIUnavailable) as e:
            ai.ask(db, "How busy was it this week?")
        assert "another question" in str(e.value)
    finally:
        ai._gen_slots.release()
    assert ai.ask(db, "How busy was it this week?")["answer"] == "ok"   # free again: answered


# ----------------------------------------------- camera-first GPU gate (2026-10-20) ---
def _gate(monkeypatch, reply):
    """The knowledge service's /gpu-gate answer (or an exception) for ai.gpu_gate()."""
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(200, json=reply, request=httpx.Request("GET", url))
    monkeypatch.setattr(ai.httpx, "get", get)
    monkeypatch.setattr(settings, "KB_SERVICE_KEY", "k")
    monkeypatch.setattr(settings, "OLLAMA_GPU_POLICY", "auto")
    ai._gate_cache.update(at=0.0)
    return calls


def test_auto_policy_follows_the_camera_gate(monkeypatch):
    _gate(monkeypatch, {"device": "gpu", "reason": "cameras idle for 130 s"})
    assert ai.cpu_now() is False
    _gate(monkeypatch, {"device": "cpu", "reason": "camera 5100 live - cameras first"})
    assert ai.cpu_now() is True


def test_auto_policy_unreachable_gate_means_cpu(monkeypatch):
    _gate(monkeypatch, httpx.ConnectError("down"))
    assert ai.cpu_now() is True
    assert "not reachable" in ai.gpu_gate()["reason"]


def test_gate_is_asked_at_most_every_five_seconds(monkeypatch):
    calls = _gate(monkeypatch, {"device": "gpu"})
    for _ in range(5):
        ai.cpu_now()
    assert len(calls) == 1


def test_cpu_only_still_wins_over_the_gate(monkeypatch):
    calls = _gate(monkeypatch, {"device": "gpu"})
    monkeypatch.setattr(settings, "OLLAMA_CPU_ONLY", True)
    assert ai.cpu_now() is True and calls == []


def test_answer_options_follow_the_gate(db, monkeypatch, ollama):
    fake = ollama([{"role": "assistant", "content": "a"}, {"role": "assistant", "content": "b"}])
    _gate(monkeypatch, {"device": "cpu"})
    monkeypatch.setattr(ai.httpx, "get", lambda url, headers=None, timeout=None: httpx.Response(
        200, json={"device": "cpu"} if url.endswith("/gpu-gate") else {"models": [{"name": "qwen2.5:3b"}, {"name": "qwen2.5:1.5b"}]},
        request=httpx.Request("GET", url)))
    ai.ask(db, "q")
    assert fake.bodies[-1]["options"].get("num_gpu") == 0          # cameras busy: processor
    ai._gate_cache.update(at=0.0)
    monkeypatch.setattr(ai.httpx, "get", lambda url, headers=None, timeout=None: httpx.Response(
        200, json={"device": "gpu"} if url.endswith("/gpu-gate") else {"models": [{"name": "qwen2.5:3b"}, {"name": "qwen2.5:1.5b"}]},
        request=httpx.Request("GET", url)))
    ai.ask(db, "q")
    assert "num_gpu" not in fake.bodies[-1]["options"]            # cameras idle: graphics card
