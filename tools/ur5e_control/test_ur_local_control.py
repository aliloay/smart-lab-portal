"""UR5e Local-mode Home / Stop - mocked controller, nothing reaches a robot.
    py -3.12 -m pytest -q tools/ur5e_control"""
import math
import socket
import threading
import time

import pytest

import ur_local_control as U

HOME_RAD = [math.radians(v) for v in U.HOME_Q_DEG]
NEAR = [math.radians(v + 3.0) for v in U.HOME_Q_DEG]         # 3 deg from Home: inside the verified zone
FAR = [math.radians(v + 40.0) for v in U.HOME_Q_DEG]


def state(**kw):
    s = {"t": time.time(), "remote": False, "robot_mode": "RUNNING", "safety": "NORMAL",
         "program_state": "PLAYING portal_control.urp", "loaded_program": "/programs/portal_control.urp",
         "q": NEAR, "qd": [0.0] * 6, "link": "connected"}
    s.update(kw)
    return s


class FakeDash:
    def __init__(self, s): self.s = s
    def read(self): return {k: self.s[k] for k in ("remote", "robot_mode", "safety", "program_state", "loaded_program")}


class FakeRtde:
    def __init__(self, s): self.s = s
    def getActualQ(self): return self.s["q"]
    def getActualQd(self): return self.s["qd"]


class FakeLink:
    def __init__(self, ok=True): self.calls, self.ok = [], ok
    def isConnected(self): return self.ok
    def isProgramRunning(self): return self.ok
    def moveJ(self, q, v, a, asynchronous): self.calls.append(("moveJ", q, v, a, asynchronous))
    def stopJ(self, a, asynchronous): self.calls.append(("stopJ", a, asynchronous))


def agent(mode="dry_run", **kw):
    s = state(**kw)
    link = FakeLink(kw.get("link", "connected") == "connected") if mode == "live" else None
    return U.Agent(U.Config(mode=mode), dash=FakeDash(s), rtde_r=FakeRtde(s), link=link), link


def test_local_mode_portal_program_home_is_dry_run_only():
    a, _ = agent()
    r = a.command("home", "c1", confirmed=True)
    assert r["status"] == "DRY_RUN" and not r["sent"] and "nothing sent" in r["reason"]
    assert r["controller"]["control_mode"] == "LOCAL" and r["controller"]["driver"] == "PORTAL_PROGRAM"


def test_home_needs_confirmation():
    a, _ = agent()
    r = a.command("home", "c1", confirmed=False)
    assert r["status"] == "REJECTED" and "confirmed" in r["reason"]


def test_idle_local_mode_home_says_press_play_on_pendant():
    a, _ = agent(program_state="STOPPED", link="dry_run")
    r = a.command("home", "c1", confirmed=True)
    assert r["status"] == "REJECTED" and "Play on the teach pendant" in r["reason"]


def test_stop_cannot_end_another_program_in_local_mode():
    a, _ = agent(program_state="PLAYING pick_place.urp", loaded_program="/programs/pick_place.urp")
    r = a.command("stop", "s1")
    assert r["status"] == "UNSUPPORTED" and "Remote mode" in r["reason"] and "pendant" in r["reason"]


def test_stop_cannot_stop_pendant_jogging():
    a, _ = agent(program_state="STOPPED", qd=[0.2, 0, 0, 0, 0, 0])
    r = a.command("stop", "s1")
    assert r["status"] == "UNSUPPORTED" and r["controller"]["driver"] == "PENDANT_MANUAL" and "E-stop" in r["reason"]


def test_home_refused_from_unverified_start_pose():
    a, _ = agent(q=FAR)
    r = a.command("home", "c1", confirmed=True)
    assert r["status"] == "REJECTED" and "verified" in r["reason"]


def test_home_refused_while_moving_or_unsafe():
    a, _ = agent(qd=[0, 0.05, 0, 0, 0, 0])
    assert "moving" in a.command("home", "c1", confirmed=True)["reason"]
    a, _ = agent(safety="PROTECTIVE_STOP")
    assert "PROTECTIVE_STOP" in a.command("home", "c2", confirmed=True)["reason"]


