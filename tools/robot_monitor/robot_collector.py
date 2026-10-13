"""
Robot collector - READ-ONLY. One process per robot, on the lab laptop:

    robot  --(read-only interface)-->  this collector  --HTTP-->  portal backend
                                         runs RobotMotion (robot_state.py)
                                         at the robot's data rate

It never sends a motion command, a program, a register or an I/O write:
no source below has a write path.

Sources:
  ur        Universal Robots RTDE, receive interface only (ur_rtde's
            RTDEReceiveInterface): actual_q, actual_qd, actual_TCP_pose,
            robot_mode, safety_mode, runtime_state, controller timestamp.
            Port 30004 on the controller. NOT VERIFIED on the lab's UR5e yet.
  fanuc     NOT IMPLEMENTED until the controller is inspected (model,
            software, enabled options). `fanuc_probe.py` reads what the
            controller's own web pages show, read-only, so the right
            interface can be chosen; no protocol is assumed here.
  sim       a scripted demo motion, posted as source "SIMULATION": the
            portal shows it as DEMO DATA, never as a real robot.

    py robot_collector.py --source ur --robot <UR IP on the lab LAN> --device UR5E_01 --model UR5e
    py robot_collector.py --source sim --device UR5E_01 --model UR5e      (no robot needed)

Every 0.2 s the latest state goes to POST /api/robots/telemetry; motion
events go at once to POST /api/robots/events (kept and retried, bounded,
while the portal is unreachable); every 5 s the old RUNNING/IDLE/FAULT
report goes to /api/equipment/state (used by n8n workflows 18-19).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from collections import deque

import requests

from robot_state import MotionConfig, RobotMotion, Sample

HERE = os.path.dirname(os.path.abspath(__file__))
SAFETY_OK = {1, 2}             # RTDE safety_mode NORMAL / REDUCED (UR RTDE guide) - VERIFY on the controller
RUNTIME_PLAYING = 2            # RTDE runtime_state PLAYING - VERIFY


def device_key() -> str:
    key = os.environ.get("DEVICE_KEY", "")
    if not key:
        env = os.path.join(HERE, "..", "..", ".env")
        if os.path.isfile(env):
            for line in open(env, encoding="utf-8"):
                if line.strip().startswith("DEVICE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or "dev-device-key-change-me"


# --------------------------------------------------------------- sources ---
class URSource:
    """UR RTDE receive-only."""
    name = "RTDE"

    def __init__(self, ip: str, hz: float):
        try:
            from rtde_receive import RTDEReceiveInterface
        except ImportError:
            sys.exit("ur_rtde is not installed: pip install ur_rtde")
        self.rx = RTDEReceiveInterface(ip, hz)

    def read(self) -> Sample:
        rx = self.rx
        # ur_rtde keeps the last values after the link drops: never pass them on as current.
        if not rx.isConnected():
            raise ConnectionError("RTDE link lost")
        return Sample(t=float(rx.getTimestamp()), q=list(rx.getActualQ()), qd=list(rx.getActualQd()),
                      tcp=list(rx.getActualTCPPose()),
                      extra={"robot_mode": rx.getRobotMode(), "safety_mode": rx.getSafetyMode(),
                             "runtime_state": rx.getRuntimeState(),
                             "speed_scaling": round(float(rx.getSpeedScaling()), 3)})

    def close(self):
        try:
            self.rx.disconnect()
        except Exception:
            pass


class SimSource:
    """DEMO: a scripted cycle - still, J1 swing, J3 + J4 together, J6 twist,
    back home. Marked SIMULATION everywhere."""
    name = "SIMULATION"
    HOME = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]           # UR "upright" pose
    HOME_FANUC = [0.0, 0.0, 0.0, 0.0, -1.5708, 0.0]                  # FANUC: arm up, wrist down

    def __init__(self, hz: float, model: str = "UR5e"):
        self.t0 = time.time()
        self.home = self.HOME_FANUC if "FANUC" in model.upper() else self.HOME

    def pose(self, t: float) -> list:
        t = t % 24.0
        q = list(self.home)
        s = lambda a, b: 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, (t - a) / (b - a))))
        q[0] += math.radians(35) * (s(3, 6) - s(15, 18))
        q[2] += math.radians(-25) * (s(7, 10) - s(18, 21))
        q[3] += math.radians(30) * (s(7, 10) - s(18, 21))
        q[5] += math.radians(90) * (s(11, 13) - s(21, 23))
        return q

    def read(self) -> Sample:
        now = time.time()
        t = now - self.t0
        q = self.pose(t)
        # Velocities like a real controller reports them (central difference of the script).
        qd = [(a - b) / 0.02 for a, b in zip(self.pose(t + 0.01), self.pose(t - 0.01))]
        return Sample(t=now, q=q, qd=qd, extra={"robot_mode": "SIMULATION", "safety_mode": 1, "runtime_state": 2})

    def close(self):
        pass


def valid(s: Sample, joints: int = 6) -> bool:
    """6 finite joint angles (rad, |q| <= 2 turns as UR allows), finite velocities if given."""
    if not isinstance(s.q, list) or len(s.q) != joints:
        return False
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) <= 4 * math.pi + 0.01 for v in s.q):
        return False
    return s.qd is None or (len(s.qd) == joints and all(math.isfinite(v) for v in s.qd))


# --------------------------------------------------------------- collector ---
class Collector:
    def __init__(self, args):
        self.args = args
        self.portal = args.portal.rstrip("/")
        self.http = requests.Session()
        self.http.headers["X-Device-Key"] = device_key()
        self.motion = RobotMotion(MotionConfig(stale_s=args.stale_s))
        self.outbox: deque = deque(maxlen=500)      # events waiting for the portal (bounded)
        self.rate_t: deque = deque(maxlen=200)
        self.last_post = self.last_equipment = 0.0
        self.source = None
        self.last_ctrl_t = None                     # last controller timestamp seen (dedupe)
        self.rejected = 0                           # samples that failed valid()

    def open_source(self):
        a = self.args
        if a.source == "sim":
            return SimSource(a.hz, a.model)
        if a.source == "ur":
            if not a.robot:
                sys.exit("--robot <IP> is required for --source ur")
            return URSource(a.robot, a.hz)
        sys.exit("FANUC: run fanuc_probe.py first - the read-only interface is not chosen yet (see README).")

    def post(self, path, body, timeout=2.0) -> bool:
        try:
            r = self.http.post(self.portal + path, json=body, timeout=timeout)
            if r.status_code >= 400:
                print(f"[portal] {path} HTTP {r.status_code}: {r.text[:120]}")
            return r.status_code < 400
        except requests.RequestException as e:
            print(f"[portal] {path} unreachable: {e.__class__.__name__}")
            return False

    def flush(self):
        while self.outbox:
            batch = [self.outbox[i] for i in range(min(50, len(self.outbox)))]
            if not self.post("/robots/events", {"device_uid": self.args.device, "events": batch}):
                return
            for _ in batch:
                self.outbox.popleft()

    def report(self, now: float):
        a = self.args
        rate = 0.0
        if len(self.rate_t) >= 2:
            rate = (len(self.rate_t) - 1) / max(1e-6, self.rate_t[-1] - self.rate_t[0])
        snap = self.motion.snapshot(now)
        self.post("/robots/telemetry", {
            "device_uid": a.device, "lab_id": a.lab, "model": a.model, "source": self.source.name if self.source else
            ("SIMULATION" if a.source == "sim" else "RTDE"), "name": a.name or a.device,
            "rate_hz": round(rate, 1), "sent_at": now, **snap})
        if now - self.last_equipment >= 5.0:              # the older RUNNING/IDLE/FAULT report (n8n)
            ex = snap.get("extra") or {}
            fault = isinstance(ex.get("safety_mode"), int) and ex["safety_mode"] not in SAFETY_OK
            st = "FAULT" if fault else ("RUNNING" if snap["state"] == "MOVING" or ex.get("runtime_state") == RUNTIME_PLAYING
                                        else "IDLE")
            if snap["state"] != "TELEMETRY_STALE":
                self.post("/equipment/state", {"device_uid": a.device, "lab_id": a.lab, "kind": "ROBOT",
                                               "asset_tag": a.asset, "state": st,
                                               "firmware_version": f"robot-collector-0.2 ({a.source})",
                                               "detail": {k: ex.get(k) for k in ("robot_mode", "safety_mode", "runtime_state")}})
            self.last_equipment = now

    def run(self):
        a = self.args
        period = 1.0 / a.hz
        print(f"[robot] {a.device} ({a.model}) source={a.source} read-only. Ctrl+C stops.")
        # A simulation stops by itself (default 30 min) so a forgotten demo
        # does not keep writing demo events for hours.
        until = time.time() + a.max_minutes * 60 if (a.source == "sim" and a.max_minutes > 0) else None
        while True:
            now = time.time()
            if until is not None and now >= until:
                print(f"[robot] simulation ran {a.max_minutes:g} min - stopping (use --max-minutes 0 for no limit)")
                return
            if self.source is None:
                try:
                    self.source = self.open_source()
                    print("[robot] connected")
                except SystemExit:
                    raise
                except Exception as e:
                    print(f"[robot] cannot connect: {e.__class__.__name__}: {e} - retrying in 3 s")
                    self._events(self.motion.tick(now))
                    self.report(now) if now - self.last_post >= 1.0 else None
                    self.last_post = now
                    time.sleep(3)
                    continue
            try:
                s = self.source.read()
                if not valid(s):
                    self.rejected += 1
                    if self.rejected in (1, 10, 100) or self.rejected % 1000 == 0:
                        print(f"[robot] invalid sample ignored ({self.rejected} so far): q={s.q!r:.120}")
                elif a.source == "ur" and s.t == self.last_ctrl_t:
                    pass                                       # no new controller sample: not fresh data
                else:
                    if a.source == "ur":
                        self.last_ctrl_t = s.t
                        s.extra["controller_t"] = round(s.t, 3)
                        s.t = now                              # controller clock -> laptop clock (offset not assumed)
                    self.rate_t.append(now)
                    self._events(self.motion.update(s, arrival=now))
            except Exception as e:
                print(f"[robot] read failed: {e.__class__.__name__}: {e} - reconnecting")
                self.source.close()
                self.source = None
            self._events(self.motion.tick(now))
            if now - self.last_post >= a.report_s:
                self.report(now)
                self.last_post = now
                self.flush()
            time.sleep(max(0.0, period - (time.time() - now)))

    def _events(self, events):
        for e in events:
            d = e.as_dict()
            d["source"] = "SIMULATION" if self.args.source == "sim" else "RTDE"
            print(f"[robot] {e.kind}" + (f" J{e.joint + 1}" if e.joint is not None else "") + f" {e.detail}")
            self.outbox.append(d)
        if events:
            self.flush()


def main():
    ap = argparse.ArgumentParser(description="Read-only robot collector")
    ap.add_argument("--source", choices=["ur", "fanuc", "sim"], required=True)
    ap.add_argument("--robot", default="", help="controller IP on the lab LAN (inspect the robot - never assumed)")
    ap.add_argument("--device", required=True, help="device id in the portal, e.g. UR5E_01")
    ap.add_argument("--model", default="UR5e", help="UR5e, FANUC (exact model once inspected), ...")
    ap.add_argument("--name", default="")
    ap.add_argument("--asset", default=None, help="asset tag in the portal")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default=os.environ.get("PORTAL_URL", "http://127.0.0.1:8000/api"))
    ap.add_argument("--hz", type=float, default=50.0, help="samples per second read from the robot")
    ap.add_argument("--report-s", type=float, default=0.2, help="latest state to the portal this often")
    ap.add_argument("--stale-s", type=float, default=2.0)
    ap.add_argument("--max-minutes", type=float, default=30.0, help="simulation only: stop after this long (0 = never)")
    args = ap.parse_args()
    try:
        Collector(args).run()
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
