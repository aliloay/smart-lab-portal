"""
Hardware STOP for the UR5e that works in LOCAL mode, whoever drives the arm (2026-10-26, owner's design).

In Local mode the controller ignores every network stop (Dashboard 'stop' is Remote-only), so a portal STOP can
only reach another person's program, pendant jogging or Freedrive through the controller's own SAFEGUARD STOP
input. An ESP32 (firmware/SmartLab_Robot_Stop) holds two relay contacts closed in that input's two channels while
the portal says RUN; a portal STOP opens them -> the controller performs its safeguard stop (UR: stop category 2,
everything halts, pendant shows "Safeguard stop"). ESP32 power loss also opens them (fail-safe).

The relay mirrors the existing STOP latch (robot_control._state.stops): latched -> relay STOP. So every way the
portal stops the robot (Global STOP button, Stop in the twin, restored latch after a restart) also opens the relay,
and only the administrator recovery closes it again - and only once the robot reports NO program running/paused,
because with no Safeguard Reset input configured, closing the input lets a paused program carry on by itself.

NOT a safety-rated emergency stop (hobby relays, Wi-Fi). The pendant E-stop stays the emergency stop.
Unused until ROBOT_STOP_RELAY_UID is set (the ESP32 registered on Devices with its own key) - wiring needs the
lab's approval (docs/ROBOT_CONTROL.md "Hardware stop relay").
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

RELAY_UID = os.environ.get("ROBOT_STOP_RELAY_UID", "").strip()          # e.g. UR5E_STOP_RELAY
ROBOT_UID = os.environ.get("ROBOT_STOP_RELAY_ROBOT", "UR5E_01").strip()
ONLINE_S = 2.0                     # polled every 200 ms; silent longer than this = offline (shown, not assumed)

_lock = threading.Lock()
_s: dict = {"seq": 0, "wanted": None, "changed_t": None, "poll_t": None, "relay": None, "applied_seq": None,
            "applied_t": None, "latency_ms": None, "fw": None, "rssi": None}


def configured() -> bool:
    return bool(RELAY_UID)


def reset() -> None:                                                       # tests
    with _lock:
        _s.update(seq=0, wanted=None, changed_t=None, poll_t=None, relay=None, applied_seq=None, applied_t=None,
                  latency_ms=None, fw=None, rssi=None)


def poll(wanted_stop: bool, relay: Optional[str], applied_seq: Optional[int], fw: Optional[str] = None,
         rssi: Optional[int] = None, now: Optional[float] = None) -> dict:
    """The ESP32's poll: it reports what its relays do now, gets what they must do."""
    now = now or time.time()
    with _lock:
        if _s["wanted"] is None or wanted_stop != _s["wanted"]:
            _s.update(wanted=wanted_stop, seq=_s["seq"] + 1, changed_t=now)
        _s.update(poll_t=now, fw=fw, rssi=rssi)
        if relay in ("RUN", "STOP"):
            _s["relay"] = relay
        if applied_seq is not None and applied_seq == _s["seq"] and _s["applied_seq"] != applied_seq:
            _s.update(applied_seq=applied_seq, applied_t=now,
                      latency_ms=round((now - (_s["changed_t"] or now)) * 1000))
        return {"stop": _s["wanted"], "seq": _s["seq"], "server_t": round(now, 3)}


def view(wanted_stop: bool, now: Optional[float] = None) -> dict:
    now = now or time.time()
    with _lock:
        online = _s["poll_t"] is not None and now - _s["poll_t"] <= ONLINE_S
        return {"configured": configured(), "uid": RELAY_UID or None, "online": online,
                "last_poll_s": None if _s["poll_t"] is None else round(now - _s["poll_t"], 1),
                "wanted": "STOP" if wanted_stop else "RUN", "relay": _s["relay"] if online else None,
                "in_sync": online and _s["relay"] == ("STOP" if wanted_stop else "RUN"),
                "latency_ms": _s["latency_ms"], "fw": _s["fw"], "rssi": _s["rssi"]}


def release_blocker(program_state: Optional[str]) -> Optional[str]:
    """Closing the relay after a STOP: refused unless the controller reports no program running or paused."""
    p = str(program_state or "").upper()
    if not p:
        return ("the robot's program state is unknown - closing the stop relay could let a paused program carry "
                "on; start the UR agent / monitor first")
    if p.startswith("PLAYING") or p.startswith("PAUSED"):
        return ("a program is still loaded as " + p.split()[0] + " - press Stop on the teach pendant first, then "
                "recover (closing the stop relay would let it carry on by itself)")
    return None
