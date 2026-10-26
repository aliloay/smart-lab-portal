"""Voice service HTTP layer with a fake engine (no models): key, limits, one at a time, nothing stored.
    py -m pytest -q tools/voice      (the real models: see README.md, measured separately)"""
import json
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

import voice_service as V

KEY = "k" * 32


class FakeVoice(V.Voice):
    def __init__(self):
        super().__init__()
        self.stt = self.tts = object()

    def transcribe_pcm(self, pcm):
        time.sleep(0.3)
        return "is the lab free"


@pytest.fixture(scope="module")
def url():
    v = FakeVoice()
    v.speak = lambda text: (200, b"RIFF" + text.encode()) if text else (422, {"error": "no text"})
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    threading.Thread(target=V.serve, args=(v, KEY, port), daemon=True).start()
    time.sleep(0.3)
    V.decode = lambda data: np.zeros(int(16000 * (len(data) / 1000)), dtype=np.float32)   # 1000 bytes = 1 s
    return f"http://127.0.0.1:{port}"


def post(url, path, body, key=KEY):
    req = urllib.request.Request(url + path, data=body, method="POST", headers={"X-Voice-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_key_required(url):
    assert post(url, "/transcribe", b"x" * 2000, key="wrong")[0] == 401


def test_transcribe_and_short_audio(url):
    code, body = post(url, "/transcribe", b"x" * 2000)
    assert code == 200 and json.loads(body)["text"] == "is the lab free"
    code, body = post(url, "/transcribe", b"x" * 100)              # 0.1 s: nothing to transcribe
    assert code == 200 and json.loads(body)["text"] == ""


def test_too_long_is_refused(url):
    assert post(url, "/transcribe", b"x" * 40000)[0] == 413          # 40 s > 30 s


def test_one_transcription_at_a_time(url):
    res = []
    ts = [threading.Thread(target=lambda: res.append(post(url, "/transcribe", b"x" * 2000)[0])) for _ in range(3)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(res).count(200) >= 1 and 429 in res


def test_speak_returns_wav(url):
    code, body = post(url, "/speak", json.dumps({"text": "hello"}).encode())
    assert code == 200 and body.startswith(b"RIFF")


def test_spoken_text_is_capped():
    v = V.Voice(); v.tts = None
    assert v.speak("")[0] == 422 and v.speak("hi")[0] == 503
