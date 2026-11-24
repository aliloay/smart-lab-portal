"""Live, one-line answers the assistant used to send to the language model (2026-11-21).

Measured on 21 Nov with both local models: "How many labs are there?" was answered "1" (there are 11), and "Is the
consumables bin online?" got "offline" / "no data" while BIN_NODE_1 had reported seconds earlier. These questions
have exact answers in the records, so they are answered here in milliseconds, never by the model:

  * lab count / list of labs
  * one named device: "is the consumables bin online", "when was PC-02 last seen", "what firmware is the master on"
  * "which ESP32 handles environment monitoring" (role words -> the board)
  * the ESP32 boards together
  * which model each assistant uses
  * the Lab Health Score

Read only. Device state comes from the same device_out() the Devices page uses.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Device, DeviceType, Lab

ESP32_TYPES = (DeviceType.MASTER_CONTROLLER, DeviceType.SENSOR_NODE, DeviceType.CAMERA)

# Role words people use -> which device. (uid prefix or type, phrases). Longest phrase wins.
_ROLES: list[tuple[Any, tuple[str, ...], str]] = [
    ("MASTER", ("master", "master esp32", "master controller", "door controller", "door node", "door esp32",
                "door board", "door access", "access control", "rfid", "fingerprint", "the door"), "door access (RFID, QR, fingerprint, face, lock)"),
    ("ENV", ("environment", "environment node", "environmental", "env node", "environment monitoring",
             "temperature", "humidity", "gas sensor", "flame sensor", "smoke"), "environment monitoring (temperature, humidity, gas, flame)"),
    ("BIN_NODE", ("consumables bin", "consumable bin", "consumables", "bin node", "scale", "load cell",
                  "resistor bin", "consumables node", "bin"), "consumables bin (weighs parts, counts stock)"),
    ("REUSE", ("reusable bin", "reusables bin", "reusables", "reusable", "dock", "reusable node", "bin"),
     "reusable-items dock (borrow / return)"),
    (DeviceType.CAMERA, ("esp32-cam", "esp32 cam", "esp32cam", "entry camera", "door camera"), "door camera (QR and face for the door)"),
    (DeviceType.FACE_SERVER, ("face server", "face recognition server"), "face recognition for the door"),
    ("UR5E", ("ur5e", "ur5", "universal robot"), "UR5e robot (read-only twin)"),
    ("FANUC", ("fanuc",), "FANUC robot (read-only twin)"),
]
_PLURAL = re.compile(r"\b(devices|robots|cameras|pcs|computers|nodes|boards|esp32s|sensors|all)\b")
_STATUS = re.compile(r"\b(online|offline|working|up|down|alive|connected|disconnected|reporting|running|status|state|"
                     r"last seen|seen|firmware|version|ip|address|ok|reachable|responding)\b")
_WHICH_BOARD = re.compile(r"\bwhich\b.*\b(esp32|esp 32|board|node|device|controller|microcontroller)\b")

LAB_COUNT = re.compile(r"\bhow many (labs?|laborator(y|ies))\b|\b(list|show)( me)?( all)?( the)? (labs|laboratories)\b|"
                       r"\bwhat labs (are there|do we have|exist)\b|\bwhich labs (are there|exist|do we have)\b")
ESP32_ALL = re.compile(r"\b(esp32s?|esp 32|esp boards?|nodes|boards)\b.*\b(online|status|state|working|how many|list|which)\b|"
                       r"\b(how many|are the|are all|list|status of the)\b.*\b(esp32s?|esp 32|esp boards?|nodes)\b")
AI_MODEL = re.compile(r"\b(which|what)\b.*\b(model|llm)\b|\bmodel\b.*\b(assistant|ai|using|running|use)\b")
# Lab 24 Nov 2026: these went to the language model, which answered from an old simulation ("running for 2.8 hours"),
# "62 people" and "the lab is empty" while five people were in view.
ROBOT_DOING = re.compile(r"\bwhat('s| is)\b.*\b(doing|up to)\b|\bis\b.*\bmoving\b")
CAM_COUNT = re.compile(r"\bhow many (people|persons|humans)\b.*\b(cameras?|see|seen|visible|in view)\b|"
                       r"\b(cameras?)\b.*\bhow many (people|persons|humans)\b")
LAB_NOW = re.compile(r"\b(summar\w*|overview|status|situation)\b.*\brobotics lab\b|"
                     r"\brobotics lab\b.*\b(summar\w*|overview|status|situation)\b")
LAB_PERIOD = re.compile(r"\b(week|month|yesterday|daily|report|last|year)\b")
HEALTH = re.compile(r"\bhealth score\b|\blab health\b|\bhealth of the lab")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-/.,?!:;()]", " ", s.lower())).strip()


def _has(phrase: str, qn: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(_norm(phrase)) + r"(?![a-z0-9])", qn) is not None


def _key_matches(key, d: Device, uid: str) -> bool:
    # DeviceType is a str enum, so test it before treating the key as a uid prefix
    if isinstance(key, DeviceType):
        return d.device_type == key
    return uid.startswith(key)


def _role_of(d: Device) -> Optional[str]:
    uid = d.device_uid.upper()
    for key, _p, role in _ROLES:
        if _key_matches(key, d, uid):
            return role
    return None


def find_device(devs: list[Device], question: str) -> tuple[Optional[Device], list[Device]]:
    """(device, []) for one clear match, (None, candidates) when several match equally, (None, []) for none."""
    qn = _norm(question)
    scored: dict[int, tuple[int, Device]] = {}

    def hit(d: Device, n: int):
        if n > scored.get(d.id, (0, d))[0]:
            scored[d.id] = (n, d)

    for d in devs:
        for name in {d.device_uid, d.name}:
            if name and len(_norm(name)) >= 3 and _has(name, qn):
                hit(d, 100 + len(name))                       # the uid or the exact name beats any role word
        uid = d.device_uid.upper()
        for key, phrases, _role in _ROLES:
            if _key_matches(key, d, uid):
                for p in phrases:
                    if _has(p, qn):
                        hit(d, len(p))
    if not scored:
        return None, []
    best = max(n for n, _ in scored.values())
    top = [d for n, d in scored.values() if n == best]
    if len(top) > 1:                                  # "the UR5e" means the real one when its simulation twin also matches
        real = [d for d in top if not _is_sim(d)]
        if real and len(real) < len(top):
            top = real
    return (top[0], []) if len(top) == 1 else (None, top)


def _is_sim(d: Device) -> bool:
    return d.device_uid.upper().endswith("_SIM") or (d.component_state or {}).get("source") == "SIMULATION"


def _line(d: Device, now: datetime, when) -> str:
    from app.services.devices import device_out
    o = device_out(d, now=now)
    word = {"ONLINE": "online", "DEGRADED": "partly working", "OFFLINE": "offline", "NO_DATA": "never reported"}
    bits = [f"**{word.get(o.state, o.state.lower())}**",
            f"last report {when(d.last_seen_at) if d.last_seen_at else 'never'}"]
    if d.ip_address:
        bits.append(f"IP {d.ip_address}")
    if d.firmware_version:
        bits.append(f"firmware {d.firmware_version}")
    if o.state == "DEGRADED" and o.state_note:
        bits.append(o.state_note)
    label = o.name if o.name == d.device_uid else f"{o.name} ({d.device_uid})"
    return f"{label}: " + " - ".join(bits)


def _robot_line(d: Device, now: datetime) -> str:
    from app.services.live_target import robot_live
    r = robot_live(d, now)
    age = r["telemetry_age_s"]
    if r["connection"] != "LIVE" or r["state"] not in ("MOVING", "STATIONARY"):
        return (f"{d.name}: **not reporting live** - last telemetry "
                + ("never" if age is None else f"{age:.0f} s ago" if age < 90 else f"{age / 60:.0f} min ago"))
    n = sum(1 for m in (r["joints_moving"] or []) if m)
    doing = (f"**moving** ({n} joint{'s' if n != 1 else ''})" if r["state"] == "MOVING" else "**standing still**")
    mode = f", robot mode {r['robot_mode']}" if r.get("robot_mode") not in (None, "FANUC_WEB") else ""
    return f"{d.name}: {doing} - telemetry {age:.1f} s old{mode}"


def _camera_lines(devs: list[Device], now: datetime) -> list[str]:
    from app.services.devices import is_fresh
    out = []
    for d in devs:
        if d.device_type != DeviceType.SECURITY_CAMERA:
            continue
        cs = d.component_state or {}
        if not is_fresh(d, now):
            out.append(f"{d.name} ({d.device_uid}): not reporting")
            continue
        n = cs.get("people")
        if not isinstance(n, int) or isinstance(n, bool):
            n = len(cs["activity"]) if isinstance(cs.get("activity"), list) else None
        out.append(f"{d.name} ({d.device_uid}): " + ("no people count reported" if n is None else f"**{n}** in view"))
    return out


def _camera_count(devs: list[Device], now: datetime, bullets) -> str:
    lines = _camera_lines(devs, now)
    if not lines:
        return "No security camera is registered."
    return ("**People the cameras see now:**\n" + bullets(lines)
            + "\nThe two views overlap, so the numbers must not be added up.")


def _kb_model() -> Optional[str]:
    """The knowledge assistant's model from its own /status (1.5 s budget; None when not reachable)."""
    try:
        import httpx
        r = httpx.get(settings.KB_SERVICE_URL.rstrip("/") + "/status", headers={"X-KB-Key": settings.KB_SERVICE_KEY},
                      timeout=1.5)
        return r.json().get("model") if r.status_code == 200 else None
    except Exception:  # noqa: BLE001 - optional detail
        return None


