"""
Guided bin calibration (2026-11-20, owner): one button in the portal; the bin node's LCD shows each step
with a countdown, so nobody has to read numbers off a serial monitor.

    CLEAR      platform empty and held still HOLD_S -> the node zeroes itself (same "tare" reply as the
               portal's Zero scale; the node refuses above 60 g)
    ZEROING    two readings near 0 g in a row (also gives inventory._zero_g a fresh zero)
    CONTAINER  the EMPTY container on and held still HOLD_S -> m0
    PIECES     parts in, held still; staff type how many and press Calibrate -> u = (m - m0) / n
    DONE       the LCD shows the result for DONE_SHOW_S, then the bin is back to normal counting

Nothing is booked while a session runs (raw readings are still stored). The node only sends SETTLED
readings (~1/s while steady), so "no reading for FRESH_S" means the weight is moving: the countdown
restarts. In memory: one backend process (uvicorn, no workers), like inventory._PENDING_TARE.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Optional

HOLD_S = 10.0           # held still this long (owner: "wait for 10 seconds", shown as a countdown)
PARTS_HOLD_S = 3.0      # parts in: steady this long before Calibrate is allowed
FRESH_S = 3.0           # no reading for longer = the node is not steady
BAND_G = 0.10           # readings this close to each other count as "held still"
EMPTY_MAX_G = 60.0      # the node refuses a zero above this (PORTAL_TARE_MAX_G in the firmware)
ZERO_OK_G = 0.10        # "zeroed": a reading this close to 0 g
CONTAINER_MIN_G = 2.0   # lighter than this is not a container
PARTS_MIN_G = 0.10      # parts must add at least this (one 10k resistor = 0.2 g)
RETARE_S = 6.0          # ZEROING: ask the node again if it is still not at 0 g after this
DONE_SHOW_S = 15.0
EXPIRE_S = 15 * 60      # an abandoned session ends by itself

STEPS = ("CLEAR", "ZEROING", "CONTAINER", "PIECES", "DONE")


def _now() -> float:            # tests replace this
    return time.time()


@dataclass
class Session:
    bin_id: int
    item_name: str
    user_id: int
    step: str = "CLEAR"
    started: float = field(default_factory=lambda: _now())
    touched: float = field(default_factory=lambda: _now())
    last_g: Optional[float] = None
    last_at: float = 0.0
    hold_ref: Optional[float] = None
    hold_since: float = 0.0
    zero_hits: int = 0
    tare_asked: float = 0.0
    m0: Optional[float] = None
    parts_g: Optional[float] = None
    done_at: float = 0.0
    result: Optional[dict] = None


SESSIONS: dict[int, Session] = {}


def _ascii(s: str, n: int) -> str:
    """LCD-safe: printable ASCII, no quotes or backslashes (the node's JSON reader is minimal)."""
    return re.sub(r'[^ -~]|["\\]', "", s or "")[:n]


def start(bin_id: int, item_name: str, user_id: int) -> Session:
    s = Session(bin_id=bin_id, item_name=_ascii(item_name.strip(), 64) or "Bin", user_id=user_id)
    SESSIONS[bin_id] = s
    return s


def get(bin_id: int) -> Optional[Session]:
    s = SESSIONS.get(bin_id)
    if s is None:
        return None
    now = _now()
    if (s.step == "DONE" and now - s.done_at > DONE_SHOW_S) or (s.step != "DONE" and now - s.touched > EXPIRE_S):
        SESSIONS.pop(bin_id, None)
        return None
    return s


def cancel(bin_id: int) -> bool:
    return SESSIONS.pop(bin_id, None) is not None


def _held(s: Session, now: float) -> float:
    """Seconds the weight has been steady (0 when the last reading is stale: it is moving)."""
    if s.last_at == 0 or now - s.last_at > FRESH_S:
        return 0.0
    return now - s.hold_since


def _reset_hold(s: Session) -> None:
    s.hold_ref, s.hold_since = None, 0.0


def on_reading(s: Session, mass: float) -> bool:
    """Feed one settled reading. Returns True when the node should zero itself now."""
    now = _now()
    s.touched = now
    if s.hold_ref is None or abs(mass - s.hold_ref) > BAND_G or now - s.last_at > FRESH_S:
        s.hold_ref, s.hold_since = mass, now
    s.last_g, s.last_at = mass, now
    held = now - s.hold_since

    if s.step == "CLEAR":
        if abs(mass) <= EMPTY_MAX_G and held >= HOLD_S:
            s.step, s.zero_hits, s.tare_asked = "ZEROING", 0, now
            _reset_hold(s)
            return True
    elif s.step == "ZEROING":
        if abs(mass) <= ZERO_OK_G:
            s.zero_hits += 1
            if s.zero_hits >= 2:
                s.step = "CONTAINER"
                _reset_hold(s)
        else:
            s.zero_hits = 0
            if now - s.tare_asked > RETARE_S and abs(mass) <= EMPTY_MAX_G:
                s.tare_asked = now
                return True
    elif s.step == "CONTAINER":
        if mass >= CONTAINER_MIN_G and held >= HOLD_S:
            s.m0 = round(s.hold_ref if s.hold_ref is not None else mass, 3)
            s.step = "PIECES"
            _reset_hold(s)
    elif s.step == "PIECES":
        s.parts_g = mass if (s.m0 is not None and mass - s.m0 >= PARTS_MIN_G) else None
    return False


def parts_ready(s: Session) -> bool:
    now = _now()
    return (s.step == "PIECES" and s.parts_g is not None and s.m0 is not None
            and _held(s, now) >= PARTS_HOLD_S)


def lcd(s: Session) -> tuple[str, str]:
    """The two 16-character LCD lines for the current step."""
    now = _now()
    held = _held(s, now)
    left = max(0, math.ceil(HOLD_S - held))
    name = _ascii(s.item_name, 10).upper()
    l1 = f"{name} SETUP"
    if s.step == "CLEAR":
        l2 = "Remove all items" if s.last_g is not None and abs(s.last_g) > EMPTY_MAX_G else f"Empty scale {left:>2}s"
    elif s.step == "ZEROING":
        l2 = "Zeroing..."
    elif s.step == "CONTAINER":
        l2 = "Put empty bin on" if s.last_g is None or s.last_g < CONTAINER_MIN_G else f"Empty bin {left:>2}s"
    elif s.step == "PIECES":
        if s.parts_g is None:
            l2 = "Now add parts"
        elif not parts_ready(s):
            l2 = "Hold still..."
        else:
            l2 = "Enter count now"
    else:
        r = s.result or {}
        l1 = "CALIBRATED"
        l2 = f"{r.get('pieces', '?')} pcs {r.get('unit_mass_g', 0):.3f}g"
    return _ascii(l1, 16), _ascii(l2, 16)


def status(s: Session) -> dict:
    now = _now()
    held = _held(s, now)
    l1, l2 = lcd(s)
    return {"active": s.step != "DONE", "step": s.step, "step_no": STEPS.index(s.step) + 1, "steps": len(STEPS),
            "item_name": s.item_name, "last_g": s.last_g,
            "reading_fresh": s.last_at != 0 and now - s.last_at <= FRESH_S,
            "held_s": round(held, 1), "hold_s": HOLD_S, "countdown_s": max(0, math.ceil(HOLD_S - held)),
            "m0_g": s.m0, "parts_g": s.parts_g,
            "net_g": round(s.parts_g - s.m0, 3) if s.parts_g is not None and s.m0 is not None else None,
            "parts_ready": parts_ready(s), "lcd": [l1, l2], "result": s.result}


def finish(s: Session, pieces: int) -> dict:
    """Computes the calibration; the caller saves it on the bin and writes the audit row."""
    if s.step != "PIECES" or not parts_ready(s):
        raise ValueError("Put the parts in and wait until the scale is steady")
    if pieces < 1:
        raise ValueError("Enter how many pieces you put in")
    net = s.parts_g - s.m0
    u = net / pieces
    if u <= 0:
        raise ValueError("The parts weigh nothing on the scale - check the container is on the platform")
    s.result = {"tare_g": round(s.m0, 4), "unit_mass_g": round(u, 5), "pieces": pieces,
                "net_g": round(net, 3), "item_name": s.item_name}
    s.step, s.done_at = "DONE", _now()
    return s.result
