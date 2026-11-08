"""
Robot control requests (Home, approved routines, software stop) - SAFE BY DEFAULT.

The portal's robot links are READ-ONLY today: the UR5e collector uses RTDE *receive* and the FANUC
collector only GETs /MD/CURPOS.DG. Neither can command a robot, and no command interface has been
commissioned on either controller. So every adapter below reports motion as UNAVAILABLE with the
reason, and nothing is ever sent to a controller. What IS implemented and enforced server-side:

  * exclusive portal control ownership per robot (staff only), with expiry and explicit release;
    ownership lives in memory, so a backend restart can never leave a stale owner behind
  * an allowlist of actions; unknown routines are refused
  * command ids: a repeated id is answered with the first result, never executed twice
  * an audit record for every request and its outcome
  * readiness checks (fresh telemetry, ownership, adapter support) before anything else

The portal's lock does NOT stop someone at the teach pendant: a real adapter must also read the
controller's own mode (UR: remote/local control, FANUC: TP enabled / remote) before it may act.
See docs/ROBOT_CONTROL.md for the commissioning steps that must happen before an adapter is enabled.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

OWNERSHIP_S = 300.0                 # control lapses after 5 min without renewal
FRESH_S = 2.0                       # telemetry older than this = not ready
ACTIONS = ("home", "routine", "stop")


@dataclass
class Result:
    status: str                     # UNAVAILABLE | REJECTED | REQUESTED | ACCEPTED | DUPLICATE
    reason: str
    command_id: Optional[str] = None
    action: Optional[str] = None

    def out(self) -> dict:
        return {"status": self.status, "reason": self.reason, "command_id": self.command_id,
                "action": self.action}


class Adapter:
    """One per controller type. A real implementation must verify the controller's mode itself."""
    name = "none"
    interface = "none"
    blocker = "No command interface is commissioned for this robot."

    def capabilities(self) -> dict:
        return {"home": False, "routines": [], "stop": False, "interface": self.interface,
                "unavailable_reason": self.blocker}

    def controller_mode(self) -> str:
        return "UNKNOWN"            # never assumed: unknown blocks every command

    def execute(self, action: str, routine: Optional[str]) -> Result:
        return Result("UNAVAILABLE", self.blocker, action=action)


import os

# ROBOT_CONTROL: "dry_run" (default) runs every check and reports what WOULD be sent, sending
# nothing; "live" talks to the UR5e Dashboard Server - only after commissioning; "off" = unavailable.
MODE = os.environ.get("ROBOT_CONTROL", "dry_run").lower()
UR_HOME_PROGRAM = os.environ.get("UR5E_HOME_PROGRAM", "home.urp")     # the program on the pendant
UR_HOST = os.environ.get("UR5E_IP", "192.168.1.102")
# Verified Home pose read off the teach pendant (owner's photo, 2026-10-17), degrees J1..J6.
UR_HOME_Q_DEG = [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27]
HOME_TOL_DEG = 0.5                  # every joint within this of Home = reached (from feedback)
HOME_TIMEOUT_S = 60.0               # not at Home by then = FAILED (reported, never retried)
# How HOME is carried out in live mode (2026-10-17):
#   "program" (default) - load + play the Home program the operator validated ON THE PENDANT
#                         (its own waypoints, speed and collision checks = the controller's validated
#                         Home behaviour). UR5E_HOME_PROGRAM must name that program exactly.
#   "movej"             - one direct joint move to UR_HOME_Q_DEG. NOT equivalent to the pendant's Home
#                         routine (path, speed, blending can differ): use only if the operator approves.
UR_HOME_METHOD = os.environ.get("UR5E_HOME_METHOD", "program").lower()
# Which way commands reach the UR5e (2026-10-26):
#   "local_agent" (default) - the robot STAYS IN LOCAL MODE. The operator presses Play on the pendant program that
#       holds the External Control node; the native agent (tools/ur5e_control/ur_local_control.py, 127.0.0.1:5310)
#       sends Home (moveJ) / Stop (stopJ) through it and runs its own checks. Official UR reference: the Dashboard's
#       load / play / stop / pause are "Only Remote Control", so in Local mode the Dashboard path is refused.
#   "dashboard" - the Remote-mode path below (load + play home.urp, Dashboard stop + stopj).
UR_PATH = os.environ.get("UR5E_CONTROL_PATH", "local_agent").lower()


