"""
Advisory safety triage (2026-10-27, backlog 15.2) - ONE ranked list of what staff should look at first, per lab,
combining what the cameras see with the robot, environment, door and access records.

ADVISORY ONLY: nothing here stops, moves, locks or unlocks anything, and it is not a safety function (the robot's
own safety system, the emergency stop and the hazard alarms stay what protects people). Every item carries its
evidence with source and age; stale sources are said to be stale, never used as current.

  P1  environment hazard / evacuation alarm active (environment.active_hazards - fresh nodes only)
  P1  a physical robot MOVING while the camera sees people in the lab ("check people are clear of the robot")
  P2  a physical robot MOVING with nobody checked in at the door and nobody on camera (unattended motion)
  P2  a physical robot MOVING while no camera is reporting (no visual supervision)
  P2  more people on camera than checked in at the door
  P3  door reported open with nobody checked in
  P3  people checked in but the environment node is not reporting (no hazard monitoring)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessSession, Device, DeviceType, Lab
from app.services.devices import is_fresh

ADVISORY = "Advisory only - not a safety function. The robot's own safety system and the emergency stop protect people."


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _age(dt, now) -> Optional[int]:
    dt = _utc(dt)
    return None if dt is None else int((now - dt).total_seconds())


def _ev(source: str, value, age_s: Optional[int]) -> dict:
    return {"source": source, "value": value, "age_s": age_s}


def triage(db: Session, now: Optional[datetime] = None, lab_id: Optional[int] = None) -> list[dict]:
    from app.api.routes.robots import _effective_state
    from app.services.environment import _is_env_node, active_hazards
    now = now or datetime.now(timezone.utc)
    labs = db.scalars(select(Lab).where(Lab.id == lab_id) if lab_id else select(Lab)).all()
    hazards = active_hazards(db)
    items: list[dict] = []

    def add(p, lab, title, action, evidence, key):
        items.append({"priority": p, "lab_id": lab.id, "lab_code": lab.code, "title": title, "action": action,
                      "evidence": evidence, "key": f"{lab.code}:{key}", "advisory": ADVISORY})

    for lab in labs:
        devs = db.scalars(select(Device).where(Device.lab_id == lab.id)).all()
        inside = db.scalar(select(func.count()).select_from(AccessSession).where(
            AccessSession.lab_id == lab.id, AccessSession.ended_at.is_(None))) or 0
        cams = [d for d in devs if d.device_type == DeviceType.SECURITY_CAMERA]
        live_cams = [d for d in cams if is_fresh(d, now) and (d.component_state or {}).get("source_ok") is not False]
        seen = max([int((d.component_state or {}).get("people") or 0) for d in live_cams], default=0)
        cam_ev = [_ev(f"camera {d.device_uid}", f"{(d.component_state or {}).get('people', 0)} people", _age(d.last_seen_at, now))
                  for d in live_cams]

        for h in (x for x in hazards if x["lab_id"] == lab.id):
            add(1, lab, h["title"], "Check the lab now; evacuate if the alarm says so.",
                [_ev("environment" if h["metric"] != "evacuation" else "emergency tab", h["label"], None)], f"hazard:{h['metric']}")

        for r in (d for d in devs if d.device_type == DeviceType.ROBOT):
            cs = r.component_state or {}
            if cs.get("source") == "SIMULATION" or r.device_uid.upper().endswith("_SIM"):
                continue
            state = _effective_state(r, now)
            if state != "MOVING":
                continue
            rev = _ev(f"robot {r.name}", f"MOVING (control {cs.get('source') or 'unknown'})", _age(r.last_seen_at, now))
            if seen > 0:
                add(1, lab, f"{r.name} is moving while the camera sees {seen} person(s) in the lab",
                    "Check that everyone is clear of the robot's reach.", [rev, *cam_ev], f"robot-people:{r.device_uid}")
            elif not live_cams:
                add(2, lab, f"{r.name} is moving and no camera is reporting",
                    "No visual supervision - check the robot in person or restore the camera.", [rev,
                    *[_ev(f"camera {d.device_uid}", "not reporting", _age(d.last_seen_at, now)) for d in cams]],
                    f"robot-nocam:{r.device_uid}")
            if inside == 0 and seen == 0:
                add(2, lab, f"{r.name} is moving with nobody checked in or on camera",
                    "Unattended motion - find who started it (pendant / program).",
                    [rev, _ev("door sessions", "0 inside", None), *cam_ev], f"robot-unattended:{r.device_uid}")

        if live_cams and seen > inside:
            add(2, lab, f"{seen} people on camera but {inside} checked in at the door",
                "Someone may have come in without the door (tailgating) - check the camera.",
                [*cam_ev, _ev("door sessions", f"{inside} inside", None)], "people-mismatch")

        door = next((d for d in devs if d.device_type == DeviceType.MASTER_CONTROLLER), None)
        if door is not None and is_fresh(door, now) and door.door_closed is False and inside == 0:
            add(3, lab, "Door reported open with nobody checked in", "Close the door or check who is there.",
                [_ev("door controller", "OPEN", _age(door.last_seen_at, now)), _ev("door sessions", "0 inside", None)],
                "door-open-empty")

        env = [d for d in devs if d.device_type == DeviceType.SENSOR_NODE and _is_env_node(d)]
        if inside > 0 and env and not any(is_fresh(d, now) for d in env):
            add(3, lab, f"{inside} person(s) inside but the environment node is not reporting",
                "No smoke / flame / gas monitoring right now - check the node.",
                [_ev(f"node {d.device_uid}", "not reporting", _age(d.last_seen_at, now)) for d in env], "env-down-occupied")

    items.sort(key=lambda i: (i["priority"], i["lab_code"]))
    return items
