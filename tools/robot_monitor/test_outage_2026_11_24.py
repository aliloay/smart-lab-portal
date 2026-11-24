"""Lab 24 Nov 2026: a blocking reconnect must not delay the outage or re-send the old pose as fresh."""
import threading
import time
import types

import pytest

import robot_collector as rc
from robot_state import Sample

Q = [0.1] * 6


class Stop(BaseException):
    pass


def test_blocked_reconnect_goes_stale_in_time_and_never_posts_old_pose(monkeypatch):
    args = types.SimpleNamespace(source="ur", robot="0.0.0.0", device="UR5E_T", model="UR5e", name="", asset=None,
                                 lab="LAB_01", portal="http://127.0.0.1:9", hz=50.0, report_s=0.1, stale_s=1.5,
                                 max_minutes=0)
    c = rc.Collector(args)
    t0, posted, release = time.time(), [], threading.Event()

    def post(path, body, timeout=2.0):
        if path == "/robots/telemetry":
            posted.append((time.time() - t0, body["state"]))
            if body["state"] == "TELEMETRY_STALE":
                raise Stop
        return True
    monkeypatch.setattr(c, "post", post)
    monkeypatch.setattr(c, "flush", lambda: None)

    class Src:
        name = "RTDE"
        n = 0

        def read(self):
            Src.n += 1
            if Src.n > 5:
                raise ConnectionError("link lost")
            return Sample(t=100.0 + Src.n, q=list(Q), qd=[0.0] * 6, extra={})

        def close(self):
            pass
    c.source = Src()
    monkeypatch.setattr(c, "open_source", lambda: release.wait(30))      # an unreachable robot blocks the connect
    with pytest.raises(Stop):
        c.run()
    release.set()
    lost = 0.1
    assert posted[-1][1] == "TELEMETRY_STALE" and posted[-1][0] < lost + 1.5 + 0.8
    assert all(t < lost + c.QUIET_S + 0.3 for t, s in posted[:-1])


def test_exit_in_the_connect_thread_still_ends_the_collector(monkeypatch):
    args = types.SimpleNamespace(source="ur", robot="", device="U", model="", name="", asset=None, lab="L",
                                 portal="http://127.0.0.1:9", hz=50.0, report_s=0.1, stale_s=1.5, max_minutes=0)
    with pytest.raises(SystemExit):
        rc.Collector(args).run()
