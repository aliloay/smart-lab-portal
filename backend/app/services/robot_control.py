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


class URAdapter(Adapter):
    name = "UR5e"
    blocker = ("UR5e: control is off (ROBOT_CONTROL=off).")

    @property
    def interface(self):
        return {"dry_run": f"DRY RUN - nothing is sent (would use Dashboard Server {UR_HOST}:29999)",
                "live": f"Dashboard Server {UR_HOST}:29999"}.get(MODE, "RTDE receive only (monitoring)")

    def capabilities(self) -> dict:
        on = MODE in ("dry_run", "live")
        return {"home": on, "routines": [], "stop": on, "interface": self.interface,
                "home_program": UR_HOME_PROGRAM,
                "unavailable_reason": None if on else self.blocker}

    def controller_mode(self) -> str:
        if MODE == "dry_run":
            return "DRY_RUN_SIMULATED"      # never shown as a real controller state
        if MODE == "live":
            from app.services.ur_dashboard import Dashboard
            return Dashboard(UR_HOST).mode()
        return "UNKNOWN"

    def execute(self, action: str, routine: Optional[str]) -> Result:
        steps = [f"load {UR_HOME_PROGRAM}", "play"] if action == "home" else ["stop"]
        if MODE == "dry_run":
            return Result("DRY_RUN", "checks passed - would send: " + " ; ".join(steps) + " (nothing sent)")
        if MODE != "live":
            return Result("UNAVAILABLE", self.blocker)
        from app.services.ur_dashboard import Dashboard
        d = Dashboard(UR_HOST)
        try:
            replies = [d.ask(c) for c in steps]
        except (OSError, ValueError) as e:
            return Result("FAILED", f"controller did not answer ({e.__class__.__name__}) - state unknown, not retried")
        ok = all(not r.lower().startswith(("error", "failed", "file not found")) for r in replies)
        return Result("REQUESTED" if ok else "REJECTED", " | ".join(replies) +
                      " - watch the twin: only telemetry shows whether it moved")


class FanucAdapter(Adapter):
    name = "FANUC"
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
    lock: threading.Lock = field(default_factory=threading.Lock)


_state = _State()


def reset() -> None:                                   # tests
    with _state.lock:
        _state.owners.clear(); _state.commands.clear()


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
        r = _check(device_id, model, user_id, action, routine, telemetry_age_s)
        r.command_id, r.action = command_id, action
        _state.commands[command_id] = r
        return r


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
    mode = ad.controller_mode()
    if mode == "DRY_RUN_SIMULATED" and MODE == "dry_run":
        return ad.execute(action, routine)          # answers DRY_RUN; sends nothing
    if mode != "REMOTE_READY":
        return Result("UNAVAILABLE", caps["unavailable_reason"] or f"controller not ready ({mode})")
    return ad.execute(action, routine)