def ur_agent_state(max_age: float = 1.0) -> Optional[dict]:
    from app.services import ur_agent
    return ur_agent.state(max_age)


def ur_agent(method: str, path: str, body: Optional[dict] = None, timeout: float = 2.0) -> Optional[dict]:
    from app.services import ur_agent as client
    return client.call(method, path, body, timeout)
# RTDE codes (Universal Robots RTDE guide): safety mode 1 NORMAL, 2 REDUCED; robot mode 7 RUNNING.
UR_SAFETY_OK = {1: "NORMAL", 2: "REDUCED"}
UR_SAFETY_NAMES = {3: "PROTECTIVE STOP", 4: "RECOVERY", 5: "SAFEGUARD STOP", 6: "SYSTEM EMERGENCY STOP",
                   7: "ROBOT EMERGENCY STOP", 8: "VIOLATION", 9: "FAULT"}


class URAdapter(Adapter):
    name = "UR5e"
    blocker = ("UR5e: control is off (ROBOT_CONTROL=off).")

    @property
    def agent_path(self) -> bool:
        return UR_PATH == "local_agent"

    @property
    def interface(self):
        if self.agent_path:
            via = "Local-mode agent (External Control program started on the pendant)"
            return {"dry_run": "DRY RUN - nothing is sent (would use the " + via + ")", "live": via}.get(
                MODE, "RTDE receive only (monitoring)")
        return {"dry_run": f"DRY RUN - nothing is sent (would use Dashboard Server {UR_HOST}:29999)",
                "live": f"Dashboard Server {UR_HOST}:29999"}.get(MODE, "RTDE receive only (monitoring)")

    def capabilities(self) -> dict:
        on = MODE in ("dry_run", "live")
        return {"home": on, "routines": [], "stop": on, "interface": self.interface, "path": UR_PATH,
                "home_program": UR_HOME_PROGRAM, "home_method": "movej (agent)" if self.agent_path else UR_HOME_METHOD,
                "unavailable_reason": None if on else self.blocker}

    def controller_mode(self) -> str:
        if self.agent_path and MODE in ("dry_run", "live"):
            st = ur_agent_state()
            if st is None:
                return "AGENT_UNREACHABLE"
            c = st.get("controller") or {}
            return f"{c.get('control_mode', 'UNKNOWN')}:{c.get('driver', 'UNKNOWN')}"   # e.g. LOCAL:PORTAL_PROGRAM
        if MODE == "dry_run":
            return "DRY_RUN_SIMULATED"      # never shown as a real controller state
        if MODE == "live":
            from app.services.ur_dashboard import Dashboard
            return Dashboard(UR_HOST).mode()
        return "UNKNOWN"

    def execute(self, action: str, routine: Optional[str]) -> Result:
        if self.agent_path and MODE in ("dry_run", "live"):
            return self._via_agent(action)
        return self._via_dashboard(action, routine)

    def _via_agent(self, action: str) -> Result:
        """Local mode: the agent runs its own checks and sends only through the pendant-started program. Both
        sides must be in the same mode (backend ROBOT_CONTROL and agent UR_CONTROL_MODE): two sign-offs."""
        st = ur_agent_state(max_age=0.0)
        if st is None:
            return Result("UNAVAILABLE", "the UR5e Local-mode agent is not running / not reachable - nothing sent "
                                         "(start tools/ur5e_control/ur_local_control.py)")
        if st.get("mode") != MODE:
            return Result("REJECTED", f"backend ROBOT_CONTROL={MODE} but the UR agent runs in {st.get('mode')} mode - "
                                      "both must agree before anything is sent")
        r = ur_agent("POST", "/command", {"action": action, "command_id": "portal", "confirmed": True}, timeout=5.0)
        if r is None:
            return Result("FAILED", "the agent did not answer - state unknown, not retried")
        status = r.get("status", "FAILED")
        if action == "stop" and status == "UNSUPPORTED" and (r.get("class") or {}).get("control_mode") == "REMOTE":
            return self._via_dashboard("stop", None)            # Remote mode: the Dashboard stop applies
        return Result(status, r.get("reason", ""))

    def _via_dashboard(self, action: str, routine: Optional[str]) -> Result:
        from app.services import ur_script
        q = ", ".join(f"{v:.2f}" for v in UR_HOME_Q_DEG)
        if action == "home":
            what = (f"Dashboard 'load {UR_HOME_PROGRAM}' + 'play' (the pendant's validated Home program; "
                    f"target [{q}] deg confirmed from joint feedback)" if UR_HOME_METHOD == "program"
                    else f"URScript movej to Home [{q}] deg (secondary client interface)")
        else:
            what = "Dashboard 'stop' + URScript stopj (secondary client interface)"
        if MODE == "dry_run":
            return Result("DRY_RUN", "checks passed - would send: " + what + " (nothing sent)")
        if MODE != "live":
            return Result("UNAVAILABLE", self.blocker)
        from app.services.ur_dashboard import Dashboard
        try:
            if action == "home" and UR_HOME_METHOD == "program":
                d = Dashboard(UR_HOST)
                loaded = d.ask(f"load {UR_HOME_PROGRAM}")
                if not loaded.lower().startswith("loading program"):
                    return Result("REJECTED", f"controller refused to load {UR_HOME_PROGRAM}: {loaded} - nothing started")
                played = d.ask("play")
                if not played.lower().startswith("starting program"):
                    return Result("REJECTED", f"controller refused to play: {played}")
                return Result("REQUESTED", f"{loaded} | {played} - Home is confirmed only from joint feedback")
            if action == "home":
                ur_script.send(UR_HOST, ur_script.home_script(UR_HOME_Q_DEG))
                return Result("REQUESTED", "Home move sent - Home is confirmed only from joint feedback")
            replies = []
            try:
                replies.append(Dashboard(UR_HOST).ask("stop"))
            finally:
                ur_script.send(UR_HOST, ur_script.STOP_SCRIPT)
            return Result("REQUESTED", "stop sent (" + " | ".join(replies) + ") - stopped state confirmed from feedback")
        except (OSError, ValueError) as e:
            return Result("FAILED", f"controller did not answer ({e.__class__.__name__}) - state unknown, not retried")


