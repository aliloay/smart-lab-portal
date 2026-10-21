"""PTZ power-on (2026-10-21): camera 2 swept, stopped tilted up, a view check re-aligned its
boxes to that view, then staff tilted it back. Right after the stream (re)connects the view
check must neither take an anchor nor move a box."""
import threading
import time
import types

import numpy as np

import realign
import security_vision as sv


def _svc(state="STREAMING", since_ago=10.0):
    s = types.SimpleNamespace(
        camera=types.SimpleNamespace(state=state, state_since=time.time() - since_ago,
                                     latest=lambda: (np.zeros((48, 64, 3), np.uint8), time.time())),
        cfg={"zones": [{"id": 1, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}], "door": None},
        lock=threading.Lock(), tracks=[], view_anchor=None, view_before={}, view_applied={},
        view_anchor_boxes={}, view_unstable=False, VIEW_STARTUP_QUIET_S=sv.Service.VIEW_STARTUP_QUIET_S)
    s.view_settling = lambda now: sv.Service.view_settling(s, now)
    return s


def test_quiet_right_after_connect():
    assert _svc(since_ago=10).view_settling(time.time())


def test_quiet_while_not_streaming():
    assert _svc(state="RECONNECTING", since_ago=999).view_settling(time.time())


def test_checks_resume_after_the_quiet_time():
    assert not _svc(since_ago=sv.Service.VIEW_STARTUP_QUIET_S + 1).view_settling(time.time())


def test_no_anchor_and_no_move_during_startup(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("view touched during the startup quiet time")
    monkeypatch.setattr(realign, "make_reference", boom)
    monkeypatch.setattr(realign, "compare", boom)
    s = _svc(since_ago=30)
    sv.Service._check_view(s)
    assert s.view_anchor is None
