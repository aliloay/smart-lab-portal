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
