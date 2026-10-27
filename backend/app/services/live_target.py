"""
Live Smart Lab camera - the shared TARGET layer (2026-10-27).

The phone camera only says WHAT is in view (a marker = an exact record key, or a face matched to an enrolled
person). Everything shown about it comes from here, read from the authoritative record of that one key:

  live_block(db, card, staff)   the structured live data for one resolved asset (robot joints, bin stock, env
                                readings, door, PC, reusable-bin contents) - each with its timestamp and quality
  person_ticket / person_from_ticket
                                a face match becomes a short-lived signed ticket; a question about "this person"
                                is answered only from a ticket the server itself issued (the phone cannot name
                                anyone by sending a user id)
  answer(db, user, question, target)
                                ONE target-aware answer path for every asset type: the question's intent is
                                resolved deterministically against the target's live data (instant, exact,
                                with sources); only questions no intent covers go to the local model, with the
                                same live data as explicit context.

Nothing here moves a robot: control-like requests are refused (monitoring only).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AccessSession, Alert, Asset, Device, DeviceType, InventoryBin, User
from app.services.devices import is_fresh

ROBOT_STALE_S, ROBOT_OFFLINE_S = 3.0, 30.0          # same limits as routes/robots.py
UR_JOINTS = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
# Numeric modes as documented in the UR RTDE guide - the collector marks them "VERIFY on the controller".
UR_ROBOT_MODE = {-1: "NO_CONTROLLER", 0: "DISCONNECTED", 1: "CONFIRM_SAFETY", 2: "BOOTING", 3: "POWER_OFF",
                 4: "POWER_ON", 5: "IDLE", 6: "BACKDRIVE", 7: "RUNNING", 8: "UPDATING_FIRMWARE"}
UR_SAFETY_MODE = {1: "NORMAL", 2: "REDUCED", 3: "PROTECTIVE_STOP", 4: "RECOVERY", 5: "SAFEGUARD_STOP",
                  6: "SYSTEM_EMERGENCY_STOP", 7: "ROBOT_EMERGENCY_STOP", 8: "VIOLATION", 9: "FAULT"}
TICKET_S = 120                                       # a face match is good for this long without a new one


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _age(dt: Optional[datetime], now: datetime) -> Optional[float]:
    dt = _utc(dt)
    return None if dt is None else round((now - dt).total_seconds(), 1)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


# ------------------------------------------------------------------------------------------ live blocks ---
def robot_live(d: Device, now: datetime) -> dict:
    cs = d.component_state or {}
    age = _age(d.last_seen_at, now)
    conn = ("NO_TELEMETRY" if age is None else "OFFLINE" if age > ROBOT_OFFLINE_S
            else "STALE" if age > ROBOT_STALE_S else "LIVE")
    q, qd = cs.get("q") or [], cs.get("qd") or []
    fanuc = "FANUC" in str(cs.get("model") or d.name).upper()
    joints = []
    for i, v in enumerate(q[:6]):
        if _num(v) is None:
            continue
        vel = _num(qd[i]) if i < len(qd) else None
        joints.append({"index": i + 1, "name": f"J{i + 1}" if fanuc else UR_JOINTS[i],
                       "deg": round(math.degrees(v), 2), "vel_deg_s": None if vel is None else round(math.degrees(vel), 2)})
    tcp = cs.get("tcp")
    tcp_out = None
    if isinstance(tcp, list) and len(tcp) >= 6 and all(_num(x) is not None for x in tcp[:6]):
        tcp_out = {"x_mm": round(tcp[0] * 1000, 1), "y_mm": round(tcp[1] * 1000, 1), "z_mm": round(tcp[2] * 1000, 1),
                   "rx": round(tcp[3], 4), "ry": round(tcp[4], 4), "rz": round(tcp[5], 4),
                   "rotation": "rotation vector, rad" if not fanuc else "W/P/R, rad"}
    extra = cs.get("extra") or {}
    rm, sm = extra.get("robot_mode"), extra.get("safety_mode")
    return {"type": "robot", "connection": conn, "telemetry_age_s": age,
            "received_at": cs.get("received_at"), "model": cs.get("model"), "state": cs.get("state"),
            "control": cs.get("source"), "home": cs.get("home"), "joints_moving": cs.get("joints_moving"),
            "robot_mode": UR_ROBOT_MODE.get(rm, rm) if isinstance(rm, int) else rm,
            "safety_mode": UR_SAFETY_MODE.get(sm, sm) if isinstance(sm, int) else sm,
            "program_state": extra.get("program_state"), "joints": joints, "tcp": tcp_out,
            "rate_hz": cs.get("rate_hz"), "simulation": cs.get("source") == "SIMULATION",
            "note": None if joints else "no joint telemetry in the record"}


def bins_live(db: Session, device_id: Optional[int], now: datetime, codes: Optional[list[str]] = None) -> list[dict]:
    from app.services.inventory import bin_out
    q = select(InventoryBin).where(InventoryBin.is_active.is_(True))
    q = q.where(InventoryBin.code.in_(codes)) if codes else q.where(InventoryBin.device_id == device_id)
    out = []
    for b in db.scalars(q.order_by(InventoryBin.code)).all():
        o = bin_out(db, b, now)
        out.append({"code": b.code, "item": b.item_name, "mass_g": o["mass_g"], "qty_est": o["qty_est"],
                    "qty_err": o["qty_err"], "calibrated": o["calibrated"], "quality": o["quality"],
                    "reorder_qty": o["reorder_qty"], "low": o["low"], "stock_max": o["stock_max"],
                    "measured_at": _utc(o["measured_at"]).isoformat() if o["measured_at"] else None,
                    "age_s": _age(o["measured_at"], now),
                    "count_is": "estimate from weight (calibrated)" if o["qty_est"] is not None else "no count - not calibrated"})
    return out


def reusable_live(db: Session, d: Device, staff: bool, now: datetime) -> dict:
    items = db.scalars(select(Asset).where(Asset.lab_id == d.lab_id,
                                           (Asset.bin_item.is_(True)) | (Asset.nfc_uid.is_not(None)))
                       .order_by(Asset.asset_tag)).all()
    out = []
    for a in items:
        holder = None
        if staff and a.holder_id:
            h = db.get(User, a.holder_id)
            holder = h.full_name if h else None
        out.append({"tag": a.asset_tag, "name": a.name, "status": a.status.value, "holder": holder,
                    "nfc_tagged": a.nfc_uid is not None,
                    "since": _utc(a.checked_out_at).isoformat() if a.checked_out_at else None})
    return {"type": "reusable_bin", "online": bool(is_fresh(d, now)), "items": out,
            "source": "portal checkout/return records (NFC scans at the bin) - the record, not a look inside the bin"}


def env_live(db: Session, d: Device, now: datetime, readings: list[dict]) -> dict:
    alerts = db.scalars(select(Alert).where(Alert.device_id == d.id, Alert.is_resolved.is_(False))
                        .order_by(Alert.id.desc()).limit(5)).all()
    return {"type": "environment", "online": bool(is_fresh(d, now)), "readings": readings,
            "open_alerts": [{"title": a.title, "severity": a.severity.value,
                             "at": _utc(a.created_at).isoformat() if getattr(a, "created_at", None) else None}
                            for a in alerts]}


def live_block(db: Session, card: dict, staff: bool, now: Optional[datetime] = None) -> Optional[dict]:
    """The structured live data for one resolved card (scan.asset_card output)."""
    now = now or datetime.now(timezone.utc)
    if card["kind"] == "bin":
        return {"type": "consumables", "bins": bins_live(db, None, now, [card["key"]])}
    if card["kind"] != "device":
        return None
    d = db.scalar(select(Device).where(Device.device_uid == card["key"]))
    if d is None:
        return None
    cs = d.component_state or {}
    if d.device_type == DeviceType.ROBOT:
        return robot_live(d, now)
    if d.device_type == DeviceType.SENSOR_NODE:
        if cs.get("reusable_bin") is True:
            return reusable_live(db, d, staff, now)
        bins = bins_live(db, d.id, now)
        if bins:
            return {"type": "consumables", "online": bool(is_fresh(d, now)), "bins": bins}
        return env_live(db, d, now, card.get("readings") or [])
    if d.device_type == DeviceType.MASTER_CONTROLLER:
        return {"type": "door", "online": bool(is_fresh(d, now)), "age_s": _age(d.last_seen_at, now),
                "door": None if d.door_closed is None else ("CLOSED" if d.door_closed else "OPEN")}
    if d.device_type == DeviceType.PC:
        return {"type": "pc", "online": bool(is_fresh(d, now)), "age_s": _age(d.last_seen_at, now),
                "agent_state": cs.get("state"), "mode": d.mode or "NORMAL",
                **({"os_user": cs.get("os_user")} if staff else {})}
    return {"type": "device", "online": bool(is_fresh(d, now)), "age_s": _age(d.last_seen_at, now)}


# ------------------------------------------------------------------------------------------- people ---
def _sig(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(settings.SECRET_KEY.encode(), b"scan-person:" + payload,
                                             hashlib.sha256).digest()[:18]).decode()


def person_ticket(user_id: int, score: float, now_s: Optional[float] = None) -> str:
    body = json.dumps({"u": user_id, "s": round(score, 3), "t": int(now_s or time.time())}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(body).decode() + "." + _sig(body)


def person_from_ticket(ticket: str, now_s: Optional[float] = None) -> Optional[dict]:
    try:
        b64, sig = ticket.split(".", 1)
        body = base64.urlsafe_b64decode(b64.encode())
        if not hmac.compare_digest(sig, _sig(body)):
            return None
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if (now_s or time.time()) - data.get("t", 0) > TICKET_S:
        return None
    return data


def mask_id(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = str(v)
    return ("•" * max(0, len(v) - 3)) + v[-3:] if len(v) > 3 else "•" * len(v)


def person_card(db: Session, user_id: int, score: Optional[float], verified_at: Optional[int]) -> Optional[dict]:
    """The approved fields for the camera overlay: name, label, role, department, a MASKED student id and the
    door session - never e-mail, credentials, card UIDs or anything else on the account."""
    u = db.get(User, user_id)
    if u is None or not u.is_active:
        return None
    inside = db.scalar(select(AccessSession).where(AccessSession.user_id == u.id,
                                                   AccessSession.ended_at.is_(None))) is not None
    return {"name": u.full_name, "auth_subject": u.auth_subject, "role": u.role.value, "department": u.department,
            "student_id": mask_id(u.student_id), "inside_by_door": inside, "score": score,
            "verified_at": datetime.fromtimestamp(verified_at, timezone.utc).isoformat() if verified_at else None}


# ------------------------------------------------------------------------------------- intents/answers ---
INTENTS: list[tuple[str, re.Pattern]] = [
    ("control", re.compile(r"^(please )?(move|jog|home|go home|stop|halt|start|run|play|pause|open|unlock|lock|"
                           r"turn (on|off)|power (on|off))\b|\b(can you|could you|please) (move|stop|start|home|open|unlock)\b", re.I)),
    ("who", re.compile(r"\bwho\b", re.I)),
    ("joint", re.compile(r"\bjoint\s*(\d)\b|\bj\s*([1-6])\b|\b(base|shoulder|elbow|wrist\s*[123])\b", re.I)),
    ("tcp", re.compile(r"\b(tcp|tool (centre|center|point)|end[- ]effector|tool position)\b", re.I)),
    ("connected", re.compile(r"\b(connected|connection|online|offline|alive|reachable|reporting|up)\b", re.I)),
    ("stock", re.compile(r"\b(how (much|many)|left|remain\w*|stock|count|weight|weigh|empty|reorder|run(ning)? out)\b", re.I)),
    ("contents", re.compile(r"\b(inside|contain\w*|contents?|what('s| is) in|items?)\b", re.I)),
    ("problems", re.compile(r"\b(wrong|problems?|issues?|alerts?|alarms?|fault\w*|errors?|safe|ok(ay)?|healthy|trust\w*)\b", re.I)),
    ("door", re.compile(r"\b(door|closed|open)\b", re.I)),
    ("state", re.compile(r"\b(tell me more|more|what is (this|it|that)|what('s| is) this|state|status|doing|details?|"
                         r"explain|describe|summar\w*|about (it|this))\b", re.I)),
]


def intent_of(question: str) -> Optional[tuple[str, Optional[re.Match]]]:
    q = question.strip()
    for name, rx in INTENTS:
        m = rx.search(q)
        if m:
            return name, m
    return None


def _fmt_age(s: Optional[float]) -> str:
    if s is None:
        return "never"
    return f"{s:.0f} s ago" if s < 90 else f"{s / 60:.0f} min ago" if s < 5400 else f"{s / 3600:.1f} h ago"


def _robot_answer(intent: str, m: Optional[re.Match], name: str, r: dict) -> list[str]:
    conn = r["connection"]
    head = {"LIVE": f"{name} is connected - telemetry {_fmt_age(r['telemetry_age_s'])}.",
            "STALE": f"{name}'s telemetry is STALE - last update {_fmt_age(r['telemetry_age_s'])}; the values below are "
                     f"not current.",
            "OFFLINE": f"{name} is not reporting - last telemetry {_fmt_age(r['telemetry_age_s'])}. Nothing below is live.",
            "NO_TELEMETRY": f"{name} has never sent telemetry to the portal."}[conn]
    if r.get("simulation"):
        head += " (This record is a SIMULATION, not the physical robot.)"
    if intent == "connected":
        return [head]
    if intent == "joint":
        idx = None
        if m and m.group(1):
            idx = int(m.group(1))
        elif m and m.group(2):
            idx = int(m.group(2))
        elif m and m.group(3):
            w = re.sub(r"\s+", " ", m.group(3).lower()).title()
            idx = next((j["index"] for j in r["joints"] if j["name"] == w), None)
        j = next((j for j in r["joints"] if j["index"] == idx), None)
        if j is None:
            return [head, f"No reading for joint {idx or '?'} in the robot's record."]
        vel = j["vel_deg_s"]
        motion = ("not moving" if vel is not None and abs(vel) < 0.3 else
                  f"moving at {vel:+.1f} deg/s" if vel is not None else "velocity not reported")
        return [f"Joint {j['index']} ({j['name']}) is at {j['deg']:.1f} deg, {motion}.", head]
    if intent == "tcp":
        t = r.get("tcp")
        return [head, "TCP not reported by this controller." if not t else
                f"TCP at x {t['x_mm']} mm, y {t['y_mm']} mm, z {t['z_mm']} mm (base frame; {t['rotation']} "
                f"{t['rx']}, {t['ry']}, {t['rz']})."]
    lines = [head]
    if r.get("state"):
        lines.append(f"State {r['state']}" + (f", control: {r['control']}" if r.get("control") else "") +
                     (f", home: {r['home']}" if r.get("home") else "") + ".")
    if r.get("robot_mode") is not None or r.get("safety_mode") is not None:
        lines.append(f"Controller: robot mode {r.get('robot_mode') or 'not reported'}, safety mode "
                     f"{r.get('safety_mode') or 'not reported'}.")
    if r["joints"]:
        lines.append("Joints: " + ", ".join(f"{j['name']} {j['deg']:.0f}°" for j in r["joints"]) + ".")
    if intent == "problems" and r.get("safety_mode") not in (None, "NORMAL", "REDUCED"):
        lines.append(f"Attention: safety mode is {r['safety_mode']}.")
    return lines


def _bins_answer(intent: str, bins: list[dict]) -> list[str]:
    if not bins:
        return ["No consumables bin is linked to this node in the portal."]
    out = []
    for b in bins:
        if b["qty_est"] is None:
            out.append(f"{b['item']} ({b['code']}): no count - the scale is not calibrated"
                       + (f"; last mass {b['mass_g']:.1f} g" if b["mass_g"] is not None else "") + ".")
            continue
        err = f" ± {b['qty_err']}" if b["qty_err"] else ""
        q = "" if b["quality"] == "VALID" else f" - reading {b['quality'].lower().replace('_', ' ')}"
        out.append(f"{b['item']}: about {b['qty_est']}{err} pieces left (estimate from {b['mass_g']:.1f} g, measured "
                   f"{_fmt_age(b['age_s'])}{q})" + (" - LOW, at or below the reorder level" if b["low"] else "") + ".")
    return out


def answer(db: Session, user: User, question: str, card: Optional[dict], person: Optional[dict]) -> Optional[dict]:
    """A deterministic, sourced answer about the target in view, or None when no intent covers the question
    (the caller then asks the local model with the same live data as context)."""
    it = intent_of(question)
    if it is None:
        return None
    intent, m = it
    if intent == "control":
        return _done("control", ["The camera assistant is monitoring only - it never moves, homes, stops or "
                                 "unlocks anything. Use the robot's own control panel (supervised) or the pendant."],
                     card, person, [])
    if intent == "who" or (person and not card and intent == "state"):
        if not person:
            return _done("who", ["No enrolled person is identified in view. A person stays unnamed unless the face "
                                 "server makes a clear match - point the camera at their face."], card, None, [])
        p = person
        lines = [f"This is {p['auth_subject']} - {p['name']}, {p['role'].replace('_', ' ').lower()}"
                 + (f", {p['department']}" if p.get("department") else "") + ".",
                 "Checked in at the lab door (open session)." if p["inside_by_door"] else "No open door session right now."]
        return _done("who", lines, card, p, [{"label": "face match", "quality": f"score {p['score']}", "at": p["verified_at"]},
                                             {"label": "user account", "quality": "RECORD", "at": None}])
    if card is None:
        return _done(intent, ["Nothing is identified in view yet. Point the camera at a Smart Lab marker (or a "
                              "person's face), or tap a target to select it."], None, person, [])
    live = card.get("live") or {}
    t = live.get("type")
    name = card["name"]
    src = [{"label": card["type"], "quality": card["status"], "at": card.get("last_seen_at")}]
    if t == "robot":
        return _done(intent, _robot_answer(intent, m, name, live), card, person, src)
    if t == "consumables":
        lines = _bins_answer(intent, live.get("bins") or [])
        return _done(intent, lines, card, person, src)
    if t == "reusable_bin":
        items = live["items"]
        avail = [i for i in items if i["status"] == "AVAILABLE"]
        out = [i for i in items if i["status"] == "CHECKED_OUT"]
        lines = [f"{name} is {'online' if live['online'] else 'NOT reporting'}.",
                 f"Per the portal's records: {len(avail)} item(s) available"
                 + (f" ({', '.join(i['name'] for i in avail[:6])})" if avail else "")
                 + f", {len(out)} checked out"
                 + (f" ({', '.join(i['name'] + (' - ' + i['holder'] if i['holder'] else '') for i in out[:6])})" if out else "") + ".",
                 "This is the checkout/return record from NFC scans, not a camera look inside the bin."]
        return _done(intent, lines, card, person, src)
    if t == "environment":
        rd = live.get("readings") or []
        lines = [f"{name} is {'online' if live['online'] else 'NOT reporting'}."]
        if rd:
            lines.append("Readings: " + "; ".join(f"{r['metric']} {r['value']} {r['unit']} ({_fmt_age(r['age_s'])}"
                                                  f"{', STALE' if r['quality'] == 'STALE' else ''})" for r in rd) + ".")
        else:
            lines.append("No readings in the last 24 h - nothing current to report.")
        al = live.get("open_alerts") or []
        lines.append(f"{len(al)} open alert(s) on this node" + (": " + "; ".join(a["title"] for a in al[:3]) if al else "") + ".")
        return _done(intent, lines, card, person, src)
    if t == "door":
        lines = [f"{name} is {'online' if live['online'] else 'NOT reporting'} (last report {_fmt_age(live['age_s'])}).",
                 "Door: not reported." if live["door"] is None else f"Door reported {live['door']}."]
        return _done(intent, lines, card, person, src)
    if t == "pc":
        lines = [f"{name} is {'online' if live['online'] else 'offline'} (last agent report {_fmt_age(live['age_s'])})."]
        if live.get("agent_state"):
            lines.append(f"Agent state {live['agent_state']}, mode {live['mode']}"
                         + (f", signed in: {live['os_user']}" if live.get("os_user") else "") + ".")
        return _done(intent, lines, card, person, src)
    # any other identified asset: its card facts
    lines = [f"{name} ({card['type']}): status {card['status'].replace('_', ' ').lower()}, last report "
             f"{_fmt_age(card.get('seconds_since_seen'))}."]
    lines += [f"{f['label']}: {f['value']}" for f in card.get("facts", [])[:6]]
    return _done(intent, lines, card, person, src)


def _done(intent: str, lines: list[str], card: Optional[dict], person: Optional[dict], sources: list[dict]) -> dict:
    return {"answer": "\n".join(lines), "intent": intent, "deterministic": True,
            "target": {"code": card["code"], "name": card["name"]} if card else
                      ({"person": person["auth_subject"]} if person else None),
            "sources": sources, "model": "smartlab-live-target"}


def context_text(card: Optional[dict], person: Optional[dict]) -> str:
    """The same live data as plain text for the local model (questions no intent covers)."""
    parts = []
    if card:
        parts.append(f"The phone camera is pointed at {card['name']} ({card['type']}, marker {card['code']}). "
                     f"Its live record: {json.dumps(card.get('live') or {}, default=str)[:2500]}")
    if person:
        parts.append(f"The person in view is identified by face as {person['auth_subject']} - {person['name']}, "
                     f"{person['role']}{', ' + person['department'] if person.get('department') else ''}.")
    parts.append("Answer only from this data; say so if it does not contain the answer. Never claim to control anything.")
    return " ".join(parts)