class FanucAdapter(Adapter):
    name = "FANUC"
    # Verified from the controller's own summary page (/MD/SUMMARY.DG, read-only GET on 2026-10-14 18:21,
    # parsed by tools/robot_monitor/fanuc_summary.py). Its DEMO option list is empty: these are installed
    # options, not time-limited trials. Installed is not configured - nothing below is set up for remote use.
    identity = "LR HandlingTool V9.30P/12 (root V9.30107), ER-4iA, Mate controller, DCS V4.2.14"
    installed_interfaces = ("User Socket Msg R648, Socket Messaging R636, PC Interface R641, KAREL R632, "
                            "HMI Device (SNPX) R553, Prog Num Selection J515, Robot Service Request, OPC-UA, "
                            "Ethernet/IP I/O Adp. R538")
    # What must still exist before any FANUC command can be designed (2026-10-18).
    dependencies = [
        "Choose ONE installed interface with the qualified operator (e.g. a HOME TP program started through "
        "Robot Service Request / Prog Num Selection J515 signals, or a KAREL socket server on User Socket Msg R648) "
        "and configure it on the controller - nothing is configured for remote use yet",
        "Controller AUTO mode with remote start enabled, and the permissions agreed with the qualified operator",
        "A HOME TP program written and validated on the pendant at reduced speed, with its joint values recorded",
        "The strongest supported normal stop for that interface (e.g. UOP *HOLD / cycle stop or a program abort) "
        "identified and tested under supervision",
        "A portal adapter for that one interface, tested in dry run and signed off - none exists, on purpose",
    ]
    interface = "HTTP GET /MD/CURPOS.DG (monitoring)"
    blocker = ("FANUC: the portal only reads the position page. Commands need a controller-supported "
               "remote interface (e.g. robot-side TP programs started via a licensed option) set up "
               "and validated by an authorized operator - not done yet.")


