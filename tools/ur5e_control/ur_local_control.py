"""
UR5e Home + software Stop while the robot stays in LOCAL control mode (2026-10-26). DRY RUN by default.

Why a separate agent: in Local mode the controller refuses the Dashboard Server's load / play / stop / pause and
script sent to ports 30001-30003 (UR Dashboard Server e-Series reference, "Only Remote Control": load, play, stop,
pause, power, brake release, unlock protective stop, close safety popup). What Universal Robots supports in Local
mode is a program STARTED ON THE TEACH PENDANT that hands control to a computer: the External Control URCap (the
ROS 2 driver's "teach pendant mode"; ur_rtde's FLAG_USE_EXT_UR_CAP). While that pendant program plays, the robot
connects OUT to this laptop (port 50002) and runs the motion this agent sends - the operator started it, the
pendant keeps full authority (Stop / E-stop / pausing the program end it at once).

So, in Local mode:
  HOME  - only while the portal-control pendant program is playing and connected; guarded checks below; one joint
          move (moveJ) to the verified Home pose; completion is judged from joint feedback, never from the reply.
  STOP  - stopJ (controlled deceleration) through the same link: stops motion THIS link commanded.
          It cannot stop pendant jogging, Freedrive, or another program - the Dashboard 'stop' that would end another
          program is Remote-only. Those are reported as such, never as stopped.
In Remote mode the backend keeps its existing Dashboard path (docs/ROBOT_CONTROL.md).
NEVER an emergency stop: the pendant E-stop and the cell's hardware E-stop are the only emergency stops.

The monitoring collector (tools/robot_monitor) stays read-only; this agent is the only place that can command the
UR5e, and only with UR_CONTROL_MODE=live (owner sign-off). Python 3.12 + ur_rtde (already installed for RTDE).

    py -3.12 tools/ur5e_control/ur_local_control.py            # HTTP on 127.0.0.1:5310 (key from robot.env)
"""
from __future__ import annotations

import json
import math
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

HOME_Q_DEG = [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27]   # verified on the pendant 2026-10-17 (ROBOT_CONTROL.md)
HOME_TOL_DEG = 0.5
APPROACH_TOL_DEG = 10.0         # a start pose counts as "verified" within this of a recorded approach pose
STILL_RAD_S = 0.01              # every joint slower than this = the arm is still
FRESH_S = 1.0
HOME_SPEED, HOME_ACCEL = 0.35, 0.8   # rad/s, rad/s^2 (same as the reviewed Remote-mode movej)
STOP_DECEL = 2.0                     # rad/s^2: controlled stop, the value the Remote path already uses
SAFETY_OK = ("NORMAL", "REDUCED")


@dataclass
class Config:
    mode: str = "dry_run"                         # dry_run | live (owner sign-off) | off
    host: str = "192.168.1.102"
    program: str = "portal_control.urp"           # the pendant program holding the External Control node
    ur_cap_port: int = 50002
    approach: list = field(default_factory=list)  # operator-verified start poses (deg), recorded at commissioning

    @staticmethod
    def from_env(env: Optional[dict] = None) -> "Config":
        e = env if env is not None else os.environ
        poses = []
        p = e.get("UR_APPROACH_FILE", "")
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                poses = [list(map(float, q)) for q in json.load(f).get("poses", [])]
        return Config(mode=e.get("UR_CONTROL_MODE", "dry_run").lower(), host=e.get("UR5E_IP", "192.168.1.102"),
                      program=e.get("UR_PORTAL_PROGRAM", "portal_control.urp"),
                      ur_cap_port=int(e.get("UR_CAP_PORT", "50002")), approach=poses)


# ------------------------------------------------------------------ policy (pure, unit-tested) ---
def _deg(q):
    return [math.degrees(v) for v in q]


