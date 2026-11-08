"""
Robot motion state without a robot: synthetic joint telemetry at 50 Hz.

    py -m pytest test_robot_state.py -q
"""
import math

from robot_state import MotionConfig, RobotMotion, Sample, home_state

HZ = 50
HOME = [0.0, -1.57, 1.57, -1.57, -1.57, 0.0]


def feed(m, t0, seconds, q_of_t, with_qd=True):
    ev, t = [], t0
    prev = None
    for k in range(int(seconds * HZ)):
        t = t0 + k / HZ
        q = q_of_t(t)
        qd = None
        if with_qd:
            qd = [0.0] * 6 if prev is None else [(a - b) * HZ for a, b in zip(q, prev)]
        prev = q
        ev += m.update(Sample(t, q, qd))
    return ev, t


def kinds(ev):
    return [e.kind for e in ev]


def test_one_joint_move_is_detected_and_logged_once():
    m = RobotMotion()
    ev, t = feed(m, 0.0, 1.0, lambda t: HOME)
    assert m.state == "STATIONARY" and ev == []
    # J4 turns 12.3 degrees in 1 s, everything else still.
    target = math.radians(12.3)
    ramp = lambda t: HOME[:3] + [HOME[3] + target * min(1.0, max(0.0, t - 1.0))] + HOME[4:]
    ev, t = feed(m, 1.0, 3.0, ramp)
    assert kinds(ev) == ["MOVEMENT_STARTED", "JOINT_MOVED", "MOVEMENT_STOPPED"]
    jm = ev[1]
    assert jm.joint == 3 and abs(jm.detail["delta_deg"] - 12.3) < 0.2
    assert ev[0].detail["joints"] == ["J4"]
    assert m.state == "STATIONARY"


def test_noise_never_makes_it_move():
    m = RobotMotion()
    noisy = lambda t: [q + 0.0002 * math.sin(97 * t + i) for i, q in enumerate(HOME)]
    ev, _ = feed(m, 0.0, 5.0, noisy)
    assert ev == [] and m.state == "STATIONARY"


def test_small_rotation_with_little_tcp_change_still_counts():
    m = RobotMotion()
    feed(m, 0.0, 0.5, lambda t: HOME)
    # J6 (the wrist flange) turns 3 degrees: the tool tip hardly moves.
    ev, _ = feed(m, 0.5, 2.0, lambda t: HOME[:5] + [math.radians(3) * min(1.0, max(0.0, (t - 0.5) * 2))])
    assert "JOINT_MOVED" in kinds(ev) and [e.joint for e in ev if e.kind == "JOINT_MOVED"] == [5]


def test_works_without_velocities():
    m = RobotMotion()
    feed(m, 0.0, 0.5, lambda t: HOME, with_qd=False)
    ev, _ = feed(m, 0.5, 2.5, lambda t: [HOME[0] + 0.3 * min(1.0, max(0.0, t - 0.5))] + HOME[1:], with_qd=False)
    assert kinds(ev) == ["MOVEMENT_STARTED", "JOINT_MOVED", "MOVEMENT_STOPPED"]


def test_telemetry_loss_is_stale_not_stationary_and_recovers():
    m = RobotMotion(MotionConfig(stale_s=2.0))
    _, t = feed(m, 0.0, 1.0, lambda t: HOME)
    assert m.tick(t + 1.0) == []
    ev = m.tick(t + 2.5)
    assert kinds(ev) == ["TELEMETRY_STALE"] and m.state == "TELEMETRY_STALE"
    assert m.tick(t + 3.0) == []                                       # once, not repeatedly
    ev = m.update(Sample(t + 4.0, HOME, [0.0] * 6))
    assert kinds(ev) == ["TELEMETRY_RESTORED"] and m.state == "STATIONARY"


def test_home_states():
    assert home_state(None, HOME)["home"] == "UNKNOWN"
    assert home_state(HOME, None)["home"] == "UNKNOWN"
    assert home_state(HOME, HOME)["home"] == "HOME"
    near = HOME[:2] + [HOME[2] + math.radians(3)] + HOME[3:]
    assert home_state(near, HOME)["home"] == "NEAR_HOME"
    far = HOME[:2] + [HOME[2] + math.radians(20)] + HOME[3:]
    h = home_state(far, HOME)
    assert h["home"] == "NOT_HOME" and h["worst_joint"] == "J3" and abs(h["worst_deg"] - 20) < 0.01


def test_a_movement_is_recorded_for_replay():
    m = RobotMotion()
    feed(m, 0.0, 0.5, lambda t: HOME)
    target = math.radians(20)
    ev, _ = feed(m, 0.5, 2.5, lambda t: [HOME[0] + target * min(1.0, max(0.0, t - 0.5))] + HOME[1:])
    stop = [e for e in ev if e.kind == "MOVEMENT_STOPPED"][0]
    tr = stop.detail["trajectory"]
    assert len(tr["t"]) == len(tr["q"]) >= 10                      # ~10 a second
    assert tr["t"][0] == 0.0 and tr["t"] == sorted(tr["t"])
    assert abs(tr["q"][0][0] - HOME[0]) < 0.01                       # starts where it was still
    assert abs(tr["q"][-1][0] - (HOME[0] + target)) < 0.01           # ends where it stopped
