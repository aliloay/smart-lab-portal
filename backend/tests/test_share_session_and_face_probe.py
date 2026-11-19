"""
2026-11-19: (1) a presenter's frame is stored only in the share it was checked against - the upload body is read after
the check, and an old presenter must not appear in a share that started meanwhile; (2) the face server counts as up
only on a genuine /health answer (200 + {"status": "ok"}), not on any reply under 500, a timeout or a malformed body.
"""
import threading

import pytest

from app.services import devices, pc_control

JPEG = b"\xff\xd8" + b"x" * 100


@pytest.fixture(autouse=True)
def _clean_share():
    pc_control.broadcast_reset()
    yield
    pc_control.broadcast_reset()


def test_frame_for_an_older_share_is_refused():
    old = pc_control.broadcast_start("Admin", 1, "master_pc")["session"]
    assert pc_control.broadcast_put(JPEG, old) is True
    new = pc_control.broadcast_start("Student", 2, "pc", device_id=7)["session"]
    assert new == old + 1
    assert pc_control.broadcast_put(JPEG, old) is False          # the master PC's late frame
    assert pc_control.broadcast_frame() is None                   # the new share shows nothing of it
    assert pc_control.broadcast_put(JPEG, new) is True
    assert pc_control.broadcast_frame() == JPEG


def test_frame_after_stop_is_refused():
    s = pc_control.broadcast_start("Admin", 1, "browser")["session"]
    pc_control.broadcast_stop()
    assert pc_control.broadcast_put(JPEG, s) is False


class _R:
    def __init__(self, code, body=None, bad_json=False):
        self.status_code, self._body, self._bad = code, body, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._body


@pytest.mark.parametrize("resp,ok", [
    (_R(200, {"status": "ok", "model_trained": True}), True),
    (_R(200, {"status": "starting"}), False),
    (_R(200, bad_json=True), False),                              # malformed body
    (_R(200, ["not", "a", "dict"]), False),
    (_R(404, {"status": "ok"}), False),                           # another program on the port
    (_R(401), False),
    (_R(503, {"status": "ok"}), False),
])
def test_face_health_needs_a_genuine_answer(resp, ok):
    assert devices._face_health_ok(resp) is ok


def test_probe_timeout_is_down_and_recovery_is_up(monkeypatch):
    import httpx

    class _Now(threading.Thread):                                  # run the background probe inline
        def start(self):
            self.run()
    monkeypatch.setattr(threading, "Thread", _Now)
    state = {"at": 0.0, "ok": None, "busy": False}

    def boom(*a, **k):
        raise httpx.TimeoutException("timeout")
    monkeypatch.setattr(httpx, "get", boom)
    assert devices._probe(state, "http://x/health", devices._face_health_ok) is False
    state["at"] = 0.0                                              # cache expired
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _R(200, {"status": "ok"}))
    assert devices._probe(state, "http://x/health", devices._face_health_ok) is True
