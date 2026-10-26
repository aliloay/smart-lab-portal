"""Voice routes (2026-10-26): audio passes through to the local voice service, nothing is stored; the text then
goes through the normal assistant path. The voice service is faked."""
import pytest

from app.api.routes import voice
from tests.conftest import auth_headers


class FakeResp:
    def __init__(self, code, body=None, content=b""):
        self.status_code, self._body, self.content = code, body, content or (b"{}" if body is not None else b"")

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, transcribe=(200, {"text": "Is the lab free?", "ms": 900}), speak=(200, b"RIFFwav")):
        self.t, self.s, self.calls = transcribe, speak, []

    def get(self, url, timeout=None):
        return FakeResp(200, {"ok": True, "stt": "base.en", "tts": "en_US-lessac-medium.onnx"})

    def post(self, url, content=None, json=None, headers=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], headers.get("X-Voice-Key"), len(content or b"")))
        if url.endswith("/transcribe"):
            return FakeResp(self.t[0], self.t[1])
        return FakeResp(self.s[0], content=self.s[1])


@pytest.fixture
def svc(monkeypatch):
    c = FakeClient()
    monkeypatch.setattr(voice, "KEY", "k" * 32)
    monkeypatch.setattr(voice, "_client", c)
    voice._health.update(t=0.0, v=None)
    return c


def test_voice_needs_sign_in(client, svc):
    assert client.post("/api/voice/transcribe", content=b"abc").status_code == 401
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 401


def test_status_transcribe_and_speak(client, staff, svc):
    h = auth_headers(client, staff.email)
    assert client.get("/api/voice/status", headers=h).json() == {"stt": True, "tts": True, "model": "base.en",
                                                                 "voice": "en_US-lessac-medium.onnx"}
    r = client.post("/api/voice/transcribe", content=b"\x1aE\xdf\xa3webm", headers={**h, "Content-Type": "audio/webm"})
    assert r.status_code == 200 and r.json()["text"] == "Is the lab free?"
    w = client.post("/api/voice/speak", json={"text": "The lab is free."}, headers=h)
    assert w.status_code == 200 and w.headers["content-type"] == "audio/wav" and w.content == b"RIFFwav"
    assert [c[0] for c in svc.calls] == ["transcribe", "speak"] and all(c[1] == "k" * 32 for c in svc.calls)


def test_student_can_use_voice_too(client, alice, svc):
    h = auth_headers(client, alice.email)
    assert client.post("/api/voice/transcribe", content=b"x" * 100, headers=h).status_code == 200


def test_limits_and_busy(client, staff, svc, monkeypatch):
    h = auth_headers(client, staff.email)
    assert client.post("/api/voice/transcribe", content=b"x" * (voice.MAX_AUDIO + 1), headers=h).status_code == 413
    assert client.post("/api/voice/speak", json={"text": "x" * 601}, headers=h).status_code == 422
    svc.t = (429, {"error": "busy"})
    r = client.post("/api/voice/transcribe", content=b"x" * 100, headers=h)
    assert r.status_code == 429 and "try again" in r.json()["detail"]


def test_not_configured_says_so(client, staff, monkeypatch):
    monkeypatch.setattr(voice, "KEY", "")
    h = auth_headers(client, staff.email)
    assert client.get("/api/voice/status", headers=h).json()["stt"] is False
    assert client.post("/api/voice/transcribe", content=b"x", headers=h).status_code == 503