def test_stale_feedback_blocks_home():
    a, _ = agent(t=time.time() - 10)
    a.rtde_r = None                                     # RTDE unreachable -> no joints at all
    a.dash = FakeDash(state())
    import builtins
    real = builtins.__import__

    def no_rtde(name, *args, **kw):
        if name == "rtde_receive":
            raise ImportError("no robot")
        return real(name, *args, **kw)
    builtins.__import__ = no_rtde
    try:
        r = a.command("home", "c1", confirmed=True)
    finally:
        builtins.__import__ = real
    assert r["status"] == "REJECTED" and "Fresh joint feedback" in r["reason"]


def test_live_home_sends_one_movej_to_verified_pose_and_stop_sends_stopj():
    a, link = agent(mode="live")
    r = a.command("home", "h1", confirmed=True)
    assert r["status"] == "REQUESTED" and r["sent"] and "feedback" in r["reason"]
    kind, q, v, acc, asyn = link.calls[0]
    assert kind == "moveJ" and q == pytest.approx(HOME_RAD) and v == U.HOME_SPEED and acc == U.HOME_ACCEL and asyn
    r = a.command("stop", "s1")
    assert r["status"] == "REQUESTED" and link.calls[1] == ("stopJ", U.STOP_DECEL, False)


def test_stop_latches_home_until_recovery_and_recovery_refused_while_moving():
    a, link = agent(mode="live")
    a.command("stop", "s1")
    r = a.command("home", "h1", confirmed=True)
    assert r["status"] == "REJECTED" and "latched" in r["reason"] and len(link.calls) == 1
    a.rtde_r.s["qd"] = [0.1] * 6
    assert a.recover()["ok"] is False
    a.rtde_r.s["qd"] = [0.0] * 6
    assert a.recover()["ok"] is True
    assert a.command("home", "h2", confirmed=True)["status"] == "REQUESTED"


def test_live_mode_without_connected_program_sends_nothing():
    a, link = agent(mode="live", link="waiting")
    assert a.command("home", "h1", confirmed=True)["status"] == "REJECTED"
    assert a.command("stop", "s1")["status"] == "UNSUPPORTED"
    assert link.calls == []


def test_off_mode_unavailable():
    r = U.decide("home", state(), U.Config(mode="off"), True)
    assert r["status"] == "UNAVAILABLE"


def test_remote_mode_stop_defers_to_dashboard_path():
    r = U.decide("stop", state(remote=True, program_state="PLAYING other.urp", loaded_program="other.urp"), U.Config())
    assert r["status"] == "UNSUPPORTED" and "Dashboard" in r["reason"]


def test_dashboard_reader_only_sends_read_queries():
    """A fake Dashboard Server records every line the reader writes: only the read-only queries."""
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port, seen = srv.getsockname()[1], []
    answers = {"is in remote control": "false", "robotmode": "Robotmode: RUNNING", "safetystatus": "Safetystatus: NORMAL",
               "programState": "PLAYING portal_control.urp", "get loaded program": "Loaded program: /p/portal_control.urp",
               "PolyscopeVersion": "URSoftware 5.x"}

    def run():
        c, _ = srv.accept()
        f = c.makefile("rwb", buffering=0)
        f.write(b"Connected: Universal Robots Dashboard Server\n")
        for line in f:
            cmd = line.decode().strip(); seen.append(cmd)
            f.write((answers.get(cmd, "?") + "\n").encode())
            if len(seen) == len(answers):
                break
        c.close()
    threading.Thread(target=run, daemon=True).start()
    r = U.DashboardReader("127.0.0.1")
    import unittest.mock as m
    real = socket.create_connection
    with m.patch.object(U.socket, "create_connection", lambda addr, timeout: real(("127.0.0.1", port), timeout)):
        out = r.read()
    assert set(seen) == set(answers) and out["remote"] is False and out["robot_mode"] == "RUNNING"
    assert not {"stop", "pause", "play", "load", "power on", "power off", "brake release"} & set(seen)