def adapter_for(model: Optional[str]) -> Adapter:
    m = (model or "").upper()
    if "FANUC" in m:
        return FanucAdapter()
    if m.startswith("UR"):
        return URAdapter()
    return Adapter()


@dataclass
class Owner:
    user_id: int
    name: str
    until: float


@dataclass
class _State:
    owners: dict = field(default_factory=dict)        # device_id -> Owner
    commands: dict = field(default_factory=dict)      # command_id -> Result
    stops: dict = field(default_factory=dict)         # device_id -> latched STOP (blocks all motion)
    homing: dict = field(default_factory=dict)        # device_id -> Home being tracked from feedback
    lock: threading.Lock = field(default_factory=threading.Lock)


_state = _State()


def reset() -> None:                                   # tests
    with _state.lock:
        _state.owners.clear(); _state.commands.clear(); _state.stops.clear(); _state.homing.clear()


def owner(device_id: int, now: Optional[float] = None) -> Optional[Owner]:
    now = now or time.time()
    o = _state.owners.get(device_id)
    if o and o.until < now:
        _state.owners.pop(device_id, None)
        return None
    return o


def request_control(device_id: int, user_id: int, name: str) -> tuple[bool, str, Optional[Owner]]:
    with _state.lock:
        o = owner(device_id)
        if o and o.user_id != user_id:
            return False, f"{o.name} has control of this robot; they must release it first.", o
        o = Owner(user_id, name, time.time() + OWNERSHIP_S)
        _state.owners[device_id] = o
        return True, "control granted (portal only - the teach pendant can still take over)", o


def release_control(device_id: int, user_id: int, force: bool = False) -> bool:
    with _state.lock:
        o = owner(device_id)
        if o is None or (o.user_id != user_id and not force):
            return False
        _state.owners.pop(device_id, None)
        return True


def submit(device_id: int, model: Optional[str], user_id: int, action: str, routine: Optional[str],
           command_id: str, telemetry_age_s: Optional[float]) -> Result:
    with _state.lock:
        if command_id in _state.commands:
            r = _state.commands[command_id]
            return Result("DUPLICATE", f"command already handled: {r.status}", command_id, r.action)
        if action != "stop" and device_id in _state.stops:
            r = Result("REJECTED", "STOP is latched - an administrator must run the recovery first")
        else:
            r = _check(device_id, model, user_id, action, routine, telemetry_age_s)
        r.command_id, r.action = command_id, action
        _state.commands[command_id] = r
        if action == "home" and r.status in ("REQUESTED", "DRY_RUN"):
            _state.homing[device_id] = {"t": time.time(), "command_id": command_id,
                                        "dry_run": r.status == "DRY_RUN"}
        return r


def global_stop(device_id: int, model: Optional[str], name: str, command_id: str) -> Result:
    """Any staff member, whoever owns or drives the robot. STOP takes priority: the latch is set
    FIRST under the lock (no Home can start after this), Home tracking is cancelled, then the stop
    is sent. Nothing restarts by itself; recover() is the deliberate way back."""
    with _state.lock:
        if command_id in _state.commands:
            r = _state.commands[command_id]
            return Result("DUPLICATE", f"command already handled: {r.status}", command_id, r.action)
        _state.stops[device_id] = {"t": time.time(), "by": name}
        _state.homing.pop(device_id, None)
        ad = adapter_for(model)
        caps = ad.capabilities()
        r = ad.execute("stop", None) if caps.get("stop") else Result("UNAVAILABLE", caps["unavailable_reason"])
        r.command_id, r.action = command_id, "stop"
        _state.stops[device_id]["result"] = r.status
        _state.commands[command_id] = r
        return r


