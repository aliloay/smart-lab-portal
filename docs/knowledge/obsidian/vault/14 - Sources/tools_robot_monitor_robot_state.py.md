---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/robot_monitor/robot_state.py"
source_hash: "0e519c6da629c7f0b2d31f309b495de5cd6430d13c4ba7acf3f2040f41c8ede0"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/robot_monitor/robot_state.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[tools_robot_monitor_test_collector.py]] - tests
- [[tools_robot_monitor_test_fanuc_source.py]] - tests
- [[tools_robot_monitor_test_robot_state.py]] - tests
- [[docs_ROBOTS.md]] - mentioned by docs
- [[tools_robot_monitor_robot_collector.py]] - imports

```py
"""
Robot motion state from joint telemetry - READ-ONLY monitoring, any 6-axis arm
(UR5e over RTDE, FANUC once its read-only interface is confirmed, others).

Per joint, every sample:

    moving   |qd| above start_velocity, or the joint moved more than
             start_delta since it was last still (works without qd too)
    still    |qd| below stop_velocity AND no change above stop_delta for
             settle_s - hysteresis: no MOVING/STOPPED flicker on noise

Robot:   MOVING (any joint moving) > STATIONARY;  TELEMETRY_STALE when no
         sample for stale_s (never "stationary" just because data stopped);
         UNKNOWN before the first sample.

Events (state transitions only, never per sample):

    MOVEMENT_STARTED / MOVEMENT_STOPPED   the robot; STOPPED carries the
                                           movement's path (10 samples a second,
                                           at most 60 s) for 3D replay
    JOINT_MOVED                            one joint, after it settles:
                                           from / to / delta (rad and deg),
                                           peak velocity, duration
    TELEMETRY_STALE / TELEMETRY_RESTORED

A single joint moving while the tool tip barely moves is still reported
(joint deltas, not only TCP distance). Thresholds are configurable and NOT
tuned on the real robots yet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MotionConfig:
    start_velocity: float = 0.02       # rad/s: a joint faster than this is moving
    stop_velocity: float = 0.005       # rad/s: slower than this may be still
    start_delta: float = 0.002         # rad (~0.11 deg) moved since last still = moving
    stop_delta: float = 0.0005         # rad: changes below this are noise
    settle_s: float = 0.5              # still this long before "stopped"
    min_event_delta: float = 0.0017    # rad (~0.1 deg): smaller completed moves are not logged
    stale_s: float = 2.0               # no sample this long = TELEMETRY_STALE
    path_every_s: float = 0.1          # movement path kept at this interval for replay ...
    path_max: int = 600                # ... at most this many samples (60 s)


@dataclass
class Sample:
    t: float                           # source timestamp (s); arrival time used if the source has none
    q: list                            # 6 joint positions, rad
    qd: Optional[list] = None          # 6 joint velocities, rad/s (None if the source has none)
    tcp: Optional[list] = None         # x, y, z (m), rx, ry, rz
    extra: dict = field(default_factory=dict)   # robot_mode, safety_mode, runtime_state ... as reported


@dataclass
class JointState:
    moving: bool = False
    still_since: Optional[float] = None
    rest_q: Optional[float] = None     # where it was when last still
    move_started: Optional[float] = None
    peak_v: float = 0.0
    last_q: Optional[float] = None


@dataclass
class RobotEvent:
    kind: str
    t: float
    joint: Optional[int] = None        # 0-5 (J1 = 0)
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "t": round(self.t, 3), "joint": self.joint, "detail": self.detail}


class RobotMotion:
    def __init__(self, cfg: Optional[MotionConfig] = None, joints: int = 6):
        self.cfg = cfg or MotionConfig()
        self.joints = [JointState() for _ in range(joints)]
        self.state = "UNKNOWN"
        self.last_sample: Optional[Sample] = None
        self.last_arrival: Optional[float] = None
        self.stale = False
        self.samples = 0
        self.path: list = []                       # (t, q) of the movement in progress

    # -- feeding --------------------------------------------------------------
    def update(self, s: Sample, arrival: Optional[float] = None) -> list[RobotEvent]:
        c, ev = self.cfg, []
        arrival = s.t if arrival is None else arrival
        if self.stale:
            ev.append(RobotEvent("TELEMETRY_RESTORED", s.t, detail={"after_s": round(arrival - (self.last_arrival or arrival), 2)}))
            self.stale = False
        prev = self.last_sample
        dt = (s.t - prev.t) if prev else 0.0
        any_moving = False
        for i, (j, q) in enumerate(zip(self.joints, s.q)):
            v = abs(s.qd[i]) if s.qd is not None else (abs(q - j.last_q) / dt if (j.last_q is not None and dt > 0) else 0.0)
            if j.rest_q is None:
                j.rest_q, j.still_since = q, s.t
            changed = j.last_q is not None and abs(q - j.last_q) > c.stop_delta
            if not j.moving:
                if v > c.start_velocity or abs(q - j.rest_q) > c.start_delta:
                    j.moving, j.move_started, j.peak_v, j.still_since = True, prev.t if prev else s.t, v, None
            else:
                j.peak_v = max(j.peak_v, v)
                if v < c.stop_velocity and not changed:
                    j.still_since = j.still_since or s.t
                    if s.t - j.still_since >= c.settle_s:
                        delta = q - j.rest_q
                        if abs(delta) >= c.min_event_delta:
                            ev.append(RobotEvent("JOINT_MOVED", s.t, i, {
                                "from_rad": round(j.rest_q, 5), "to_rad": round(q, 5),
                                "delta_rad": round(delta, 5), "delta_deg": round(math.degrees(delta), 2),
                                "peak_velocity_rad_s": round(j.peak_v, 4),
                                "duration_s": round(j.still_since - (j.move_started or j.still_since), 2)}))
                        j.moving, j.rest_q, j.peak_v, j.move_started = False, q, 0.0, None
                else:
                    j.still_since = None
            j.last_q = q
            any_moving = any_moving or j.moving
        new_state = "MOVING" if any_moving else "STATIONARY"
        if new_state == "MOVING" and self.state != "MOVING":
            self.path = [(prev.t, list(prev.q))] if prev else []
        if new_state == "MOVING" or (self.state == "MOVING" and new_state != "MOVING"):
            if (not self.path or s.t - self.path[-1][0] >= c.path_every_s) and len(self.path) < c.path_max:
                self.path.append((s.t, list(s.q)))
        if new_state != self.state:
            if new_state == "MOVING":
                ev.append(RobotEvent("MOVEMENT_STARTED", s.t, detail={
                    "joints": [f"J{i + 1}" for i, j in enumerate(self.joints) if j.moving]}))
            elif self.state == "MOVING":
                t0 = self.path[0][0] if self.path else s.t
                ev.append(RobotEvent("MOVEMENT_STOPPED", s.t, detail={
                    "duration_s": round(s.t - t0, 2),
                    "trajectory": {"t": [round(t - t0, 2) for t, _ in self.path],
                                   "q": [[round(v, 4) for v in q] for _, q in self.path]}}))
                self.path = []
            self.state = new_state
        self.last_sample, self.last_arrival = s, arrival
        self.samples += 1
        return ev

    def tick(self, now: float) -> list[RobotEvent]:
        """Call regularly even when no sample arrives: detects a telemetry outage."""
        if self.last_arrival is None or self.stale:
            return []
        if now - self.last_arrival > self.cfg.stale_s:
            self.stale = True
            was = self.state
            self.state = "TELEMETRY_STALE"
            for j in self.joints:                     # unknown now - restart cleanly afterwards
                j.moving, j.still_since, j.move_started = False, None, None
            return [RobotEvent("TELEMETRY_STALE", now, detail={"last_sample_age_s": round(now - self.last_arrival, 2),
                                                               "state_before": was})]
        return []

    # -- reading ------------------------------------------------------------------
    def snapshot(self, now: float) -> dict:
        s = self.last_sample
        return {"state": self.state,
                "telemetry_age_ms": None if self.last_arrival is None else round((now - self.last_arrival) * 1000),
                "q": None if s is None else [round(v, 5) for v in s.q],
                "qd": None if s is None or s.qd is None else [round(v, 5) for v in s.qd],
                "tcp": None if s is None or s.tcp is None else [round(v, 5) for v in s.tcp],
                "joints_moving": [j.moving for j in self.joints],
                "extra": {} if s is None else s.extra}


# --------------------------------------------------------------- home ---
def home_state(q: Optional[list], home_q: Optional[list], tolerance_rad: float = math.radians(1.0),
               near_rad: float = math.radians(5.0)) -> dict:
    """HOME / NEAR_HOME / NOT_HOME (per-joint |q - home|) or UNKNOWN without data/calibration."""
    if not q or not home_q or len(q) != len(home_q):
        return {"home": "UNKNOWN", "deviation_rad": None}
    dev = [abs(a - b) for a, b in zip(q, home_q)]
    worst = max(dev)
    st = "HOME" if worst <= tolerance_rad else "NEAR_HOME" if worst <= near_rad else "NOT_HOME"
    return {"home": st, "deviation_rad": [round(d, 5) for d in dev],
            "worst_joint": f"J{dev.index(worst) + 1}", "worst_deg": round(math.degrees(worst), 2)}

```
