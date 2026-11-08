"""
Anomaly detection for the measurements the lab really has (2026-10-17).

Three layers, in order of trust:
  1. RULES      - fixed thresholds (comfort / equipment limits) per metric.
  2. SENSOR     - sensor-fault checks: physically impossible values, a flat line, no data (stale).
  3. BASELINE   - statistics: the last hour against the node's own previous 7 days (robust z from
                  median / MAD), and how often a binary detector fired in 24 h against its baseline rate.
Machine-learning detection is NOT used: one environment node with ~6 days of history is not enough to
train or validate a model (said explicitly in the response, `ml_status`).

Every finding names the signal, expected range or baseline, observed value, window, confidence and the
source table. Missing data is reported as missing - never as zero.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

CONTINUOUS = {   # metric: (rule low, rule high, physical low, physical high, unit)
    "temperature": (15.0, 32.0, -20.0, 70.0, "°C"),
    "humidity": (20.0, 75.0, 0.0, 100.0, "%"),
}
BINARY = ("smoke", "flame", "gas", "motion")
CADENCE_S = 60
MIN_BASELINE = 200
Z_LIMIT = 3.5


def _series(db: Session, device_id: int, metric: str, start: datetime, end: datetime) -> list[tuple[datetime, float]]:
    return [(r.ts, r.v) for r in db.execute(text(
        "select recorded_at as ts, value as v from sensor_readings where device_id = :d and metric = :m "
        "and recorded_at >= :s and recorded_at <= :e order by recorded_at"), {"d": device_id, "m": metric, "s": start, "e": end})]


def _robust(values: list[float]) -> tuple[float, float]:
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values]) or 1e-9
    return med, 1.4826 * mad


def scan(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    streams = db.execute(text("""
        select s.device_id, d.device_uid, l.code as lab, s.metric, max(s.recorded_at) as last, count(*) as n
        from sensor_readings s join devices d on d.id = s.device_id left join labs l on l.id = s.lab_id
        group by 1, 2, 3, 4 having count(*) >= 10 order by 2, 4""")).all()
    findings, evaluated = [], []
    for st in streams:
        end = st.last
        age = (now - end).total_seconds()
        stale = age > CADENCE_S * 3
        base = {"device": st.device_uid, "lab": st.lab, "metric": st.metric, "source": "sensor_readings",
                "evaluated_at": end.isoformat(), "data_age_s": round(age), "stale": stale}
        evaluated.append({**base, "readings": st.n})
        if stale:
            findings.append({**base, "layer": "SENSOR", "kind": "NO_CURRENT_DATA", "severity": "WARNING",
                             "signal": f"{st.metric} from {st.device_uid}", "observed": f"last reading {end.isoformat()}",
                             "expected": f"a reading about every {CADENCE_S} s", "window": "-",
                             "confidence": "certain (no rows)", "explanation":
                             "The node stopped reporting. The analysis below uses its last day of data, not the present."})
        last_hour = _series(db, st.device_id, st.metric, end - timedelta(hours=1), end)
        baseline = _series(db, st.device_id, st.metric, end - timedelta(days=7), end - timedelta(hours=1))
        vals = [v for _, v in last_hour]
        if not vals:
            continue
        if st.metric in CONTINUOUS:
            lo, hi, plo, phi, unit = CONTINUOUS[st.metric]
            cur = statistics.fmean(vals)
            bad = [v for v in vals if v < plo or v > phi]
            if bad:
                findings.append({**base, "layer": "SENSOR", "kind": "IMPOSSIBLE_VALUE", "severity": "WARNING",
                                 "signal": st.metric, "observed": f"{len(bad)} reading(s) like {bad[0]} {unit}",
                                 "expected": f"{plo} to {phi} {unit} (physically possible)", "window": "last hour of data",
                                 "confidence": "high", "explanation": "Values outside what the sensor can measure: a wiring or sensor fault."})
            if len(vals) >= 30 and max(vals[-30:]) == min(vals[-30:]):
                findings.append({**base, "layer": "SENSOR", "kind": "FLAT_LINE", "severity": "INFO", "signal": st.metric,
                                 "observed": f"30 identical readings ({vals[-1]} {unit})", "expected": "small natural variation",
                                 "window": "last 30 readings", "confidence": "medium",
                                 "explanation": "A frozen value can mean a stuck sensor; a very stable room can also do this."})
            if cur > hi or cur < lo:
                findings.append({**base, "layer": "RULE", "kind": "OUT_OF_RANGE", "severity": "WARNING", "signal": st.metric,
                                 "observed": f"{cur:.1f} {unit} (1 h mean)", "expected": f"{lo} to {hi} {unit}",
                                 "window": "last hour of data", "confidence": "high (measured)",
                                 "explanation": "Outside the lab's comfort / equipment range."})
            bvals = [v for _, v in baseline if plo <= v <= phi]
            if len(bvals) < MIN_BASELINE:
                evaluated[-1]["baseline"] = f"insufficient ({len(bvals)} < {MIN_BASELINE} readings)"
                continue
            med, sig = _robust(bvals)
            z = (cur - med) / sig if sig > 1e-6 else 0.0
            evaluated[-1]["baseline"] = {"median": round(med, 2), "robust_sigma": round(sig, 2), "n": len(bvals),
                                         "current": round(cur, 2), "z": round(z, 2)}
            if abs(z) >= Z_LIMIT:
                findings.append({**base, "layer": "BASELINE", "kind": "DEVIATION", "severity": "INFO" if abs(z) < 6 else "WARNING",
                                 "signal": st.metric, "observed": f"{cur:.1f} {unit} (1 h mean)",
                                 "expected": f"{med:.1f} ± {Z_LIMIT * sig:.1f} {unit} (7-day median ± {Z_LIMIT} robust σ)",
                                 "window": "last hour vs previous 7 days", "confidence": f"z = {z:.1f}; {len(bvals)} baseline readings, one node",
                                 "explanation": "Unusual for this node compared with its own history - not necessarily a fault."})
        elif st.metric in BINARY:
            day = _series(db, st.device_id, st.metric, end - timedelta(hours=24), end)
            rate = sum(1 for _, v in day if v > 0) / len(day) if day else 0.0
            brate = (sum(1 for _, v in baseline if v > 0) / len(baseline)) if baseline else None
            evaluated[-1]["baseline"] = {"rate_24h": round(rate, 3), "baseline_rate": None if brate is None else round(brate, 3),
                                         "n": len(baseline)}
            if st.metric in ("flame", "smoke", "gas") and rate <= 0.05 and brate is not None and brate > 0.05:
                # How concentrated: the longest continuous active run and how many separate activations.
                longest, run_start, starts, prev = timedelta(0), None, 0, 0.0
                for t, v in baseline:
                    if v > 0 and prev <= 0:
                        run_start, starts = t, starts + 1
                    if v > 0 and run_start is not None:
                        longest = max(longest, t - run_start)
                    prev = v
                findings.append({**base, "layer": "SENSOR", "kind": "HISTORICALLY_FREQUENT", "severity": "INFO",
                                 "signal": f"{st.metric} detector",
                                 "observed": f"active in {brate:.0%} of {len(baseline)} readings over the previous 7 days; "
                                             f"{starts} separate activation(s), the longest continuous for "
                                             f"{longest.total_seconds() / 60:.0f} min",
                                 "expected": "almost never active without a real fire / smoke",
                                 "window": "previous 7 days of data", "confidence": "medium",
                                 "explanation": "The detector fired often in the past (quiet in the last 24 h of data). Check its sensitivity "
                                                "and placement before relying on it."})
            if st.metric in ("flame", "smoke", "gas") and rate > 0.05:
                findings.append({**base, "layer": "SENSOR", "kind": "FREQUENT_DETECTIONS", "severity": "WARNING",
                                 "signal": f"{st.metric} detector", "observed": f"active in {rate:.0%} of readings (24 h)",
                                 "expected": "almost never active without a real fire / smoke",
                                 "window": "last 24 h of data", "confidence": "medium",
                                 "explanation": "A detector that fires this often is more likely mis-adjusted or seeing ambient light / dust "
                                                "than a fire - check its sensitivity before trusting its alarms. Real alarms still go through "
                                                "the normal hazard path."})
    return {"generated_at": now.isoformat(), "findings": findings, "evaluated": evaluated,
            "ml_status": "Not used: one environment node with about 6 days of history is not enough data to train or validate "
                         "a machine-learning detector. Rules, sensor-fault checks and robust statistical baselines are used instead.",
            "not_covered": "Vibration, motor current and energy are not measured by any integrated sensor yet; robots and PCs "
                           "report state only. These are not analysed (no data), not assumed normal."}


def raise_alert(db: Session, f: dict) -> tuple[bool, int]:
    """Turn a finding into an incident once per day per (device, metric, kind): the dedupe key stops repeats."""
    from app.models import Alert, AlertSeverity, Device
    key = f"anomaly:{f['device']}:{f['metric']}:{f['kind']}:{f['evaluated_at'][:10]}"
    existing = db.execute(text("select id from alerts where dedupe_key = :k"), {"k": key}).scalar()
    if existing:
        return False, existing
    d = db.execute(text("select id, lab_id from devices where device_uid = :u"), {"u": f["device"]}).first()
    from app.services.alert_grouping import raise_or_group
    # Same anomaly on another day while the incident is still open: counted on it, not a new row.
    a, outcome = raise_or_group(
        db, lab_id=d.lab_id if d else None, device_id=d.id if d else None,
        severity=AlertSeverity.WARNING if f["severity"] == "WARNING" else AlertSeverity.INFO,
        title=f"Anomaly: {f['signal']} - {f['kind'].replace('_', ' ').lower()}"[:128],
        detail=(f"Observed {f['observed']}; expected {f['expected']}; window {f['window']}; confidence {f['confidence']}. "
                f"{f['explanation']} Source: {f['source']}."),
        fp=f"anomaly:{f['device']}:{f['metric']}:{f['kind']}", fields={"dedupe_key": key})
    db.commit()
    return outcome != "grouped", a.id
