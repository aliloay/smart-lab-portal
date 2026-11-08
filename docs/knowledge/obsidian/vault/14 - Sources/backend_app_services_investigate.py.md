---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/investigate.py"
source_hash: "6302e53d970e95f799b33769985d25ed7d73aed86fbc529fa4b2b8de6fa29995"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/investigate.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reliability.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_dependency_graph.py]] - imports
- [[backend_app_services_policy.py]] - imports
- [[backend_app_core_config.py]] - imports

```py
"""
Evidence-based incident investigation (2026-10-18).

For one incident: what the records show around it, which explanations fit and which do not, how sure
that is, and which safe checks would tell the explanations apart. Rules, not a language model - every
hypothesis lists the observations behind it and against it. Correlation is reported as correlation:
nothing here is a proven root cause, and nothing here acts on any device.

Inputs: the incident (alerts row), other incidents opened in the same window, the dependency graph
(current states, who needs whom), the backend's own start time (a portal restart makes every device
look silent at once) and the device's own reports.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Device
from app.services import dependency_graph as dg
from app.services import policy

STARTED_AT = time.time()            # this backend process (a restart = a gap in every heartbeat)
WINDOW = timedelta(minutes=10)


def _utc(d: Optional[datetime]) -> Optional[datetime]:
    return None if d is None else d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _deploys() -> list[dict]:
    import json
    import os
    from app.core.config import settings
    p = os.path.join(os.path.dirname(settings.BACKUP_STATUS_PATH or "/backups/x"), "deploy_history.jsonl")
    try:
        with open(p, encoding="utf-8") as f:
            return [json.loads(x) for x in f.read().splitlines()[-50:] if x.strip()]
    except (OSError, ValueError):
        return []


def _conf(support: int, against: int) -> str:
    score = support - 2 * against
    return "high" if score >= 3 else "medium" if score >= 2 else "low"


def investigate(db: Session, alert: Alert, services: list[dict], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    t0 = _utc(alert.created_at)
    graph = dg.build(services, now)
    by = {n["key"]: n for n in graph["nodes"]}
    dev = db.get(Device, alert.device_id) if alert.device_id else None
    node = next((n for n in graph["nodes"] if dev is not None and n.get("device_id") == dev.id), None)
    near = db.scalars(select(Alert).where(Alert.created_at >= t0 - WINDOW, Alert.created_at <= t0 + WINDOW,
                                          Alert.id != alert.id)).all()
    devices = {d.id: d for d in db.scalars(select(Device)).all()}
    title = (alert.title or "").lower()
    offline_like = "offline" in title or "not responding" in title or "no picture" in title
    hyps: list[dict] = []

    # ---- H1: a shared upstream failure (network / power / the portal host) -------------------------
    peers = [a for a in near if a.device_id and a.device_id != alert.device_id and "offline" in (a.title or "").lower()
             and abs((_utc(a.created_at) - t0).total_seconds()) <= 120]
    if offline_like:
        sup, con = [], []
        if peers:
            sup.append(f"{len(peers)} other device(s) went offline within 2 min of this one: "
                       + ", ".join(devices[a.device_id].device_uid for a in peers if a.device_id in devices))
        shared = None
        if node:
            mine = {x["node"] for x in node["needs"]}
            for a in peers:
                other = next((n for n in graph["nodes"] if n.get("device_id") == a.device_id), None)
                if other and mine & {x["node"] for x in other["needs"]}:
                    shared = sorted(mine & {x["node"] for x in other["needs"]})
                    break
        if shared:
            sup.append(f"they share {', '.join(by[k]['name'] for k in shared if k in by)}")
        if not peers:
            con.append("no other device went offline at the same time")
        hyps.append({"id": "shared_upstream", "title": "A shared supply, network or Wi-Fi outage stopped several devices",
                     "supporting": sup, "contradicting": con, "confidence": _conf(len(sup) + (1 if len(peers) >= 2 else 0), len(con)),
                     "checks": ["Is the shared 12 V supply / master switch on? (measure at the distribution)",
                                "Do the router and the other devices answer a ping from the laptop?",
                                "Serial monitor of one node: does it boot and join Wi-Fi?"]})

    # ---- H2: the portal itself was down (laptop off / Docker / backend restart) --------------------
    restart = datetime.fromtimestamp(STARTED_AT, timezone.utc)
    if offline_like:
        sup, con = [], []
        if abs((restart - t0).total_seconds()) <= 300:
            sup.append(f"the backend started at {restart.isoformat(timespec='seconds')}, within 5 min of the alert")
        if len(peers) >= 3 and all(abs((_utc(a.created_at) - t0).total_seconds()) <= 5 for a in peers):
            sup.append("several devices were marked offline in the same few seconds (typical after a portal gap)")
        if not sup:
            con.append("no backend restart near the alert time")
        hyps.append({"id": "portal_gap", "title": "The portal was not receiving (laptop asleep / Docker or backend restart)",
                     "supporting": sup, "contradicting": con, "confidence": _conf(len(sup), len(con)),
                     "checks": ["`docker compose ps` start times; Windows event log for sleep / restart around that time"]})

    # ---- H3: the device itself (power, crash, cable) ----------------------------------------------
    if dev is not None and offline_like:
        sup, con = [], []
        if not peers:
            sup.append("it is the only device that went offline then")
        if node and all(by.get(x["node"], {}).get("state") == "HEALTHY" for x in node["needs"]):
            sup.append("everything it depends on is healthy now")
        if peers:
            con.append("other devices failed at the same time - a shared cause is more likely")
        if node and node["state"] == "HEALTHY":
            con.append("it reports again now (the cause was temporary)")
        hyps.append({"id": "device_itself", "title": f"{dev.name} itself stopped (power, crash, cable, its process)",
                     "supporting": sup, "contradicting": con, "confidence": _conf(len(sup), len(con)),
                     "checks": [f"Look at {dev.name}: power LED, cable; its process / serial output"]})

    # ---- H4: an unstable condition (flapping) -------------------------------------------------------
    if (alert.reopened_count or 0) >= 2 or (alert.occurrences or 1) >= 10:
        hyps.append({"id": "unstable", "title": "An unstable connection or sensor (the condition keeps coming back)",
                     "supporting": [f"{alert.occurrences or 1} occurrences, reopened {alert.reopened_count or 0} times"],
                     "contradicting": [], "confidence": "medium",
                     "checks": ["Wi-Fi signal (RSSI) at the node, loose connectors, supply sag under load",
                                "For a sensor: compare with a second instrument before trusting either"]})

    # ---- H4b: a deployment shortly before (deploy history written by tools/deploy/deploy.py) ----------
    for dep in _deploys():
        try:
            at = datetime.strptime(dep["started"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if timedelta(0) <= t0 - at <= timedelta(hours=2):
            hyps.append({"id": "deployment", "title": f"A portal deployment {int((t0 - at).total_seconds() // 60)} min before",
                         "supporting": [f"deploy {dep.get('version')} at {dep['started']}: {dep.get('outcome')}"],
                         "contradicting": [] if not dev else ["a device outage is rarely caused by a portal deploy"],
                         "confidence": "low" if dev else "medium",
                         "checks": ["Compare the behaviour before / after; the deploy's smoke tests in backups/deploy_history.jsonl"]})
            break

    # ---- H5: camera-specific -------------------------------------------------------------------------
    if "camera-wide" in title or ("moved" in title and "boxes" in (alert.detail or "").lower()):
        hyps.append({"id": "camera_view", "title": "The camera view changed (lighting, camera bumped) - not the equipment",
                     "supporting": ["several boxes of one camera changed at the same moment"], "contradicting": [],
                     "confidence": "medium", "checks": ["Open the snapshot; compare the view with the boxes"]})

    order = {"high": 0, "medium": 1, "low": 2}
    hyps.sort(key=lambda h: (order[h["confidence"]], -len(h["supporting"])))
    earliest = min([t0, *(_utc(a.created_at) for a in peers)]) if peers else t0
    affected = dg.impact(graph, node["key"]) if node else []
    suggestions = [{"action": "health.recheck", "text": "Re-run the health checks now (read-only)"},
                   {"action": "incident.note", "text": "Record what was checked on the incident"}]
    if dev is not None and offline_like:
        suggestions.append({"action": "device.physical_check", "text": f"Check {dev.name} on site (power, cable, Wi-Fi)"})
    for s in suggestions:
        s["policy"] = policy.evaluate(s["action"], {"automatic": False})
    return {
        "incident": alert.id, "generated_at": now.isoformat(),
        "statement": "Ranked explanations from the records - correlation, not proof. Confirm with the checks.",
        "hypotheses": hyps,
        "earliest_warning": earliest.isoformat(),
        "affected_components": [{"node": k, "name": by[k]["name"], "state": by[k]["state"]} for k in affected],
        "related_incidents": [{"id": a.id, "title": a.title, "at": _utc(a.created_at).isoformat()} for a in near[:15]],
        "unknowns": ["what happened physically at the device (no camera / sensor watches the power supply)",
                     "router-side logs (not available to the portal)"],
        "suggestions": suggestions,
    }

```