def answer(db: Session, question: str, staff: bool, when, answer_fn, bullets) -> Optional[dict]:
    """A live answer, or None to let the other intents / the model handle it."""
    from app.services.devices import is_retired, refresh_liveness
    q = question.lower()
    now = datetime.now(timezone.utc)

    if LAB_COUNT.search(q):
        labs = db.scalars(select(Lab).order_by(Lab.code)).all()
        active = [l for l in labs if l.is_active]
        lines = [f"{l.code} - {l.name}" + (f" ({l.location})" if (l.location or "").strip() else "") for l in active]
        extra = f" ({len(labs) - len(active)} more inactive)" if len(labs) > len(active) else ""
        return answer_fn(f"**{len(active)} labs**{extra}:\n" + bullets(lines), "lab_count",
                         {"label": "Open Laboratories", "to": "/labs"})

    if staff and HEALTH.search(q):
        from app.services.health_score import score_labs
        refresh_liveness(db)
        rows = score_labs(db)
        if not rows:
            return answer_fn("No active lab to score.", "health_score")
        lines = []
        for r in rows:
            weak = r.get("weakest")
            ev = (r.get("parts", {}).get(weak) or {}).get("evidence") if weak else None
            lines.append(f"{r['lab_code']} {r['lab_name']}: **{r['score']:.0f}/100 ({r['band']})**"
                         + (f" - weakest: {weak} ({ev})" if weak else ""))
        return answer_fn("**Lab Health Score** (advisory; ranks attention, does not certify safety):\n" + bullets(lines),
                         "health_score", {"label": "Open Labs", "to": "/labs"})

    # ultracode K2: "model" alone no longer counts as "about the AI" ("What model is the UR5e?" asked the robot)
    if AI_MODEL.search(q) and re.search(r"\b(ai|assistant|chat|llm|you|language model|ollama|qwen|portal)\b", q):
        from app.services import ai
        portal = ai.model_name() or "not configured"
        kb = _kb_model()
        txt = (f"The portal assistant (this chat) uses **{portal}**"
               + (" locally through Ollama" if ai.provider() == "ollama" else "") + ".")
        if kb:
            txt += f" The project-documents assistant uses **{kb}**."
        txt += " Both run on this laptop; the security cameras keep the GPU first."
        return answer_fn(txt, "ai_model")

    if not staff:
        return None                                   # device details (IPs, firmware) are staff-only, as on /devices

    devs = [d for d in refresh_liveness(db) if not is_retired(d)]

    if CAM_COUNT.search(q):
        return answer_fn(_camera_count(devs, now, bullets), "camera_people",
                         {"label": "Open Security camera", "to": "/admin/security"})

    if LAB_NOW.search(q) and not LAB_PERIOD.search(q):
        from sqlalchemy import func
        from app.models import AccessSession, Alert
        lab = db.scalar(select(Lab).where(Lab.name.ilike("%robotics%")).order_by(Lab.code))
        if lab is not None:
            mine = [d for d in devs if d.lab_id == lab.id]
            inside = db.scalar(select(func.count(AccessSession.id)).where(AccessSession.lab_id == lab.id,
                                                                          AccessSession.ended_at.is_(None))) or 0
            alerts = db.scalar(select(func.count(Alert.id)).where(Alert.lab_id == lab.id,
                                                                  Alert.is_resolved.is_(False))) or 0
            lines = [f"Checked in at the door: {inside}", *_camera_lines(mine, now),
                     *[_robot_line(d, now) for d in mine if d.device_type == DeviceType.ROBOT and not _is_sim(d)],
                     f"Open alerts: {alerts}"]
            return answer_fn(f"**{lab.name} now** (from the live records):\n" + bullets(lines), "lab_now",
                             {"label": "Open Laboratories", "to": f"/labs/{lab.id}"})

    if ROBOT_DOING.search(q):
        d, _several = find_device([x for x in devs if x.device_type == DeviceType.ROBOT], question)
        if d is not None:
            return answer_fn(_robot_line(d, now), "robot_now", {"label": "Open Robots", "to": f"/robots/{d.id}"})

    if ESP32_ALL.search(q) and not _WHICH_BOARD.search(q):
        esp = sorted((d for d in devs if d.device_type in ESP32_TYPES), key=lambda d: d.device_uid)
        if not esp:
            return answer_fn("No ESP32 board has been registered.", "esp32_status")
        from app.services.devices import device_out
        on = sum(1 for d in esp if device_out(d, now=now).state == "ONLINE")
        lines = [_line(d, now, when) + (f" - {_role_of(d)}" if _role_of(d) else "") for d in esp]
        return answer_fn(f"**ESP32 boards: {on} of {len(esp)} online**\n" + bullets(lines), "esp32_status",
                         {"label": "Open Devices", "to": "/admin/devices"})

    which = bool(_WHICH_BOARD.search(q))
    if not (which or _STATUS.search(q)) or (_PLURAL.search(q) and not which):
        return None
    d, several = find_device(devs, question)
    if d is None and several:
        return answer_fn("Which one do you mean? " + "; ".join(
            x.name if x.name == x.device_uid else f"{x.name} ({x.device_uid})" for x in several[:6]), "device_status")
    if d is None:
        return None
    role = _role_of(d)
    head = (f"That is **{d.device_uid}**" + (f" - {role}" if role else "") + ".\n") if which else ""
    return answer_fn(head + _line(d, now, when), "device_status", {"label": "Open Devices", "to": "/admin/devices"})