def restore_latches(events: list[dict]) -> list[int]:
    """A latched STOP survives a backend restart (2026-10-18). The latch lives in memory, so a restart
    used to clear it - an implicit recovery nobody approved. At start-up the audit rows
    ROBOT_GLOBAL_STOP / ROBOT_STOP_RECOVERY (in time order) are replayed: a robot whose last word is a
    STOP (no successful recovery after it) is latched again. Only the latch - nothing is sent to any
    robot, and Home tracking is never resumed."""
    last: dict[int, dict] = {}
    for e in events:
        if e["action"] == "ROBOT_GLOBAL_STOP":
            last[e["device_id"]] = e
        elif e["action"] == "ROBOT_STOP_RECOVERY" and e.get("cleared"):
            last.pop(e["device_id"], None)
    with _state.lock:
        for did, e in last.items():
            _state.stops[did] = {"t": e["t"], "by": e.get("by") or "?", "result": e.get("result"),
                                 "restored": True}
    return sorted(last)


def recover(device_id: int, moving: bool) -> tuple[bool, str]:
    """Clear a latched STOP - only while the arm is reported still. Restarts nothing."""
    with _state.lock:
        if device_id not in _state.stops:
            return False, "no STOP is latched"
        if moving:
            return False, "the arm is still reported moving - recovery refused"
        _state.stops.pop(device_id, None)
        return True, "STOP cleared - motion commands are allowed again (nothing was restarted)"


def master_state(device_id: int, q_deg: Optional[list], moving: bool, fresh: bool,
                 extra: Optional[dict] = None, simulated: bool = False) -> dict:
    """READY / HOMING / HOME_REACHED / BLOCKED / FAILED - from joint FEEDBACK, never a command reply."""
    home = UR_HOME_Q_DEG
    err = (max(abs(a - b) for a, b in zip(q_deg, home))
           if q_deg and len(q_deg) == 6 else None)
    at_home = err is not None and err <= HOME_TOL_DEG
    with _state.lock:
        stop = _state.stops.get(device_id)
        h = _state.homing.get(device_id)
        if stop:
            # STOPPED only when the feedback shows the arm still (and no program playing).
            playing = "PLAYING" in str((extra or {}).get("program_state") or "").upper()
            if fresh and err is not None and not moving and not playing:
                phase, detail = "STOPPED", f"STOP latched by {stop['by']}; feedback: arm still - recovery needed"
            else:
                phase, detail = "STOP_REQUESTED", (f"STOP latched by {stop['by']}; waiting for feedback that the arm "
                                                    "has stopped" + ("" if fresh else " (no fresh telemetry)"))
        elif h and h.get("dry_run"):
            phase = "HOME_REACHED" if at_home else "READY"
            detail = "dry run - nothing was sent, the arm did not move"
            _state.homing.pop(device_id, None)
        elif h:
            if not fresh:
                phase, detail = "FAILED", "telemetry lost during homing - state unknown"
                _state.homing.pop(device_id, None)
            elif at_home and not moving:
                phase, detail = "HOME_REACHED", f"every joint within {HOME_TOL_DEG} deg of Home (feedback)"
                _state.homing.pop(device_id, None)
            elif time.time() - h["t"] > HOME_TIMEOUT_S:
                phase = "FAILED"
                detail = (f"not at Home after {HOME_TIMEOUT_S:.0f} s" +
                          (f" (max error {err:.1f} deg)" if err is not None else ""))
                _state.homing.pop(device_id, None)
            else:
                phase = "HOMING"
                detail = "moving to Home" + (f" - max error {err:.1f} deg" if err is not None else "")
        elif not fresh:
            phase, detail = "BLOCKED", "no fresh telemetry - robot state unknown"
        elif err is None:               # the collector reports, but the controller gives no joints
            phase, detail = "BLOCKED", "no joint feedback from the controller - robot state unknown"
        else:
            phase, detail = ("HOME_REACHED", "at Home (feedback)") if at_home else ("READY", "")
    local = ur_agent_state() if UR_PATH == "local_agent" and MODE in ("dry_run", "live") else None
    checks = ur_checks(q_deg, fresh, extra or {}, stop is not None, simulated, local)
    pre = all(c["ok"] for c in checks if c["key"] != "signoff")
    readiness = ("READY" if pre and MODE == "live" else "READY_FOR_PHYSICAL_TEST" if pre and MODE == "dry_run"
                 else "BLOCKED")
    return {"phase": phase, "detail": detail, "readiness": readiness, "checks": checks,
            "home_method": UR_HOME_METHOD, "home_program": UR_HOME_PROGRAM,
            "home_q_deg": home, "tolerance_deg": HOME_TOL_DEG,
            "max_error_deg": None if err is None else round(err, 2), "stop_latched": stop is not None,
            "stop": None if not stop else {"by": stop["by"], "at": stop["t"], "result": stop.get("result"),
                                           "restored": bool(stop.get("restored"))},   # latched before a restart
            "path": UR_PATH,
            # Local-mode view from the agent: actual control mode, who drives the arm, the agent's own Home checks
            "local": None if local is None else {"controller": local.get("controller"), "agent_mode": local.get("mode"),
                                                 "program": local.get("program"), "state": local.get("state"),
                                                 "home_checks": local.get("home_checks")},
            # automatic Home after the arm sat idle (agent, UR_AUTO_HOME) - countdown shown + cancellable in the twin
            "auto_home": None if local is None else local.get("auto_home"),
            "relay": _relay_view(stop is not None),
            "local_limits": ("Local mode: Home and Stop work only while the portal program runs on the pendant "
                             "(the operator pressed Play). Stop cannot end pendant jogging, Freedrive or another "
                             "program - the controller accepts the Dashboard stop only in Remote mode.")
                            if UR_PATH == "local_agent" else None,
            "estop_note": "Software stop only (stopJ / Dashboard stop). It is NOT a safety-rated emergency "
                          "stop - use the red E-stop on the teach pendant or the cell's hardware E-stop."}


