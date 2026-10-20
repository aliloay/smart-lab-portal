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

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (Alert, AlertSeverity, Device, DeviceType, EventType, Lab,
                        SensorReading)
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
    from app.models import Device
    from app.services.devices import is_fresh
    out = []
    for a in rows:
        # A sensor node that stopped reporting cannot say the hazard is still
        # there: no full-screen alarm from a stale reading (the alert stays
        # open on the Alerts page for staff to check and resolve).
        dev = db.get(Device, a.device_id) if a.device_id else None
        if dev is not None and not is_fresh(dev):
            continue
        metric = a.dedupe_key.split(":")[2]
        lab = db.get(Lab, a.lab_id) if a.lab_id else None
        out.append({"alert_id": a.id, "lab_id": a.lab_id,
                    "lab_code": lab.code if lab else "", "metric": metric,
                    "label": HAZARD_LABEL.get(metric, metric), "title": a.title,
                    "detail": a.detail, "at": a.created_at.isoformat() if a.created_at else None})
    return evacuation_alarms(db) + out


def evacuation_alarm(lab: Lab, e) -> dict:
    """An evacuation alarm switched on in the Emergency tab, as a hazard: the
    same full-screen alarm and siren on every signed-in page, not only the
    door buzzer. Its id is negative (no alert row) and changes with every
    emergency change, so a screen that cleared an earlier alarm sounds again."""
    detail = "Evacuation alarm switched on from the Emergency tab. Leave by the nearest exit."
    if e.message:
        detail += f' "{e.message}"'
    return {"alert_id": -(lab.id * 1_000_000 + e.version), "lab_id": lab.id, "lab_code": lab.code,
            "metric": "evacuation", "label": "evacuation alarm", "title": f"EVACUATE {lab.code} now",
            "detail": detail, "at": e.updated_at.isoformat() if e.updated_at else None}


def evacuation_alarms(db: Session) -> list[dict]:
    from app.models import LabEmergency
    out = []
    for e in db.scalars(select(LabEmergency).where(LabEmergency.alarm.is_(True))).all():
        lab = db.get(Lab, e.lab_id)
        if lab is not None:
            out.append(evacuation_alarm(lab, e))
    return out


# Advisories: worth a staff pop-up (orange, no siren), not an evacuation.
def _advisories() -> dict:
    return {
        "temperature": ("temp_high", settings.ENV_TEMP_HIGH_C, settings.ENV_TEMP_NORMAL_C,
                        "Temperature high in {lab}: {v:.1f} C",
                        "Above {hi:.0f} C. Consider ventilation or air conditioning."),
        "humidity": ("humidity_high", settings.ENV_HUMIDITY_HIGH, settings.ENV_HUMIDITY_NORMAL,
                     "Humidity high in {lab}: {v:.0f} %",
                     "Above {hi:.0f} %. Consider ventilation, a dehumidifier or air conditioning."),
    }


def _warning_message(lab: Lab, kind: str, state: str, alert: Alert, title: str,
                     detail: str, value: Optional[float]) -> dict:
    return {"type": "env_warning", "state": state, "kind": kind, "lab_id": lab.id,
            "lab_code": lab.code, "title": title, "detail": detail, "value": value,
            "alert_id": alert.id, "at": datetime.now(timezone.utc).isoformat()}