def classify(state: dict, cfg: Config) -> dict:
    """What the controller is doing and who drives it - from what it reports (never assumed)."""
    remote = state.get("remote")
    prog = str(state.get("program_state") or "")
    loaded = str(state.get("loaded_program") or "")
    playing = prog.upper().startswith("PLAYING")
    ours = playing and os.path.basename(loaded).lower() == cfg.program.lower()
    moving = any(abs(v) > STILL_RAD_S for v in (state.get("qd") or []))
    if ours and state.get("link") in ("connected", "dry_run"):
        driver = "PORTAL_PROGRAM"           # pendant-started portal program, link up (dry run: never opened)
    elif playing:
        driver = "OTHER_PROGRAM"
    elif moving:
        driver = "PENDANT_MANUAL"          # jogging / Freedrive / move screen - no program
    else:
        driver = "IDLE"
    return {"control_mode": "REMOTE" if remote is True else "LOCAL" if remote is False else "UNKNOWN",
            "driver": driver, "playing": playing, "ours": ours, "moving": moving}


def home_checks(state: dict, cfg: Config, confirmed: bool, latched: bool, now: Optional[float] = None) -> list[dict]:
    now = now or time.time()
    c = classify(state, cfg)
    q = state.get("q")
    qdeg = _deg(q) if q and len(q) == 6 else None
    near = None
    if qdeg:
        cands = [HOME_Q_DEG] + list(cfg.approach)
        near = min(max(abs(a - b) for a, b in zip(qdeg, p)) for p in cands)
    fresh = state.get("t") is not None and now - state["t"] <= FRESH_S

    def ck(key, name, ok, detail):
        return {"key": key, "name": name, "ok": bool(ok), "detail": detail}
    return [
        ck("confirmed", "Operator confirmed in the portal", confirmed, "confirmed" if confirmed else "not confirmed"),
        ck("telemetry", "Fresh joint feedback", fresh and qdeg is not None,
           "fresh" if fresh and qdeg else "no fresh joints - state unknown"),
        ck("safety", "Safety status NORMAL / REDUCED", str(state.get("safety")) in SAFETY_OK,
           str(state.get("safety") or "not reported")),
        ck("power", "Robot RUNNING", state.get("robot_mode") == "RUNNING", str(state.get("robot_mode") or "not reported")),
        ck("program", f"Pendant program {cfg.program} playing and connected", c["driver"] == "PORTAL_PROGRAM",
           {"PORTAL_PROGRAM": "playing, link connected", "OTHER_PROGRAM": "another program is playing - someone else "
            "controls the robot", "PENDANT_MANUAL": "moved from the pendant (jog / Freedrive)",
            "IDLE": f"start {cfg.program} with Play on the teach pendant (Local mode needs the operator)"}[c["driver"]]),
        ck("still", "Arm still", not c["moving"], "still" if not c["moving"] else "moving - wait"),
        ck("stop", "STOP not latched", not latched, "clear" if not latched else "latched - administrator recovery"),
        ck("approach", "Start pose verified for the Home path", near is not None and near <= APPROACH_TOL_DEG,
           "unknown" if near is None else (f"within {near:.1f} deg of a verified pose" if near <= APPROACH_TOL_DEG else
           f"{near:.1f} deg from every verified pose - jog closer on the pendant, or record this pose during "
           "commissioning")),
    ]