def _relay_view(latched: bool) -> Optional[dict]:
    from app.services import stop_relay
    return stop_relay.view(latched) if stop_relay.configured() else None


def stop_latched(device_id: int) -> bool:
    with _state.lock:
        return device_id in _state.stops


def _check(device_id, model, user_id, action, routine, age) -> Result:
    if action not in ACTIONS:
        return Result("REJECTED", f"unknown action {action!r}")
    ad = adapter_for(model)
    caps = ad.capabilities()
    if action == "routine" and routine not in caps["routines"]:
        return Result("REJECTED", f"routine {routine!r} is not on this robot's approved list")
    o = owner(device_id)
    if o is None or o.user_id != user_id:
        return Result("REJECTED", "you do not have control of this robot")
    if age is None or age > FRESH_S:
        return Result("REJECTED", "telemetry is not fresh - the robot's state is unknown")
    h = _state.homing.get(device_id)                 # conflicting request: one Home at a time
    if action == "home" and h and not h.get("dry_run") and time.time() - h["t"] < HOME_TIMEOUT_S:
        return Result("REJECTED", "Home is already in progress - wait for Home reached / failed, or press STOP")
    mode = ad.controller_mode()
    if getattr(ad, "agent_path", False) and MODE in ("dry_run", "live"):
        if mode == "AGENT_UNREACHABLE":
            return Result("UNAVAILABLE", "the UR5e Local-mode agent is not reachable - nothing sent")
        return ad.execute(action, routine)          # the agent checks the controller itself (Local or Remote)
    if mode == "DRY_RUN_SIMULATED" and MODE == "dry_run":
        return ad.execute(action, routine)          # answers DRY_RUN; sends nothing
    if mode != "REMOTE_READY":
        return Result("UNAVAILABLE", caps["unavailable_reason"] or f"controller not ready ({mode})")
    return ad.execute(action, routine)


