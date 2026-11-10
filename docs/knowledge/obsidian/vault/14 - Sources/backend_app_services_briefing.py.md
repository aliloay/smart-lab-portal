---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/briefing.py"
source_hash: "b0d2651dad19d00981aa8f99fca06869d736d7d4aaa3c9e9cba4e6b686b9112a"
generated: true
updated: "2026-11-04T00:02:39+02:00"
redactions: ["configured-literal"]
---
> Read-only mirror of `backend/app/services/briefing.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reliability.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[docs_FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md]] - mentioned by docs

```py
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


# The sign-in table in the public README (2026-10-26 audit: on the live portal the admin and staff accounts still
# accepted these). Checked against each account's CURRENT hash; the answer is cached per hash, so the ~100 ms Argon2
# check runs once per password change, not on every briefing. Nothing is changed - the owner changes the passwords.
PUBLISHED_DEFAULTS = {"admin@giu-uni.de": "[REDACTED:configured-literal]", "ramy@giu-uni.de": "Staff#2026", "ali@giu-uni.de": "Student#2026"}
_default_cache: dict[tuple[str, str], bool] = {}


def default_passwords_in_use(db: Session) -> list[str]:
    from app.core.security import verify_password
    from app.models import User
    out = []
    for u in db.scalars(select(User).where(User.email.in_(list(PUBLISHED_DEFAULTS)), User.is_active.is_(True))).all():
        k = (u.email, u.hashed_password or "")
        if k not in _default_cache:
            _default_cache[k] = bool(u.hashed_password) and verify_password(PUBLISHED_DEFAULTS[u.email], u.hashed_password)
        if _default_cache[k]:
            out.append(f"{u.email} ({getattr(u.role, 'value', u.role)})")
    return out


def build(db: Session, services: list[dict], drift: Optional[dict], regressions: list[dict],
          backup: dict, restore: Optional[dict], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    items: list[dict] = []

    def add(priority, kind, title, evidence, link, uncertainty=None):
        items.append({"priority": priority, "kind": kind, "title": title, "evidence": evidence, "link": link,
                      "uncertainty": uncertainty})

    weak = default_passwords_in_use(db)
    if weak:
        add(1, "security", f"{len(weak)} account(s) still use the password printed in the public README",
            weak + ["Change them on Users & roles (or Profile) - anyone who read the repository can sign in."],
            "/admin/users")
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

```