def decide(action: str, state: dict, cfg: Config, confirmed: bool = False, latched: bool = False) -> dict:
    """ACCEPTED (would / will send) | REJECTED (a check failed) | UNSUPPORTED (Local mode cannot do this)."""
    c = classify(state, cfg)
    if cfg.mode == "off":
        return {"status": "UNAVAILABLE", "reason": "UR control is off (UR_CONTROL_MODE=off)", "class": c}
    if action == "home":
        checks = home_checks(state, cfg, confirmed, latched)
        bad = [k for k in checks if not k["ok"]]
        if bad:
            return {"status": "REJECTED", "reason": "; ".join(f"{k['name']}: {k['detail']}" for k in bad),
                    "checks": checks, "class": c}
        return {"status": "ACCEPTED", "reason": "all checks passed", "checks": checks, "class": c,
                "send": f"moveJ to Home {HOME_Q_DEG} deg, v={HOME_SPEED} rad/s, a={HOME_ACCEL} rad/s^2"}
    if action == "stop":
        if c["driver"] == "PORTAL_PROGRAM":
            return {"status": "ACCEPTED", "reason": "the portal program drives the arm - controlled stop through it",
                    "class": c, "send": f"stopJ(a={STOP_DECEL} rad/s^2)"}
        if c["control_mode"] == "REMOTE":
            return {"status": "UNSUPPORTED", "reason": "Remote mode: the backend's Dashboard 'stop' path applies",
                    "class": c}
        why = {"OTHER_PROGRAM": "another program started on the pendant is running; ending it needs the Dashboard "
                                "'stop', which the controller accepts only in Remote mode - press Stop / Pause on the "
                                "pendant or use the E-stop",
               "PENDANT_MANUAL": "the arm is moved from the pendant (jog / Freedrive) - only the person at the pendant "
                                 "or the E-stop can stop that",
               "IDLE": "nothing is commanded by the portal right now (no motion to stop)"}[c["driver"]]
        return {"status": "UNSUPPORTED", "reason": "Local mode: " + why, "class": c}
    return {"status": "REJECTED", "reason": f"unknown action {action!r}", "class": c}


# ------------------------------------------------------------ controller links (read / command) ---
class DashboardReader:
    """READ-ONLY Dashboard queries (allowed in Local mode). Never sends a state-changing command."""
    QUERIES = {"remote": "is in remote control", "robot_mode": "robotmode", "safety": "safetystatus",
               "program_state": "programState", "loaded_program": "get loaded program",
               "polyscope": "PolyscopeVersion"}

    def __init__(self, host: str, timeout: float = 2.0):
        self.host, self.timeout = host, timeout

    def read(self) -> dict:
        out = {}
        with socket.create_connection((self.host, 29999), timeout=self.timeout) as s:
            f = s.makefile("rwb", buffering=0)
            f.readline()                                    # welcome banner
            for key, q in self.QUERIES.items():
                assert q in DashboardReader.QUERIES.values()  # nothing else is ever written
                f.write((q + "\n").encode())
                out[key] = f.readline().decode(errors="replace").strip()
        r = out["remote"].lower()
        out["remote"] = True if r == "true" else False if r == "false" else None
        out["robot_mode"] = out["robot_mode"].split(":")[-1].strip().upper()
        out["safety"] = out["safety"].split(":")[-1].strip().upper()
        out["loaded_program"] = out["loaded_program"].split(":", 1)[-1].strip()
        return out