def ur_checks(q_deg: Optional[list], fresh: bool, extra: dict, latched: bool, simulated: bool = False,
              local: Optional[dict] = None) -> list[dict]:
    """The pre-conditions for a supervised physical HOME / STOP test, from what the controller itself
    reports through the read-only collector (RTDE + Dashboard queries). Unknown = not ok.
    Local-mode path: 'Remote control' and 'no program playing' are replaced by the agent's reading - the portal
    program must be PLAYING (started on the pendant) and connected."""
    sm, rm = extra.get("safety_mode"), extra.get("robot_mode")
    remote, pstate = extra.get("remote_control"), str(extra.get("program_state") or "")
    def c(key, name, ok, detail):
        return {"key": key, "name": name, "ok": bool(ok), "detail": detail}
    if UR_PATH == "local_agent":
        ctl = (local or {}).get("controller") or {}
        drv = ctl.get("driver")
        mode_check = [
            c("agent", "Local-mode agent running", local is not None,
              "reachable" if local is not None else "not running / not reachable - nothing can be sent"),
            c("program", "Portal program playing on the pendant (External Control)", drv == "PORTAL_PROGRAM",
              {"PORTAL_PROGRAM": "playing, connected", "OTHER_PROGRAM": "another program is playing",
               "PENDANT_MANUAL": "moved manually (source unconfirmed: by hand or from the pendant)",
               "IDLE": f"press Play on {(local or {}).get('program') or 'the portal program'} on the pendant"}.get(
                  drv, "unknown")),
            c("remote", "Control mode read from the controller", ctl.get("control_mode") in ("LOCAL", "REMOTE"),
              (ctl.get("control_mode") or "unknown").lower() + " (Local mode is supported on this path)"),
        ]
    else:
        mode_check = [
            c("remote", "Remote control enabled on the pendant", remote is True,
              "remote" if remote is True else "local (pendant)" if remote is False else "not reported (Dashboard not read)"),
            c("program", "No other program playing", "PLAYING" not in pstate.upper(),
              pstate or "no program state reported"),
        ]
    return [
        c("source", "A real robot (not the simulator)", not simulated,
          "SIMULATION record - never physical evidence" if simulated else "real robot record"),
        c("telemetry", "Live telemetry", fresh, "fresh" if fresh else "no fresh telemetry from the collector"),
        c("joints", "Joint feedback", bool(q_deg) and len(q_deg) == 6,
          "6 joints, degrees, J1..J6 (base..wrist 3)" if q_deg else "no joint values from the controller"),
        c("safety", "Controller safety mode", isinstance(sm, int) and sm in UR_SAFETY_OK,
          UR_SAFETY_OK.get(sm) or (UR_SAFETY_NAMES.get(sm, f"code {sm}") if sm is not None else "not reported")),
        c("power", "Robot powered and running", rm == 7, "RUNNING" if rm == 7 else f"robot mode {rm!r}"),
        *mode_check,
        c("stop", "STOP not latched", not latched, "clear" if not latched else "latched - admin recovery needed"),
        c("signoff", "Live control signed off (ROBOT_CONTROL=live)", MODE == "live",
          "live" if MODE == "live" else f"{MODE} - nothing is sent until the owner signs off"),
    ]


def fanuc_readiness(fresh: bool, has_joints: bool, simulated: bool = False) -> dict:
    """FANUC: monitoring only. Motion stays disabled until every dependency is established.
    The identity/options evidence belongs to the real controller, never to the simulator."""
    sim = "SIMULATION record - the evidence belongs to the real controller only"
    checks = [
        {"key": "source", "name": "A real robot (not the simulator)", "ok": not simulated,
         "detail": "SIMULATION record - never physical evidence" if simulated else "real robot record"},
        {"key": "telemetry", "name": "Live telemetry", "ok": fresh, "detail": "fresh" if fresh else "no fresh telemetry"},
        {"key": "joints", "name": "Joint feedback", "ok": has_joints,
         "detail": "joint values present" if has_joints else "no joint values from the controller"},
        {"key": "identity", "name": "Controller identity", "ok": not simulated,
         "detail": sim if simulated else f"{FanucAdapter.identity} (SUMMARY.DG, 2026-10-14)"},
        {"key": "options", "name": "Remote-interface options installed", "ok": not simulated,
         "detail": sim if simulated else "R648, R636, R641, KAREL R632, SNPX R553, PNS J515, RSR (DEMO list empty)"},
        {"key": "interface", "name": "Remote command interface configured", "ok": False,
         "detail": "none chosen or configured - motion commands disabled"},
        {"key": "home_program", "name": "Validated HOME TP program", "ok": False,
         "detail": "not written / validated on the pendant yet"},
        {"key": "stop", "name": "Tested normal stop for that interface", "ok": False, "detail": "not identified / tested"},
    ]
    return {"readiness": "BLOCKED", "checks": checks, "dependencies": FanucAdapter.dependencies}
