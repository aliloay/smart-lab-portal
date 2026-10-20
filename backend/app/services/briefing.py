"""
Operator briefing (2026-10-18): what needs attention now, most urgent first, each item linked to its
evidence. Deterministic (no language model): the same records always give the same briefing. Items
already shown in the previous briefing with no change are marked repeated=True, not hidden.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, SystemSetting


def _utc(d):
    return None if d is None else d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def build(db: Session, services: list[dict], drift: Optional[dict], regressions: list[dict],
          backup: dict, restore: Optional[dict], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    items: list[dict] = []

    def add(priority, kind, title, evidence, link, uncertainty=None):
        items.append({"priority": priority, "kind": kind, "title": title, "evidence": evidence, "link": link,
                      "uncertainty": uncertainty})

    open_ = db.scalars(select(Alert).where(Alert.is_resolved.is_(False))).all()
    crit = [a for a in open_ if getattr(a.severity, "value", a.severity) == "CRITICAL"]
    if crit:
        add(1, "incident", f"{len(crit)} critical incident(s) unresolved",
            [f"INC-{a.id:06d} {a.title} (x{a.occurrences or 1})" for a in crit[:5]], "/admin/incidents?state=ACTIVE")
    recurring = [a for a in open_ if (a.reopened_count or 0) > 0]
    if recurring:
        add(2, "recurring", f"{len(recurring)} incident(s) came back after being resolved",
            [f"INC-{a.id:06d} {a.title}: reopened {a.reopened_count}x" for a in recurring[:5]], "/admin/incidents")
    new24 = [a for a in open_ if _utc(a.created_at) >= now - timedelta(hours=24)]
    if new24:
        add(3, "incident", f"{len(new24)} new incident(s) in the last 24 h",
            [f"INC-{a.id:06d} {a.title}" for a in new24[:5]], "/admin/incidents")
    down = [s for s in services if not s.get("group") and s["state"] in ("OFFLINE", "DEGRADED")]
    if down:
        add(1, "service", f"{len(down)} portal service(s) down or degraded",
            [f"{s['name']}: {s['state']} - {s.get('detail', '')}" for s in down], "/admin/system")
    devs = [s for s in services if s.get("group") and s["state"] in ("OFFLINE", "STALE", "DEGRADED")]
    if devs:
        add(2, "device", f"{len(devs)} device(s) not reporting normally",
            [f"{s['name']} ({s.get('device_uid')}): {s['state']}, last report {s.get('last_seen') or 'never'}" for s in devs[:8]],
            "/admin/system", "a silent device can be switched off on purpose - check on site")
    if drift:
        live = [f for f in drift["findings"] if not f.get("accepted")]
        if live:
            add(2, "drift", f"{len(live)} configuration difference(s) from the approved baseline",
                [f"{f['component']}: expected {f['expected']}, actual {f['actual']} ({f['class']})" for f in live[:6]],
                "/admin/reliability?tab=drift")
    for r in regressions:
        add(2, "performance", f"Slower: {r['route']}",
            [f"p95 {r['baseline_p95']} -> {r['current_p95']} ms ({r['change_pct']:+d} %), samples "
             f"{r['samples']['baseline']}/{r['samples']['current']}"], "/admin/reliability?tab=performance",
            r.get("note"))
    if backup.get("state") not in ("OK", None):
        add(1, "backup", f"Backups: {backup.get('state')}", [backup.get("detail") or ""], "/admin/system")
    if restore:
        age = (now - datetime.fromisoformat(restore["at"])).days if restore.get("at") else None
        if not restore.get("ok"):
            add(1, "backup", "The last restore drill failed", [json.dumps(restore)[:300]], "/admin/reliability?tab=backups")
        elif age is not None and age > 30:
            add(3, "backup", f"Restore last verified {age} days ago", ["run tools/evidence/restore_drill.py"],
                "/admin/reliability?tab=backups")
    add(3, "physical", "Physical validation still required",
        ["UR5e / FANUC: commissioning with the qualified operator (motion DRY RUN until sign-off)",
         "Cameras: mounting, floor calibration, identity scenarios with people",
         "ESP32 nodes: power / bench checks (offline since 11-13 Oct)",
         "Lab PCs: agent pilot needs university IT approval"], "/admin/reliability?tab=graph")
    for i in items:
        i["id"] = hashlib.sha1((i["kind"] + i["title"] + "|".join(i["evidence"])).encode()).hexdigest()[:12]
    row = db.get(SystemSetting, "briefing.last")
    prev = set(json.loads(row.value)) if row and row.value else set()
    for i in items:
        i["repeated"] = i["id"] in prev
    ids = json.dumps([i["id"] for i in items])
    if row is None:
        db.add(SystemSetting(key="briefing.last", value=ids, updated_at=now))
    else:
        row.value, row.updated_at = ids, now
    db.commit()
    items.sort(key=lambda i: (i["priority"], i["repeated"]))
    return {"generated_at": now.isoformat(), "items": items,
            "note": "From the portal's own records and checks; physical states need a person on site."}