class Agent:
    def __init__(self, cfg: Config, dash=None, rtde_r=None, link=None):
        self.cfg, self.lock = cfg, threading.Lock()
        self.dash = dash or DashboardReader(cfg.host)
        self.rtde_r, self.link = rtde_r, link
        self.state: dict = {"link": "off"}
        self.latched = False
        self.log: list[dict] = []

    def _link(self):
        """The External Control link (ur_rtde in URCap mode). Created only in live mode; it waits for the
        pendant program to connect to this laptop - it can never start a program by itself."""
        if self.link is None and self.cfg.mode == "live":
            import rtde_control
            f = rtde_control.RTDEControlInterface
            self.link = f(self.cfg.host, -1.0, f.FLAG_USE_EXT_UR_CAP | f.FLAG_UPLOAD_SCRIPT, self.cfg.ur_cap_port)
        return self.link

    def refresh(self) -> dict:
        st = {"t": None}
        try:
            st.update(self.dash.read())
        except (OSError, AssertionError, IndexError) as e:
            st["dashboard_error"] = e.__class__.__name__
        try:
            if self.rtde_r is None:
                import rtde_receive
                self.rtde_r = rtde_receive.RTDEReceiveInterface(self.cfg.host)
            st["q"], st["qd"], st["t"] = list(self.rtde_r.getActualQ()), list(self.rtde_r.getActualQd()), time.time()
        except Exception as e:                              # unreachable robot: state unknown, nothing allowed
            st["rtde_error"] = e.__class__.__name__
        if self.cfg.mode == "dry_run":
            st["link"] = "dry_run"                          # never opened: nothing can be sent
        else:
            st["link"] = ("connected" if self.link is not None and self.link.isConnected() and self.link.isProgramRunning()
                          else "waiting" if self.link is not None else "off")
        with self.lock:
            self.state = st
        return st

    def command(self, action: str, command_id: str, confirmed: bool = False) -> dict:
        st = self.refresh()
        with self.lock:
            if action == "stop":
                self.latched = True                          # latch FIRST: no Home after a Stop until recovery
            d = decide(action, st, self.cfg, confirmed, self.latched and action == "home")
            out = {"command_id": command_id, "action": action, **d, "controller": classify(st, self.cfg),
                   "sent": False}
            if d["status"] == "ACCEPTED":
                if self.cfg.mode == "dry_run":
                    out.update(status="DRY_RUN", reason="checks passed - would send: " + d["send"] + " (nothing sent)")
                elif self.cfg.mode == "live":
                    link = self._link()
                    try:
                        if action == "home":
                            link.moveJ([math.radians(v) for v in HOME_Q_DEG], HOME_SPEED, HOME_ACCEL, True)
                        else:
                            link.stopJ(STOP_DECEL, False)
                        out.update(status="REQUESTED", sent=True,
                                   reason=d["send"] + " sent - completion is judged from joint feedback only")
                    except Exception as e:
                        out.update(status="FAILED", reason=f"link error {e.__class__.__name__} - state unknown, not retried")
            self.log.append({"t": time.time(), **{k: out[k] for k in ("command_id", "action", "status", "reason")}})
            return out

    def recover(self) -> dict:
        st = self.refresh()
        if classify(st, self.cfg)["moving"]:
            return {"ok": False, "reason": "the arm is reported moving - recovery refused"}
        self.latched = False
        return {"ok": True, "reason": "STOP cleared - nothing was restarted"}


# ---------------------------------------------------------------------------------- HTTP (localhost) ---
def serve(agent: Agent, key: str, port: int = 5310):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import hmac

    class H(BaseHTTPRequestHandler):
        def _ok(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def _auth(self):
            return bool(key) and hmac.compare_digest(self.headers.get("X-UR-Agent-Key", ""), key)

        def do_GET(self):
            if not self._auth():
                return self._ok(401, {"error": "key"})
            if self.path == "/state":
                st = agent.refresh()
                return self._ok(200, {"mode": agent.cfg.mode, "program": agent.cfg.program, "latched": agent.latched,
                                      "controller": classify(st, agent.cfg),
                                      "state": {k: st.get(k) for k in ("remote", "robot_mode", "safety", "program_state",
                                                                       "loaded_program", "polyscope", "link", "t")},
                                      "home_checks": home_checks(st, agent.cfg, True, agent.latched)})
            self._ok(404, {"error": "not found"})

        def do_POST(self):
            if not self._auth():
                return self._ok(401, {"error": "key"})
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
            if self.path == "/command" and body.get("action") in ("home", "stop"):
                return self._ok(200, agent.command(body["action"], str(body.get("command_id", ""))[:64],
                                                   bool(body.get("confirmed"))))
            if self.path == "/recover":
                return self._ok(200, agent.recover())
            self._ok(400, {"error": "bad request"})

        def log_message(self, *a):
            pass

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    envf = os.path.join(here, "..", "robot_monitor", "robot.env")
    if os.path.isfile(envf):
        for line in open(envf, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.replace("set ", "").strip(), v.strip())
    cfg = Config.from_env()
    key = os.environ.get("UR_AGENT_KEY", "")
    if not key:
        raise SystemExit("UR_AGENT_KEY missing (robot.env) - refusing to start without a key")
    print(f"UR5e Local-mode control agent: {cfg.mode.upper()} | {cfg.host} | program {cfg.program} | 127.0.0.1:5310")
    agent = Agent(cfg)
    if cfg.mode == "live":                                  # wait (in the background) for the pendant program
        threading.Thread(target=agent._link, daemon=True, name="ext-control-link").start()
    serve(agent, key)
