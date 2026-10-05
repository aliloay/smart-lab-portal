"""
Environment monitoring (Robotics Lab, System 2): hazard alerts and the
latest reading of each metric with an honest quality label.

The environment node posts to the existing telemetry endpoint. Hazard
metrics are states (1 = detected, 0 = normal):

  smoke       MQ-2 smoke/gas indication     - not a certified fire alarm
  flame       flame-sensor indication       - supplementary only
  water_leak  leak probe
  emergency   monitored emergency-state signal (the node only watches it)

A hazard raises one CRITICAL alert at once (deduplicated while it lasts),
notifies staff and resolves itself when the node reports it clear. None of
this actuates anything; certified safety systems stay as they are.

Quality of a value shown anywhere:
  VALID          fresh and inside the sensor's physical range
  STALE          older than STALE_AFTER - says nothing about the room now
  MISSING        never reported
  DEVICE_OFFLINE the environment node stopped sending heartbeats
  OUT_OF_RANGE   outside what the sensor can physically report
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (Alert, AlertSeverity, Device, DeviceType, EventType,
                        Lab, SensorReading)
from app.services.devices import is_fresh
from app.services.events import log_event
from app.services.notifications import notify, staff_ids

METRICS = ("temperature", "humidity", "smoke", "flame", "water_leak",
           "motion", "emergency")
STATE_METRICS = ("smoke", "flame", "water_leak", "motion", "emergency")

# The node reports every 30 s; five minutes without a value is stale.
STALE_AFTER = timedelta(minutes=5)

# What each sensor can physically report (DHT22 datasheet ranges; states
# are 0/1). A value outside is a fault, not a measurement.
PHYSICAL_RANGE = {"temperature": (-40.0, 80.0), "humidity": (0.0, 100.0),
                  **{m: (0.0, 1.0) for m in STATE_METRICS}}

HAZARDS = {
    "smoke": ("Smoke/gas detected at {lab}",
              "The MQ-2 smoke/gas indicator triggered. It is not a certified "
              "fire alarm: check the room and follow the building procedure."),
    "flame": ("Flame indication at {lab}",
              "The flame sensor triggered. It is supplementary only: check "
              "the room and follow the building procedure."),
    "water_leak": ("Water leak at {lab}",
                   "The leak probe detected liquid near the equipment."),
    "emergency": ("Emergency state at {lab}",
                  "The monitored emergency signal is active."),
}


HAZARD_LABEL = {"smoke": "smoke/gas indication", "flame": "flame indication",
                "water_leak": "water leak", "emergency": "emergency signal"}


def _key(lab: Lab, metric: str) -> str:
    return f"env:{lab.id}:{metric}"


def _hazard_message(lab: Lab, metric: str, state: str, alert: Optional[Alert],
                    title: str, detail: str) -> dict:
    """The live message behind the portal's full-screen alarm. Published by the
    caller only AFTER the commit, so no page ever shows an alarm that was not saved."""
    return {"type": "hazard", "state": state, "lab_id": lab.id,
            "lab_code": lab.code, "metric": metric,
            "label": HAZARD_LABEL.get(metric, metric), "title": title,
            "detail": detail, "alert_id": alert.id if alert else None,
            "at": datetime.now(timezone.utc).isoformat()}


def publish(messages: list[dict]) -> None:
    """Best effort: the open alerts stay in the database (active_hazards)."""
    try:
        from app.ws.manager import manager
        for m in messages:
            manager.publish(m)
    except Exception:
        pass


def active_hazards(db: Session) -> list[dict]:
    """Every environment hazard still open, newest first (all labs)."""
    rows = db.scalars(select(Alert).where(
        Alert.dedupe_key.like("env:%"), Alert.is_resolved.is_(False))
        .order_by(desc(Alert.created_at))).all()
    out = []
    for a in rows:
        metric = a.dedupe_key.split(":")[2]
        lab = db.get(Lab, a.lab_id) if a.lab_id else None
        out.append({"alert_id": a.id, "lab_id": a.lab_id,
                    "lab_code": lab.code if lab else "", "metric": metric,
                    "label": HAZARD_LABEL.get(metric, metric), "title": a.title,
                    "detail": a.detail, "at": a.created_at.isoformat() if a.created_at else None})
    return out


def record_hazards(db: Session, lab: Lab, device: Optional[Device],
                   readings: list[tuple[str, float]]) -> list[dict]:
    """Open or close the hazard alerts for the states just reported. Returns the
    live messages to publish once the caller has committed."""
    now = datetime.now(timezone.utc)
    messages: list[dict] = []
    for metric, value in readings:
        if metric not in HAZARDS:
            continue
        active = value >= 0.5
        open_alert = db.scalar(select(Alert).where(
            Alert.dedupe_key == _key(lab, metric), Alert.is_resolved.is_(False)))
        title, detail = HAZARDS[metric]
        title = title.format(lab=lab.code)
        if active and open_alert is None:
            alert = Alert(lab_id=lab.id, device_id=device.id if device else None,
                          severity=AlertSeverity.CRITICAL, title=title,
                          detail=detail, dedupe_key=_key(lab, metric))
            db.add(alert)
            db.flush()
            messages.append(_hazard_message(lab, metric, "raised", alert, title, detail))
            log_event(db, EventType.ALARM, lab_id=lab.id,
                      device_id=device.id if device else None,
                      reason=metric.upper(), message=title)
            notify(db, staff_ids(db), "ENVIRONMENT_HAZARD", title, body=detail,
                   link=f"/labs/{lab.id}", severity="critical",
                   dedupe_key=f"{_key(lab, metric)}:{now.isoformat()}")
        elif not active and open_alert is not None:
            open_alert.is_resolved = True
            open_alert.resolved_at = now
            # Free the key for the next episode (dedupe_key is UNIQUE): without
            # this, a second flame in the same lab hit a duplicate-key error and
            # every telemetry post from the node failed with HTTP 500.
            open_alert.dedupe_key = f"{_key(lab, metric)}:{open_alert.id}"
            log_event(db, EventType.DEVICE_ONLINE, lab_id=lab.id,
                      device_id=device.id if device else None,
                      message=f"{title}: cleared")
            messages.append(_hazard_message(lab, metric, "cleared", open_alert, title, detail))
    return messages


def node(db: Session, lab: Lab) -> Optional[Device]:
    return db.scalar(select(Device).where(
        Device.lab_id == lab.id, Device.device_type == DeviceType.SENSOR_NODE)
        .order_by(desc(Device.last_seen_at)))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def latest(db: Session, lab: Lab, now: Optional[datetime] = None) -> dict:
    """Latest value of every environment metric, each with its quality."""
    now = now or datetime.now(timezone.utc)
    dev = node(db, lab)
    online = is_fresh(dev, now) if dev else None
    out = {}
    for m in METRICS:
        r = db.scalar(select(SensorReading).where(
            SensorReading.lab_id == lab.id, SensorReading.metric == m)
            .order_by(desc(SensorReading.recorded_at)))
        if r is None:
            out[m] = {"value": None, "unit": None, "at": None, "quality": "MISSING"}
            continue
        lo, hi = PHYSICAL_RANGE[m]
        if online is False:
            q = "DEVICE_OFFLINE"
        elif now - _utc(r.recorded_at) > STALE_AFTER:
            q = "STALE"
        elif not lo <= r.value <= hi:
            q = "OUT_OF_RANGE"
        else:
            q = "VALID"
        out[m] = {"value": r.value, "unit": r.unit, "at": r.recorded_at, "quality": q}
    return {"node": {"device_uid": dev.device_uid, "online": online,
                     "last_seen_at": dev.last_seen_at} if dev else None,
            "metrics": out,
            "hazards": [m for m in HAZARDS
                        if out[m]["quality"] == "VALID" and out[m]["value"] >= 0.5]}


def history(db: Session, lab: Lab, hours: int = 24,
            now: Optional[datetime] = None) -> dict:
    """What the environment node recorded over a period, for the AI and
    reports: per value metric min/mean/max and count, and every hazard
    episode (from its alert). Only stored data; empty when none was sent."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    rows = db.scalars(select(SensorReading).where(
        SensorReading.lab_id == lab.id, SensorReading.recorded_at >= since,
        SensorReading.metric.in_(("temperature", "humidity")))).all()
    values = {}
    for m in ("temperature", "humidity"):
        v = [r.value for r in rows if r.metric == m]
        values[m] = ({"count": len(v), "min": round(min(v), 2), "mean": round(sum(v) / len(v), 2),
                      "max": round(max(v), 2), "unit": next(r.unit for r in rows if r.metric == m)}
                     if v else {"count": 0})
    episodes = []
    for a in db.scalars(select(Alert).where(
            Alert.lab_id == lab.id, Alert.dedupe_key.like(f"env:{lab.id}:%"),
            Alert.created_at >= since).order_by(Alert.created_at)).all():
        episodes.append({"hazard": a.dedupe_key.split(":")[2], "title": a.title,
                         "started": a.created_at, "cleared": a.resolved_at,
                         "minutes": round((_utc(a.resolved_at) - _utc(a.created_at))
                                          .total_seconds() / 60, 1) if a.resolved_at else None})
    return {"lab": lab.code, "from": since, "to": now, "hours": hours,
            "source": "sensor_readings and alerts written by the environment node",
            "values": values, "hazard_episodes": episodes,
            "now": latest(db, lab, now)}