def record_advisories(db: Session, lab: Lab, device: Optional[Device],
                      readings: list[tuple[str, float]]) -> list[dict]:
    """Comfort limits (temperature / humidity, with hysteresis): WARNING alerts,
    staff notification and an orange pop-up; nothing is switched. Motion start:
    a quiet note only. Returns live messages to publish after the commit."""
    now = datetime.now(timezone.utc)
    messages: list[dict] = []
    dev_id = device.id if device else None
    for metric, value in readings:
        rule = _advisories().get(metric)
        if rule is not None:
            name, hi, normal, title_t, detail_t = rule
            key = _key(lab, name)
            open_alert = db.scalar(select(Alert).where(
                Alert.dedupe_key == key, Alert.is_resolved.is_(False)))
            if value >= hi and open_alert is None:
                title = title_t.format(lab=lab.code, v=value)
                detail = detail_t.format(hi=hi)
                a = Alert(lab_id=lab.id, device_id=dev_id, severity=AlertSeverity.WARNING,
                          title=title, detail=detail, dedupe_key=key)
                db.add(a)
                db.flush()
                notify(db, staff_ids(db), "ENVIRONMENT_ADVISORY", title, body=detail,
                       link=f"/labs/{lab.id}", severity="warning",
                       dedupe_key=f"{key}:{now.isoformat()}")
                messages.append(_warning_message(lab, name, "raised", a, title, detail, value))
            elif value <= normal and open_alert is not None:
                open_alert.is_resolved = True
                open_alert.resolved_at = now
                open_alert.dedupe_key = f"{key}:{open_alert.id}"   # free the key
                messages.append(_warning_message(lab, name, "cleared", open_alert,
                                                 open_alert.title, "Back to normal", value))
        elif metric == "motion" and value >= 0.5:
            # Motion is normal activity: no alert, just a quiet blue note for
            # staff when it STARTS (the node also re-sends 1 every 10 s while
            # it lasts - only the change from "none" counts).
            prev = db.scalar(select(SensorReading.value).where(
                SensorReading.lab_id == lab.id, SensorReading.metric == "motion",
                SensorReading.recorded_at < now - timedelta(seconds=1))
                .order_by(desc(SensorReading.recorded_at)))
            if prev is None or prev < 0.5:
                messages.append({"type": "env_warning", "state": "raised", "kind": "motion",
                                 "lab_id": lab.id, "lab_code": lab.code,
                                 "title": f"Motion detected in {lab.code}",
                                 "detail": "Movement seen by the motion sensors.",
                                 "value": value, "alert_id": None,
                                 "at": now.isoformat()})
    return messages


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
            # A new episode: a new incident, or the recent one REOPENED if the hazard returns within
            # 30 min of clearing (alert_grouping) - every episode is still logged as an ALARM event
            # and notified below, exactly as before.
            from app.services.alert_grouping import raise_or_group
            alert, _ = raise_or_group(db, lab_id=lab.id, device_id=device.id if device else None,
                                      severity=AlertSeverity.CRITICAL, title=title, detail=detail, now=now,
                                      fp=f"hazard:{lab.id}:{metric}", fields={"dedupe_key": _key(lab, metric)})
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
    """The lab's environment node (not a bin: bins are sensor nodes too - see latest_many)."""
    rows = db.scalars(select(Device).where(
        Device.lab_id == lab.id, Device.device_type == DeviceType.SENSOR_NODE)
        .order_by(desc(Device.last_seen_at))).all()
    return next((d for d in rows if _is_env_node(d)), rows[0] if rows else None)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


ENV_COMPONENTS = {"dht22", "pir_1", "pir_2", "mq_1", "flame"}


def _is_env_node(d: Device) -> bool:
    comps = d.component_state if isinstance(d.component_state, dict) else {}
    return (d.device_uid or "").upper().startswith("ENV") or bool(ENV_COMPONENTS & set(comps))


def latest(db: Session, lab: Lab, now: Optional[datetime] = None) -> dict:
    """Latest value of every environment metric, each with its quality."""
    return latest_many(db, [lab], now)[lab.id]


def latest_many(db: Session, labs: list[Lab], now: Optional[datetime] = None) -> dict[int, dict]:
    """latest() for several labs in two queries (the wall screen and the
    environment overview used to run 7 queries per lab)."""
    now = now or datetime.now(timezone.utc)
    ids = [lab.id for lab in labs]
    nodes: dict[int, Device] = {}
    # The lab's ENVIRONMENT node: the bins are sensor nodes too, and "most recently seen" picked a bin
    # (seen every second) - its freshness then decided whether the environment readings counted
    # (2026-10-18). A node reporting environment sensors (or named ENV_*) comes first.
    rows = db.scalars(select(Device).where(
        Device.lab_id.in_(ids), Device.device_type == DeviceType.SENSOR_NODE)
        .order_by(Device.lab_id, desc(Device.last_seen_at))).all()
    for d in sorted(rows, key=lambda d: not _is_env_node(d)):          # stable: env nodes first, newest first
        nodes.setdefault(d.lab_id, d)
    # Newest reading per (lab, metric): one small query each, with its own values, so the planner
    # sees that most labs have no readings and uses the right index. DISTINCT ON sorted the whole
    # table (72 ms, 2026-10-14); the LATERAL join over unnest() that replaced it got a generic plan
    # that walked the whole recorded_at index backwards for every empty (lab, metric) - 55-77 full
    # scans, 1.2-1.6 s per call on 34,112 readings (2026-10-18, /monitor 1.9 s). This: ~60 ms.
    metrics = list(METRICS)
    parts = [f"(SELECT s.id FROM sensor_readings s WHERE s.lab_id = :l{i} AND s.metric = :m{j} "
             f"ORDER BY s.recorded_at DESC LIMIT 1)"
             for i in range(len(ids)) for j in range(len(metrics))]
    params = {**{f"l{i}": lab_id for i, lab_id in enumerate(ids)},
              **{f"m{j}": m for j, m in enumerate(metrics)}}
    newest_ids = db.execute(text(" UNION ALL ".join(parts)), params).scalars().all() if parts else []
    newest: dict[tuple[int, str], SensorReading] = {
        (r.lab_id, r.metric): r for r in db.scalars(
            select(SensorReading).where(SensorReading.id.in_(newest_ids))).all()} if newest_ids else {}
    return {lab.id: _latest_view(nodes.get(lab.id), {m: newest.get((lab.id, m)) for m in METRICS}, now)
            for lab in labs}


def _latest_view(dev: Optional[Device], readings: dict, now: datetime) -> dict:
    online = is_fresh(dev, now) if dev else None
    out = {}
    for m in METRICS:
        r = readings[m]
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
