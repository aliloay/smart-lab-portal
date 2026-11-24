"""Gemini audit 24 Nov 2026: ROB-3A (lost outage report), 3B (late RTDE connection), 3C (rate across an outage)."""
import threading
import time
import types

import robot_collector as rc
from robot_state import Sample


def collector():
    return rc.Collector(types.SimpleNamespace(source="ur", robot="0.0.0.0", device="UR5E_T", model="UR5e", name="", asset=None, lab="LAB_01",
                                              portal="http://127.0.0.1:9", hz=50.0, report_s=0.1, stale_s=1.5, max_minutes=0))


def feed(c, t0, n, hz=35.0):
    for k in range(n):
        t = t0 + k / hz
        c.rate_t.append(t)
        c.motion.update(Sample(t=t, q=[0.1] * 6, qd=[0.0] * 6, extra={}), arrival=t)
    return t0 + (n - 1) / hz


def test_3a_the_outage_report_is_repeated_until_the_portal_takes_it(monkeypatch):
    c, sent, up = collector(), [], [False]
    monkeypatch.setattr(c, "post", lambda path, body, timeout=2.0: (path == "/robots/telemetry" and sent.append((body["sent_at"], body["state"])), up[0])[1])
    t = feed(c, 1000.0, 60)
    for k in range(int(100 / 0.1)):                      # 100 s without data; the portal is down for the first 40 s
        now = t + 0.1 * k
        up[0] = now - t > 40
        c.motion.tick(now)
        c.report(now)
    stale = [x for x in sent if x[1] == "TELEMETRY_STALE"]
    assert 3 <= len(stale) <= 8                          # backed off, not a storm
    assert stale[-1][0] - t > 40 and c._stale_reported   # delivered once the portal was back, then silent
    n = len(stale)
    t2 = feed(c, t + 101, 60)                            # data again: the next outage is a new report
    up[0] = True
    c.report(t2)
    for k in range(60):
        c.motion.tick(t2 + 0.1 * k)
        c.report(t2 + 0.1 * k)
    assert len([x for x in sent if x[1] == "TELEMETRY_STALE"]) == n + 1


def test_3b_a_connection_that_completes_after_the_stop_is_closed(monkeypatch):
    c, go, closed = collector(), threading.Event(), threading.Event()

    class Src:
        name = "RTDE"

        def close(self):
            closed.set()
    monkeypatch.setattr(c, "open_source", lambda: (go.wait(5), Src())[1])
    assert c._open_step() is False
    c.close()
    assert not closed.is_set()
    go.set()
    assert closed.wait(3)


def test_3b_already_open_but_not_taken_and_the_normal_source_are_closed(monkeypatch):
    c, n = collector(), []
    src = types.SimpleNamespace(name="RTDE", close=lambda: n.append(1))
    th = types.SimpleNamespace(is_alive=lambda: False)
    c._opening = (th, {"source": src})
    c.source = types.SimpleNamespace(close=lambda: n.append(2))
    c.close()
    c.close()
    assert n == [1, 2]


def test_3c_the_rate_is_of_the_present_connection_only(monkeypatch):
    c, rates = collector(), []
    monkeypatch.setattr(c, "post", lambda path, body, timeout=2.0: (path == "/robots/telemetry" and rates.append(body["rate_hz"]), True)[1])
    for _ in range(2):                                   # two outages of 50 s
        t = feed(c, 1000.0 + 60 * _, 200)
        c.report(t)
        assert abs(rates[-1] - 35) < 1
        c.rate_t.clear()                                 # what a lost connection does
        t = feed(c, t + 50, 5)
        c.report(t)
        assert rates[-1] == 0.0                          # warming up, not 3.5
        c.rate_t.clear()


def test_3c_a_lost_connection_clears_the_rate(monkeypatch):
    c = collector()

    class Stop(BaseException):
        pass
    opened = []

    def open_source():
        opened.append(1)
        if len(opened) > 1:
            raise Stop
        k = [0]

        def read():
            k[0] += 1
            if k[0] > 30:
                raise ConnectionError("gone")
            return Sample(t=float(k[0]), q=[0.1] * 6, qd=[0.0] * 6, extra={})
        return types.SimpleNamespace(name="RTDE", read=read, close=lambda: None)
    monkeypatch.setattr(c, "open_source", open_source)
    monkeypatch.setattr(c, "post", lambda *a, **k: True)
    try:
        c.run()
    except Stop:
        pass
    assert len(c.rate_t) == 0 and c.source is None
