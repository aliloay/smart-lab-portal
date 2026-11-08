"""Collector safety tests - a FAKE RTDE receiver, no robot, nothing sent anywhere.

    py -3.12 -m pytest -q tools/robot_monitor
"""
import math
import sys
import types

import pytest

sys.modules.setdefault("rtde_receive", types.SimpleNamespace(RTDEReceiveInterface=None))
import robot_collector as rc  # noqa: E402
from robot_state import Sample  # noqa: E402

UP = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]


class FakeRx:
    """Behaves like ur_rtde: getters return the last values even after the link is gone."""
    def __init__(self):
        self.connected, self.ts, self.q = True, 100.0, list(UP)

    def isConnected(self): return self.connected
    def getTimestamp(self): return self.ts
    def getActualQ(self): return list(self.q)
    def getActualQd(self): return [0.0] * 6
    def getActualTCPPose(self): return [0.0] * 6
    def getRobotMode(self): return 7
    def getSafetyMode(self): return 1
    def getRuntimeState(self): return 1
    def getSpeedScaling(self): return 1.0
    def disconnect(self): pass


def ur_source(rx):
    src = rc.URSource.__new__(rc.URSource)
    src.rx = rx
    return src


def test_read_refuses_values_after_link_lost():
    rx = FakeRx()
    src = ur_source(rx)
    assert src.read().q == UP
    rx.connected = False
    with pytest.raises(ConnectionError):
        src.read()


@pytest.mark.parametrize("q,ok", [
    (UP, True),
    (UP[:5], False),                                   # joint missing
    (UP + [0.0], False),                               # one too many
    (UP[:5] + [math.nan], False),
    (UP[:5] + [math.inf], False),
    (UP[:5] + [7 * math.pi], False),                   # beyond +-2 turns: not an angle in rad
    (UP[:5] + [2 * math.pi], True),                    # UR joints allow +-360 deg
])
def test_valid(q, ok):
    assert rc.valid(Sample(t=0, q=list(q), qd=[0.0] * 6)) is ok


def test_valid_rejects_bad_velocities():
    assert not rc.valid(Sample(t=0, q=list(UP), qd=[0.0] * 5 + [math.nan]))


class Stop(BaseException):
    pass


def run_collector(script, monkeypatch, stale_s=0.3):
    """Drive Collector.run with a scripted source; returns the telemetry bodies posted."""
    args = types.SimpleNamespace(source="ur", robot="0.0.0.0", device="UR5E_TEST", model="UR5e", name="", asset=None,
                                 lab="LAB_01", portal="http://127.0.0.1:9", hz=50.0, report_s=0.0, stale_s=stale_s,
                                 max_minutes=0)
    c = rc.Collector(args)
    posted = []
    monkeypatch.setattr(c, "post", lambda path, body, timeout=2.0: posted.append((path, body)) or True)
    clock = {"t": 1000.0}
    monkeypatch.setattr(rc.time, "time", lambda: clock["t"])
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)
    steps = iter(script)

    class Src:
        name = "RTDE"
        def read(self):
            try:
                dt, sample = next(steps)
            except StopIteration:
                raise Stop
            clock["t"] += dt
            if isinstance(sample, Exception):
                raise sample
            return sample
        def close(self): pass

    c.source = Src()
    monkeypatch.setattr(c, "open_source", lambda: Src())
    with pytest.raises(Stop):
        c.run()
    return c, [b for p, b in posted if p == "/robots/telemetry"]


def s(ts, q=UP):
    return Sample(t=ts, q=list(q), qd=[0.0] * 6, extra={})


def test_frozen_controller_timestamp_becomes_stale_not_stationary(monkeypatch):
    # 5 fresh samples, then the same controller timestamp for 1 s (link frozen, values repeated)
    script = [(0.02, s(100 + i * 0.002)) for i in range(5)] + [(0.05, s(100.008))] * 20
    c, tele = run_collector(script, monkeypatch)
    assert tele[4]["state"] == "STATIONARY"
    assert tele[-1]["state"] == "TELEMETRY_STALE"
    assert c.motion.samples == 5                       # repeats were never fed as new data


def test_invalid_samples_are_ignored_and_counted(monkeypatch):
    bad = UP[:5] + [math.nan]
    script = [(0.02, s(100.0)), (0.02, s(100.002, bad)), (0.02, s(100.004, UP[:4])), (0.02, s(100.006))]
    c, tele = run_collector(script, monkeypatch)
    assert c.rejected == 2
    assert all(b["q"] is None or all(math.isfinite(v) for v in b["q"]) for b in tele)
    assert c.motion.samples == 2


def test_link_loss_reconnects_and_never_posts_old_pose_as_fresh(monkeypatch):
    script = [(0.02, s(100.0)), (0.02, ConnectionError("RTDE link lost"))] + [(0.5, s(100.0))]
    c, tele = run_collector(script, monkeypatch)
    # after the drop the reopened source repeats the old controller timestamp: still not fresh
    assert c.motion.samples == 1


def test_controller_timestamp_kept_for_diagnosis(monkeypatch):
    c, tele = run_collector([(0.02, s(123.456))], monkeypatch)
    assert tele[-1]["extra"]["controller_t"] == 123.456
