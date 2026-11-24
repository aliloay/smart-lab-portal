"""
Metric registry and measurement views (2026-11-23, affordable expansion).

One description per metric (unit, physical range, cadence, calibration state), applied to the rows that already
exist in sensor_readings - no new table and no new database. Every value leaves here with device, time, quality,
freshness and provenance. A metric with status PLANNED has no sensor yet: it is described, never charted.

Occupancy stays aggregate: only the motion state of a zone is used, never a person or a name.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Device, DeviceType
from app.services.devices import is_fresh, is_retired, is_simulated

IMPL, PLAN = "IMPLEMENTED", "PLANNED"


def _m(label, unit, lo, hi, every_s, calib, *, kind="gauge", group="environment", status=IMPL, source="", note=""):
    return {"label": label, "unit": unit, "min": lo, "max": hi, "interval_s": every_s, "calibration": calib,
            "kind": kind, "group": group, "status": status, "source": source, "note": note}


DATASHEET = "datasheet accuracy, not calibrated here"
IND = "indicator only, not a certified instrument"
_NET = "a counter reset makes a negative value; those are excluded"
_FW = "needs the prepared env firmware; no parts"
_LV = "low-voltage side only"
REGISTRY: dict[str, dict] = {
    "temperature": _m("Temperature", "°C", -40, 80, 10, DATASHEET, source="DHT22"),
    "humidity": _m("Humidity", "%", 0, 100, 10, DATASHEET, source="DHT22"),
    "smoke": _m("Smoke / gas indication", "state", 0, 1, 10, IND, kind="state", source="MQ-2"),
    "flame": _m("Flame indication", "state", 0, 1, 10, IND, kind="state", source="flame board"),
    "motion": _m("Motion (zone, no identity)", "state", 0, 1, 10, "not applicable", kind="state", group="occupancy",
                 source="PIR"),
    "pc_cpu_pct": _m("PC processor load", "%", 0, 100, 60, "not applicable", group="computers", source="PC agent"),
    "pc_ram_pct": _m("PC memory use", "%", 0, 100, 60, "not applicable", group="computers", source="PC agent"),
    "pc_disk_pct": _m("PC disk use", "%", 0, 100, 60, "not applicable", group="computers", source="PC agent"),
    "pc_net_rx_kbps": _m("PC network in", "kbps", 0, 1_000_000, 60, "not applicable", group="computers",
                         source="PC agent", note=_NET),
    "pc_net_tx_kbps": _m("PC network out", "kbps", 0, 1_000_000, 60, "not applicable", group="computers",
                         source="PC agent", note=_NET),
    # firmware source prepared (env-0.2.0), not flashed
    "wifi_rssi_dbm": _m("Wi-Fi signal", "dBm", -120, 0, 60, "not applicable", group="node health", status=PLAN,
                        source="ESP32", note=_FW),
    "device_uptime_s": _m("Node uptime", "s", 0, 4_294_968, 60, "not applicable", group="node health", status=PLAN,
                          source="ESP32", note=_FW),
    "free_heap_b": _m("Node free memory", "B", 0, 520_000, 60, "not applicable", group="node health", status=PLAN,
                      source="ESP32", note=_FW),
    # parts not bought
    "co2_ppm": _m("CO2", "ppm", 400, 5000, 60, "needs fresh-air reference", status=PLAN, source="SCD41"),
    "illuminance_lux": _m("Light level", "lux", 0, 65535, 60, "needs reference lux meter", status=PLAN, source="BH1750"),
    "pm25_ug_m3": _m("PM2.5", "µg/m³", 0, 500, 60, "factory only", status=PLAN, source="PMS5003"),
    "noise_db_a": _m("Noise level (no audio kept)", "dBA", 30, 120, 60, "needs reference sound meter", status=PLAN,
                     source="INMP441"),
    "vibration_rms": _m("Vibration RMS", "m/s²", 0, 160, 60, "per-machine baseline needed", group="equipment",
                        status=PLAN, source="accelerometer"),
    "water_leak": _m("Water leak", "state", 0, 1, 10, "wet test", kind="state", status=PLAN, source="leak probe"),
    "voltage_v": _m("Supply voltage", "V", 0, 26, 60, "compare with multimeter", group="power", status=PLAN,
                    source="INA219", note=_LV),
    "current_a": _m("Supply current", "A", 0, 3.2, 60, "compare with multimeter", group="power", status=PLAN,
                    source="INA219", note=_LV),
    "power_w": _m("Supply power", "W", 0, 83, 60, "compare with multimeter", group="power", status=PLAN,
                  source="INA219", note=_LV),
}
PERIODS = {"24h": (24, 900), "7d": (168, 3600), "30d": (720, 14400), "90d": (2160, 43200)}   # hours, bucket seconds


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def quality(metric: str, value: float, age_s: float, device_fresh: Optional[bool]) -> str:
    m = REGISTRY.get(metric)
    if m is None:
        return "UNREGISTERED"
    if not (m["min"] <= value <= m["max"]):
        return "OUT_OF_RANGE"
    if device_fresh is False:
        return "DEVICE_OFFLINE"
    return "STALE" if age_s > max(300, 5 * m["interval_s"]) else "VALID"


def latest(db: Session, now: Optional[datetime] = None) -> list[dict]:
    """The newest reading of every device and metric, looking 90 days back."""
    now = now or datetime.now(timezone.utc)
    devs = {d.id: d for d in db.query(Device).all() if not is_retired(d)}
    out = []
    for r in db.execute(text(
            "select distinct on (device_id, metric) device_id, metric, value, recorded_at, provenance "
            "from sensor_readings where device_id is not null and recorded_at > :a and recorded_at <= :b "
            "order by device_id, metric, recorded_at desc"), {"a": now - timedelta(days=90), "b": now}):
        d, m = devs.get(r.device_id), REGISTRY.get(r.metric)
        if d is None:
            continue
        age = (now - _utc(r.recorded_at)).total_seconds()
        out.append({"device_id": d.id, "device_uid": d.device_uid, "device_name": d.name,
                    "sensor_id": f"{d.device_uid}:{r.metric}", "metric_name": r.metric,
                    "label": m["label"] if m else r.metric, "unit": m["unit"] if m else "",
                    "group": m["group"] if m else "other", "kind": m["kind"] if m else "gauge",
                    "value": r.value, "timestamp": _utc(r.recorded_at).isoformat(), "freshness": round(age),
                    "quality": quality(r.metric, r.value, age, is_fresh(d, now)),
                    "source": m["source"] if m else "unknown", "calibration_status": m["calibration"] if m else "unknown",
                    "sampling_interval": m["interval_s"] if m else None,
                    "metadata": {"provenance": r.provenance, "simulated": is_simulated(d) or r.provenance == "DEMO_DATA"}})
    return out


def _buckets(db: Session, device_id: int, metric: str, start: datetime, end: datetime, step: int) -> list[dict]:
    m = REGISTRY[metric]
    return [{"t": datetime.fromtimestamp(int(r.b), timezone.utc).isoformat(),
             "avg": None if r.avg is None else round(r.avg, 3), "min": r.lo, "max": r.hi, "n": r.n, "rejected": r.bad}
            for r in db.execute(text(
                "select floor(extract(epoch from recorded_at)/:s)*:s as b, "
                "avg(value) filter (where value between :lo and :hi) as avg, "
                "min(value) filter (where value between :lo and :hi) as lo, "
                "max(value) filter (where value between :lo and :hi) as hi, "
                "count(*) filter (where value between :lo and :hi) as n, "
                "count(*) filter (where not value between :lo and :hi) as bad "
                # every lab a device ever reported to: the (lab, metric, time) index serves this
                "from sensor_readings where lab_id in (select id from labs) and metric = :m and device_id = :d "
                "and recorded_at >= :a and recorded_at < :b group by 1 order by 1"),
                {"s": step, "lo": m["min"], "hi": m["max"], "m": metric, "d": device_id, "a": start, "b": end})]


def _stats(rows: list[dict]) -> dict:
    n = sum(r["n"] for r in rows)
    rejected = sum(r["rejected"] for r in rows)
    if not n:
        return {"n": 0, "avg": None, "min": None, "max": None, "rejected": rejected}
    good = [r for r in rows if r["n"]]
    return {"n": n, "avg": round(sum(r["avg"] * r["n"] for r in good) / n, 3), "min": min(r["min"] for r in good),
            "max": max(r["max"] for r in good), "rejected": rejected}


def history(db: Session, device_id: int, metric: str, period: str, now: Optional[datetime] = None) -> dict:
    """Bucketed series with the same period before it, coverage, and gaps. Empty buckets stay empty (no interpolation)."""
    now = now or datetime.now(timezone.utc)
    hours, step = PERIODS[period]
    start = now - timedelta(hours=hours)
    rows = _buckets(db, device_id, metric, start, now, step)
    prev = _buckets(db, device_id, metric, start - timedelta(hours=hours), start, step)
    t0 = int(start.timestamp() // step) * step
    by = {r["t"]: r for r in rows}
    series, gaps, gap = [], [], None
    for b in range(t0, int(now.timestamp()) + 1, step):
        t = datetime.fromtimestamp(b, timezone.utc).isoformat()
        r = by.get(t) or {"t": t, "avg": None, "min": None, "max": None, "n": 0, "rejected": 0}
        series.append(r)
        if r["n"]:
            gap = None
        elif gap is None:
            gap = {"from": t, "to": t}
            gaps.append(gap)
        else:
            gap["to"] = t
    last = [r for r in rows if r["n"]][-2:]
    change = None
    if len(last) == 2 and REGISTRY[metric]["kind"] == "gauge":
        dt = (datetime.fromisoformat(last[1]["t"]) - datetime.fromisoformat(last[0]["t"])).total_seconds()
        if dt <= 2 * step:
            change = round((last[1]["avg"] - last[0]["avg"]) * 3600 / dt, 3)
    return {"metric": {**REGISTRY[metric], "name": metric}, "device_id": device_id, "period": period,
            "bucket_s": step, "from": start.isoformat(), "to": now.isoformat(), "series": series,
            "stats": _stats(rows), "previous": _stats(prev),
            "coverage_pct": round(100 * sum(1 for x in series if x["n"]) / len(series), 1),
            "gaps": gaps[-20:], "gap_count": len(gaps), "change_per_hour": change,
            "generated_at": now.isoformat()}


def coverage(db: Session, days: int, now: Optional[datetime] = None) -> list[dict]:
    """Reporting coverage per device: hours with at least one reading / hours in the window. This is data coverage,
    not proof of uptime: a device that is switched off on purpose also lowers it."""
    now = now or datetime.now(timezone.utc)
    names = {d.id: d for d in db.query(Device).all() if not is_retired(d) and not is_simulated(d)}
    out = []
    for r in db.execute(text("select device_id, count(distinct date_trunc('hour', recorded_at)) as h, "
                             "count(*) as n, max(recorded_at) as last from sensor_readings "
                             "where recorded_at >= :a and recorded_at < :b and device_id is not null group by 1"),
                        {"a": now - timedelta(days=days), "b": now}):
        d = names.get(r.device_id)
        if d:
            out.append({"device_id": d.id, "device_uid": d.device_uid, "device_name": d.name, "hours_with_data": r.h,
                        "window_hours": days * 24, "coverage_pct": round(min(100, 100 * r.h / (days * 24)), 1),
                        "readings": r.n, "last": _utc(r.last).isoformat()})
    return sorted(out, key=lambda x: -x["coverage_pct"])


def diagnose(db: Session, dev: Device, now: Optional[datetime] = None) -> dict:
    """What the records show about one device. Rules only; each cause lists its evidence, and nothing is acted on."""
    now = now or datetime.now(timezone.utc)
    fresh, ev, causes, checks = is_fresh(dev, now), [], [], []
    last = _utc(dev.last_seen_at) if dev.last_seen_at else None
    base = {"device_id": dev.id, "device_uid": dev.device_uid, "name": dev.name, "generated_at": now.isoformat(),
            "statement": "Correlation from stored records, not proof. Nothing was changed."}
    if last is None:
        return {**base, "state": "UNKNOWN", "what_happened": "This device has never reported to the portal.",
                "evidence": [], "causes": [], "missing_evidence": ["no heartbeat, no readings"],
                "checks": ["Is it installed, powered and configured?"], "human_action": True, "similar_incidents": []}
    if is_simulated(dev):
        return {**base, "state": "SIMULATION", "what_happened": "This is a simulator, not a physical device.",
                "evidence": [], "causes": [], "missing_evidence": [], "checks": [], "human_action": False,
                "similar_incidents": []}
    age = (now - last).total_seconds()
    ev.append(f"last heartbeat {last.isoformat(timespec='seconds')}")
    alerts = db.execute(text("select title, created_at, occurrences, is_resolved from alerts "
                             "where device_id = :d and created_at > :a order by created_at desc limit 8"),
                        {"d": dev.id, "a": now - timedelta(days=30)}).all()
    off = [a for a in alerts if "offline" in (a.title or "").lower()]
    # Peers: the other non-PC nodes of the same lab, compared with the moment this one went silent.
    peers = [d for d in db.query(Device).filter(Device.lab_id == dev.lab_id, Device.id != dev.id).all()
             if not is_retired(d) and not is_simulated(d) and d.last_seen_at and d.device_type != DeviceType.PC]
    same = [d for d in peers if abs((_utc(d.last_seen_at) - last).total_seconds()) <= 120 and not is_fresh(d, now)]
    alive = [d for d in peers if is_fresh(d, now)]
    state_words = ("servo_locked_out", "locked_by_portal", "lid_closed", "door_open", "source_ok")
    bad = [k for k, v in (dev.component_state or {}).items() if v is False and k not in state_words]
    rssi = db.execute(text("select value from sensor_readings where device_id = :d and metric = 'wifi_rssi_dbm' "
                           "and recorded_at > :a order by recorded_at desc limit 1"),
                      {"d": dev.id, "a": last - timedelta(minutes=30)}).first()
    if rssi:
        ev.append(f"last Wi-Fi signal {rssi.value:.0f} dBm")
    missing = [] if rssi or dev.device_type == DeviceType.PC else ["Wi-Fi signal is not recorded for this device"]
    missing += ["supply voltage is not measured", "packet loss is not recorded"]
    if not fresh:
        if len(same) >= 2 and not alive:
            causes.append({"cause": "A shared cause: power, network, or the portal was off", "confidence": "medium",
                           "evidence": [f"{len(same)} other lab device(s) stopped within 2 minutes: "
                                        + ", ".join(d.device_uid for d in same),
                                        "no other device of this lab reports now"]})
            checks += ["Is this laptop on the lab network?", "Are the 12 V supply and the router on?"]
        elif len(same) >= 2:
            causes.append({"cause": "Part of the lab network or a shared supply", "confidence": "low",
                           "evidence": [f"{len(same)} device(s) stopped together, but {len(alive)} still report(s)"]})
            checks.append("Compare the supply and switch of the silent devices with the working ones")
        else:
            causes.append({"cause": "This device, its cable or its own power", "confidence": "medium" if alive else "low",
                           "evidence": ([f"{len(alive)} other device(s) of the lab still report"] if alive else
                                        ["fewer than two other devices stopped at the same moment"])})
            checks.append("Look at its power LED and cable, then its serial log")
        if rssi and rssi.value <= -80:
            causes.append({"cause": "Weak Wi-Fi", "confidence": "medium" if alive else "low",
                           "evidence": [f"signal was {rssi.value:.0f} dBm shortly before it stopped"]})
            checks.append("Compare the signal again after moving the node or the access point")
    if bad:
        causes.append({"cause": "Component reported as failed: " + ", ".join(bad),
                       "confidence": "high" if fresh else "low",
                       "evidence": ["the device's own last self-report" + ("" if fresh else " (old: it is silent now)")]})
        checks.append("Check the wiring of: " + ", ".join(bad))
    if len(off) >= 3:
        causes.append({"cause": "Unstable connection (it keeps dropping)", "confidence": "medium",
                       "evidence": [f"{len(off)} offline alerts in 30 days"]})
    order = {"high": 0, "medium": 1, "low": 2}
    causes.sort(key=lambda c: order[c["confidence"]])
    state = "ONLINE" if fresh else "OFFLINE" if age > 86400 else "STALE"
    what = ("It is reporting normally." if fresh and not bad else
            "It is reporting, but a component reports a fault." if fresh else
            f"It stopped reporting {round(age / 3600, 1)} h ago.")
    return {**base, "state": state, "what_happened": what, "evidence": ev, "causes": causes,
            "missing_evidence": missing, "checks": checks, "human_action": state != "ONLINE" or bool(bad),
            "similar_incidents": [{"title": a.title, "at": _utc(a.created_at).isoformat(), "resolved": a.is_resolved,
                                   "occurrences": a.occurrences} for a in alerts]}


_TIMELINE = {
    "alert": "select created_at as ts, title as text, severity::text as level, device_id, id from alerts",
    # Door rows carry no person and not the free message (it can hold a name).
    "door": "select created_at as ts, event_type::text as text, coalesce(result::text, 'INFO') as level, device_id, id "
            "from access_events",
    "pc": "select started_at as ts, state as text, 'INFO' as level, device_id, id from equipment_sessions",
    "robot": "select occurred_at as ts, kind as text, severity as level, device_id, id from robot_events "
             "where source <> 'SIMULATION'",
    "maintenance": "select created_at as ts, 'Issue reported' as text, severity::text as level, "
                   "cast(null as integer) as device_id, id from issues",
    "automation": "select occurred_at as ts, event_type::text as text, delivery_status::text as level, "
                  "cast(null as integer) as device_id, id from integration_events",
}


def timeline(db: Session, hours: int, kinds: set[str], limit: int = 200, now: Optional[datetime] = None) -> dict:
    """One ordered list from the existing tables. People are not listed: access decisions stay on Access & audit."""
    now = now or datetime.now(timezone.utc)
    names = {d.id: d.device_uid for d in db.query(Device).all()}
    items, errors = [], []
    for k in [k for k in _TIMELINE if k in kinds]:
        try:
            with db.begin_nested():
                rows = db.execute(text(f"select * from ({_TIMELINE[k]}) x where ts > :a and ts <= :b order by ts desc limit :n"),
                                  {"a": now - timedelta(hours=hours), "b": now, "n": limit + 1}).all()
        except Exception as e:
            errors.append(f"{k}: {e.__class__.__name__}")
            continue
        items += [{"kind": k, "id": r.id, "at": _utc(r.ts).isoformat(), "text": (r.text or "").replace("_", " "),
                   "level": r.level or "INFO", "device_uid": names.get(r.device_id)} for r in rows]
    items.sort(key=lambda x: x["at"], reverse=True)
    return {"items": items[:limit], "truncated": len(items) > limit, "unavailable": errors, "hours": hours,
            "generated_at": now.isoformat(), "privacy": "Device and system events only; people are not listed here."}


# ---------------------------------------------------------------- fast answers for the assistant ---------------
# Spoken names -> metric. Only these words are understood; anything else goes to the normal assistant.
_WORD = {"temperature": "temperature", "humidity": "humidity", "smoke": "smoke", "gas": "smoke", "flame": "flame",
         "motion": "motion", "pc processor load": "pc_cpu_pct", "pc memory use": "pc_ram_pct", "pc disk use": "pc_disk_pct",
         "co2": "co2_ppm", "light level": "illuminance_lux", "light": "illuminance_lux", "noise level": "noise_db_a",
         "noise": "noise_db_a", "vibration": "vibration_rms", "pm2.5": "pm25_ug_m3", "water leak": "water_leak",
         "wi-fi signal": "wifi_rssi_dbm", "wifi signal": "wifi_rssi_dbm", "node uptime": "device_uptime_s",
         "node free memory": "free_heap_b", "supply voltage": "voltage_v", "supply current": "current_a",
         "supply power": "power_w"}
_W = "(?P<w>" + "|".join(sorted(map(re.escape, _WORD), key=len, reverse=True)) + ")"
_U = r"(?P<uid>[a-z][a-z0-9]*(?:_[a-z0-9]+)+)"                       # a device id such as env_lab01
_SPAN = r"(?:in|over|during|for) the (?:last|past) (?P<span>24 hours|7 days|30 days|90 days|day|week|month)"
_PERIOD = {"24 hours": "24h", "day": "24h", "7 days": "7d", "week": "7d", "30 days": "30d", "month": "30d", "90 days": "90d"}
_HOURS = {"24h": 24, "7d": 168, "30d": 720}
_ANS: list[tuple[str, re.Pattern]] = [(k, re.compile(r"(?:please |can you tell me |tell me )?" + p)) for k, p in [
    ("def", rf"(?:what|which) sensor (?:measures|gives) (?:the )?{_W}"),
    ("def", rf"how is (?:the )?{_W} (?:measured|calibrated)"),
    ("def", rf"how (?:accurate|reliable|certain) is the {_W}(?: reading| sensor| measurement)?"),
    ("def", rf"how often is (?:the )?{_W} (?:measured|sampled|recorded)"),
    ("def", rf"(?:what|which) (?:unit|range) (?:is|does) (?:the )?{_W}(?: in| have| use)?"),
    ("def", rf"what (?:is|are) the (?:limits|valid range|units?) (?:of|for) (?:the )?{_W}"),
    ("def", rf"(?:can|does) the lab measure (?:the )?{_W}"),
    ("stat", rf"what was the (?P<f>average|mean|highest|maximum|lowest|minimum) (?:lab )?{_W} {_SPAN}"),
    ("stat", rf"how (?:much|many) (?P<f>data|readings|gaps) (?:is|are|do we have) (?:there )?(?:for|of|in) (?:the )?{_W}(?: data)? {_SPAN}"),
    ("last", rf"when was the last {_W} (?:reading|measurement)"),
    ("last", rf"how old is the (?:last |latest )?{_W} (?:reading|measurement)"),
    ("last", rf"which (?:device|node|board) (?:measures|reports|sends) (?:the )?{_W}"),
    ("seen", rf"when (?:did {_U} last report|was {_U.replace('uid', 'uid2')} last seen)"),
    ("diag", rf"why (?:is|did) {_U} (?:offline|stale|silent|not reporting|stop reporting)"),
    ("diag", rf"what (?:happened to|is wrong with) {_U}"),
    ("diag", rf"what should (?:i|we) check (?:on|for) {_U}"),
    ("diag", rf"what evidence is there (?:for|about) {_U}"),
    ("events", rf"what (?:happened|events were recorded) {_SPAN}"),
    ("events", rf"how many (?P<k>alerts|robot events|maintenance reports|door events|automation events) (?:were there|were recorded) {_SPAN}"),
    ("gone", r"(?:what|which measurements?) can(?: ?no|')t (?:the lab|we) measure(?: yet)?"),
    ("gone", r"(?:what|which) (?:sensors?|measurements?) (?:is|are) (?:missing|planned|not installed)(?: yet)?"),
    ("have", r"(?:what|which measurements?) (?:can|does) (?:the lab|the system|we) measure(?: now)?"),
    ("silent", r"which (?:sensors?|nodes?|devices?|esp32s?) (?:has|have|is|are) (?:not report(?:ed|ing)|silent|not responding)"
               r"(?: recently| now| lately)?"),
    ("silent", r"(?:what|which) (?:sensor|node|device)s? stopped reporting(?: recently| lately)?"),
    ("wifi", r"which (?:node|device|esp32|board) has the (?:weakest|worst|lowest) (?:wi-?fi|signal|rssi)(?: signal)?"),
    ("drops", r"which (?:node|device|esp32|board) has (?:the )?most (?:reconnects|dropouts|disconnections|offline alerts)"),
    ("trend", r"is (?:the )?(?:lab )?(temperature|humidity) (?:increasing|rising|going up|changing)(?: unusually| too)?(?: quickly| fast)?"),
    ("coverage", r"which (?:sensor|device|node) has the (?:best|worst|lowest|highest) (?:data )?coverage(?: this week)?"),
    ("planned", r"(?:is (?:the )?(?:lab )?air quality (?:ok|good|acceptable|safe)|what is the (?:lab )?air quality)"),
    ("planned", r"(?:what is|how much is) the (?:lab )?(?:co2|noise|light|pm2\.?5|vibration)(?: level)?(?: now)?"),
    ("planned", r"how much energy was used (?:today|this week)"),
    ("planned", r"which equipment has (?:unusual|high|the most) vibration"),
    ("calib", r"(?:what|which sensors?|which measurements?) needs? calibration"),
]]


def fast_answer(db: Session, question: str, now: Optional[datetime] = None) -> Optional[str]:
    """A whole-question match only: an extra clause ('yesterday', 'in the cafeteria', 'and open the door') never
    matches, so it goes on to the normal assistant instead of getting the wrong live value."""
    qn = re.sub(r"\s+", " ", question.lower().strip().rstrip("?!. "))
    hit = next(((k, m) for k, p in _ANS if (m := p.fullmatch(qn))), None)
    if not hit:
        return None
    now = now or datetime.now(timezone.utc)
    kind, m = hit
    g = {k: v for k, v in m.groupdict().items() if v}
    stamp = f"\n\n_Source: portal records, {now.isoformat(timespec='seconds')}._"
    real = [d for d in db.query(Device).all() if not is_retired(d) and not is_simulated(d)]
    nodes = [d for d in real if d.device_type in (DeviceType.SENSOR_NODE, DeviceType.MASTER_CONTROLLER, DeviceType.CAMERA)]
    name = _WORD.get(g.get("w", ""))
    d = REGISTRY.get(name) if name else None
    period = _PERIOD.get(g.get("span", ""))
    if kind == "def":
        rows = [x for x in latest(db, now) if x["metric_name"] == name]
        if d["status"] == PLAN and not rows:
            return (f"{d['label']} is not measured yet: no sensor is installed. Planned sensor: {d['source']}, unit {d['unit']}."
                    + stamp)
        return (f"{d['label']}: sensor {d['source']}, unit {d['unit']}, accepted range {d['min']} to {d['max']}, about every "
                f"{d['interval_s']} s while reporting. Calibration: {d['calibration']}. No measured uncertainty is stored.") + stamp
    if kind in ("stat", "last"):
        rows = sorted((x for x in latest(db, now) if x["metric_name"] == name), key=lambda x: x["freshness"])
        if not rows:
            return (f"No {d['label'].lower()} reading is stored in the last 90 days"
                    + (": no sensor is installed." if d["status"] == PLAN else ".") + stamp)
        if kind == "last":
            return "\n".join(f"- {x['device_uid']}: last {d['label'].lower()} reading {x['timestamp'][:16].replace('T', ' ')} UTC "
                             f"({x['quality'].lower().replace('_', ' ')})" for x in rows[:6]) + stamp
        if d["kind"] == "state" and g["f"] not in ("data", "readings", "gaps"):
            return None                                           # an "average flame" is not a useful answer
        out = []
        for x in rows[:6]:
            h = history(db, x["device_id"], name, period, now)
            st = h["stats"]
            if g["f"] in ("data", "readings", "gaps"):
                out.append(f"- {x['device_uid']}: {st['n']} readings, {h['coverage_pct']} % of the time slots, {h['gap_count']} gap(s)")
            elif st["n"]:
                key = "avg" if g["f"] in ("average", "mean") else "max" if g["f"] in ("highest", "maximum") else "min"
                out.append(f"- {x['device_uid']}: {st[key]:.1f} {d['unit']} (from {st['n']} readings, {h['coverage_pct']} % coverage)")
            else:
                out.append(f"- {x['device_uid']}: no stored reading in this period")
        return f"{d['label']}, last {g['span']}:\n" + "\n".join(out) + stamp
    if kind in ("seen", "diag"):
        uid = (g.get("uid") or g.get("uid2")).upper()
        dev = next((x for x in db.query(Device).all() if x.device_uid.upper() == uid and not is_retired(x)), None)
        if dev is None:
            return None
        if kind == "seen":
            return (f"{dev.device_uid} was last heard {_utc(dev.last_seen_at).isoformat(timespec='seconds')}." if dev.last_seen_at
                    else f"{dev.device_uid} has never reported.") + stamp
        r = diagnose(db, dev, now)
        lines = [f"**{dev.device_uid}: {r['state']}.** {r['what_happened']}"]
        lines += [f"- Possible cause ({c['confidence']} confidence): {c['cause']}. Evidence: {'; '.join(c['evidence'])}" for c in r["causes"]]
        lines += [f"- Evidence: {e}" for e in r["evidence"]]
        lines += [f"- Check: {c}" for c in r["checks"]]
        if r["missing_evidence"]:
            lines.append("- Not recorded: " + "; ".join(r["missing_evidence"]))
        return "\n".join(lines) + f"\n\n{r['statement']}" + stamp
    if kind == "events":
        hours = _HOURS.get(period)
        if hours is None:
            return None
        want = {"alerts": "alert", "robot events": "robot", "maintenance reports": "maintenance", "door events": "door",
                "automation events": "automation"}
        kinds = {want[g["k"]]} if g.get("k") else set(_TIMELINE)
        counts = {}
        for k in kinds:                                           # counted in SQL: the list itself is capped
            counts[k] = db.execute(text(f"select count(*) from ({_TIMELINE[k]}) x where ts > :a and ts <= :b"),
                                   {"a": now - timedelta(hours=hours), "b": now}).scalar()
        return f"Recorded in the last {g['span']}: " + ", ".join(f"{n} {k} event(s)" for k, n in sorted(counts.items())) + "." + stamp
    if kind in ("gone", "have"):
        seen = {x["metric_name"] for x in latest(db, now)}
        l = [v["label"] for k, v in REGISTRY.items() if (v["status"] == PLAN and k not in seen) == (kind == "gone")]
        return ("Not measured yet: " if kind == "gone" else "Measurements the system stores (a device must be online for a "
                "current value): ") + ", ".join(l) + "." + stamp
    if kind == "silent":
        off = [d for d in nodes if is_fresh(d, now) is False]
        never = [d.device_uid for d in nodes if d.last_seen_at is None]
        tail = f"\nNever reported: {', '.join(never)}." if never else ""
        if not off:
            return ("Every node that has ever reported is reporting now." if len(nodes) > len(never)
                    else "No node has reported yet.") + tail + stamp
        return "Not reporting now:\n" + "\n".join(
            f"- {d.device_uid}: last heard {_utc(d.last_seen_at).isoformat(timespec='minutes')}" for d in off) + tail + stamp
    if kind == "wifi":
        rows = [x for x in latest(db, now) if x["metric_name"] == "wifi_rssi_dbm" and x["quality"] == "VALID"]
        if not rows:
            return "No current Wi-Fi signal readings are stored, so I cannot compare the nodes." + stamp
        w = min(rows, key=lambda x: x["value"])
        return f"{w['device_uid']} has the weakest current signal: {w['value']:.0f} dBm ({len(rows)} node(s) compared)." + stamp
    if kind == "drops":
        by = {d.id: d for d in nodes}
        r = [x for x in db.execute(text(
            "select device_id, sum(occurrences) as n from alerts where title ilike '%offline%' and device_id is not null "
            "and created_at > :a group by 1 order by 2 desc"), {"a": now - timedelta(days=30)}).all() if x.device_id in by]
        if not r:
            return "No offline alerts are recorded for the nodes in the last 30 days." + stamp
        return (f"{by[r[0].device_id].device_uid} has the most offline alerts in 30 days: {r[0].n}. "
                "Short reconnects that raised no alert are not counted.") + stamp
    if kind == "trend":
        x = next((x for x in latest(db, now) if x["metric_name"] == m.group(1) and x["quality"] == "VALID"), None)
        if x is None:
            return f"There is no current {m.group(1)} reading, so I cannot say how it is changing." + stamp
        c = history(db, x["device_id"], m.group(1), "24h", now)["change_per_hour"]
        if c is None:
            return f"Not enough recent {m.group(1)} readings to give a rate." + stamp
        return (f"{m.group(1).capitalize()} at {x['device_uid']} is {x['value']:.1f} {x['unit']} and changing by {c:+.1f} "
                f"{x['unit']} per hour (last two 15-minute averages). No unusual-rate limit has been validated.") + stamp
    if kind == "coverage":
        c = coverage(db, 7, now)
        if not c:
            return "No readings are stored for the last 7 days." + stamp
        return (f"Over 7 days: best {c[0]['device_uid']} {c[0]['coverage_pct']} %, lowest {c[-1]['device_uid']} "
                f"{c[-1]['coverage_pct']} % (only devices with any data).") + stamp
    if kind == "planned":
        # Once one of these sensors reports, "not installed" would be wrong: leave it to the normal assistant.
        if any(REGISTRY.get(x["metric_name"], {}).get("status") == PLAN and x["group"] != "node health" for x in latest(db, now)):
            return None
        return "The lab has no sensor installed for that yet, so there is no measurement to report." + stamp
    return "The portal holds no sensor calibration certificates. Registered calibration state:\n" + "\n".join(
        f"- {v['label']}: {v['calibration']}" for v in REGISTRY.values()
        if v["status"] == IMPL and v["calibration"] != "not applicable") + stamp
