"""Devices, ESP32 boards, robots and lab PCs - read from the portal's own API (staff sign-in)."""
from __future__ import annotations

from typing import Any, Optional

from ..utils.api_client import Client
from ..utils.errors import NotFound
from ..utils.freshness import NOT_ACCESSIBLE, OFFLINE, ONLINE, STALE, UNKNOWN, human_age

ESP32_TYPES = {"MASTER_CONTROLLER", "SENSOR_NODE", "CAMERA"}
PC_TYPES = {"PC", "LAB_PC"}
ROBOT_TYPES = {"ROBOT"}
CAMERA_TYPES = {"SECURITY_CAMERA", "CAMERA"}

# The portal's own liveness (recomputed on every read) mapped onto the CLI labels.
_PORTAL_STATE = {"ONLINE": ONLINE, "OFFLINE": OFFLINE, "NO_DATA": UNKNOWN, "DEGRADED": "DEGRADED"}


def label(d: dict, stale_after_s: int) -> str:
    st = _PORTAL_STATE.get(str(d.get("state") or "").upper(), UNKNOWN)
    age = d.get("seconds_since_seen")
    if st == ONLINE and isinstance(age, (int, float)) and age > stale_after_s:
        return STALE
    return st


def shape(d: dict, stale_after_s: int) -> dict:
    age = d.get("seconds_since_seen")
    return {
        "uid": d.get("device_uid"), "name": d.get("name"), "type": d.get("device_type"),
        "lab": d.get("lab_code"), "ip": d.get("ip_address"), "firmware": d.get("firmware_version"),
        "status": label(d, stale_after_s), "portal_state": d.get("state"),
        "last_seen": d.get("last_seen_at"), "age_s": age, "age": human_age(age),
        "note": d.get("state_note"),
    }


def all_devices(c: Client, include_retired: bool = False) -> tuple[list[dict], float]:
    data, ms = c.portal("/devices", {"include_retired": "true"} if include_retired else None)
    return [shape(d, c.cfg.stale_after_s) for d in (data or [])], ms


def raw_device(c: Client, uid: str) -> dict:
    data, _ = c.portal("/devices", {"include_retired": "true"})
    for d in data or []:
        if str(d.get("device_uid", "")).lower() == uid.lower():
            return d
    raise NotFound(f"No device with uid {uid!r}", "List them with: smartlab devices list")


def inspect(c: Client, uid: str) -> dict:
    d = raw_device(c, uid)
    out = shape(d, c.cfg.stale_after_s)
    comp = d.get("component_state") or {}
    out["components"] = comp if isinstance(comp, dict) else {}
    out["door_closed"] = d.get("door_closed")
    out["has_own_key"] = d.get("has_own_key")
    return out


def filtered(rows: list[dict], types: Optional[set] = None, status: Optional[str] = None) -> list[dict]:
    out = [r for r in rows if (types is None or r["type"] in types)]
    if status:
        out = [r for r in out if r["status"] == status.upper()]
    return out


def summary(rows: list[dict]) -> dict[str, Any]:
    by: dict[str, dict[str, int]] = {}
    for r in rows:
        by.setdefault(r["type"] or "?", {}).setdefault(r["status"], 0)
        by[r["type"] or "?"][r["status"]] += 1
    return {"total": len(rows), "by_type": by,
            "online": sum(r["status"] == ONLINE for r in rows),
            "not_online": [r["uid"] for r in rows if r["status"] != ONLINE]}


def robots(c: Client) -> tuple[list[dict], float]:
    """Robot twins state from /api/robots (read-only telemetry; control is never exposed)."""
    data, ms = c.portal("/robots")
    items = data.get("robots", data) if isinstance(data, dict) else data
    rows = []
    for r in items or []:
        if not isinstance(r, dict):
            continue
        rows.append({k: r.get(k) for k in ("id", "name", "kind", "mode", "state", "online", "connected",
                                           "program", "safety", "last_seen_at", "source", "simulated")
                     if k in r})
    return rows, ms


def cameras_portal(c: Client) -> list[dict]:
    try:
        data, _ = c.portal("/security/cameras")
    except Exception as e:  # noqa: BLE001 - reported as NOT_ACCESSIBLE, never as online
        return [{"status": NOT_ACCESSIBLE, "detail": getattr(e, "message", str(e))}]
    items = data.get("cameras", data) if isinstance(data, dict) else data
    keep = ("id", "camera_id", "name", "lab", "lab_code", "online", "state", "fps", "live", "last_seen_at")
    return [{k: v for k, v in cam.items() if k in keep} for cam in items or [] if isinstance(cam, dict)]
