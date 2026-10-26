"""
Configuration drift detection (2026-10-18).

Compares what the system runs with against the approved, versioned baseline
(app/config_baseline.json) - settings, secret presence (never values: a secret is only checked for
being SET and not equal to a known default), database migration head, firmware / agent versions the
devices report, camera service ports, backup schedule and freshness.

Each finding: component, expected, actual, severity, operational impact, class
(SAFE AUTOMATIC CORRECTION / APPROVAL REQUIRED / INFORMATIONAL / UNKNOWN), remediation, approval.
No setting is on the automatic-correction whitelist today (configuration lives in .env and needs a
container restart), so nothing is ever changed automatically - the remediation is a preview.

Accepted deviations (owner, reason, optional expiry) are stored in system_settings["drift.accepted"]
and stay VISIBLE (marked accepted); they never become the baseline. A short change history is kept in
system_settings["drift.history"] (only when the set of findings changes).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Device, SystemSetting

BASELINE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config_baseline.json")
AUTO_CORRECT_WHITELIST: set[str] = set()          # deliberately empty (see module doc)
APPROVAL, INFO, AUTO, UNKNOWN = "APPROVAL REQUIRED", "INFORMATIONAL", "SAFE AUTOMATIC CORRECTION", "UNKNOWN"


def baseline() -> dict:
    with open(os.path.abspath(BASELINE_PATH), encoding="utf-8") as f:
        return json.load(f)


_HEAD: list = []


def migration_head() -> str:
    """The code's alembic head. Read once per process: finding it imports every migration file (~370 ms,
    measured 2026-10-25 - most of the 433 ms /reliability/briefing), and the files cannot change under a
    running backend. The DATABASE's version is still read on every check."""
    if not _HEAD:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))
        _HEAD.append(ScriptDirectory.from_config(cfg).get_current_head())
    return _HEAD[0]


def _actual_setting(name: str):
    if name in ("ROBOT_CONTROL", "UR5E_HOME_METHOD", "UR5E_HOME_PROGRAM"):
        from app.services import robot_control as rc
        return {"ROBOT_CONTROL": rc.MODE, "UR5E_HOME_METHOD": rc.UR_HOME_METHOD, "UR5E_HOME_PROGRAM": rc.UR_HOME_PROGRAM}[name]
    if name == "DEVICE_PROBES":
        return os.environ.get("DEVICE_PROBES", "1")
    return getattr(settings, name, None)


def _accepted(db: Session) -> dict:
    row = db.get(SystemSetting, "drift.accepted")
    try:
        items = json.loads(row.value) if row and row.value else []
    except ValueError:
        items = []
    now = datetime.now(timezone.utc)
    return {i["id"]: i for i in items
            if not i.get("expires_at") or datetime.fromisoformat(i["expires_at"]) > now}


def check(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    b = baseline()
    out: list[dict] = []

    def add(fid, component, expected, actual, severity, impact, klass, remediation, approval=True):
        out.append({"id": fid, "component": component, "expected": expected, "actual": actual,
                    "severity": severity, "impact": impact, "class": klass, "remediation": remediation,
                    "approval_required": approval, "detected_at": now.isoformat(),
                    "auto_correctable": fid in AUTO_CORRECT_WHITELIST})

    # settings
    for name, spec in b["settings"].items():
        act = _actual_setting(name)
        exp = spec["expected"]
        same = (str(act).lower() == str(exp).lower()) if not isinstance(exp, bool) else (bool(act) == exp)
        if not same:
            add(f"setting:{name}", f"setting {name}", exp, act, spec["severity"], spec["why"], APPROVAL,
                f"set {name}={exp} in .env and redeploy the backend - or record the approved new value in the baseline")
    # secrets: presence / not a known default - never the value
    for name in b["secrets_present"]:
        if not getattr(settings, name, ""):
            add(f"secret:{name}", f"secret {name}", "set", "missing", "high", "feature or security depends on it", APPROVAL,
                f"set {name} in .env (never in the repository)")
    for name, default in b["secrets_not_default"].items():
        if name == "DATABASE_PASSWORD":
            is_default = f":{default}@" in settings.DATABASE_URL
        else:
            is_default = getattr(settings, name, None) == default
        if is_default:
            add(f"secret_default:{name}", f"secret {name}", "not the published default", "published default",
                "high", "anyone who reads the repository knows it", APPROVAL, f"rotate {name} (credentials change needs the owner)")
    # migration head
    try:
        head = migration_head()
        # never send a failing statement: it would abort the caller's transaction
        managed = db.execute(text("select to_regclass('public.alembic_version')")).scalar() is not None
        dbv = db.execute(text("select version_num from alembic_version")).scalar() if managed else None
        if not managed:
            add("migration:head", "database schema", head, "not managed by alembic (test / quick-start database)",
                "low", "none for a throwaway database", INFO, "production must be alembic-managed", approval=False)
        elif head != dbv:
            add("migration:head", "database schema", head, dbv, "high", "the API refuses to start behind head",
                APPROVAL, "dump the database, test the migration on a restored copy, then `alembic upgrade head`")
    except Exception as e:
        add("migration:head", "database schema", "head", f"could not compare ({e.__class__.__name__})", "low",
            "unknown", UNKNOWN, "check alembic manually", approval=False)
    # firmware / agent versions the devices report
    for d in db.scalars(select(Device)).all():
        exp = next((v for pat, v in b["firmware"].items() if fnmatch(d.device_uid, pat)), None)
        if exp is None or not d.firmware_version:
            continue
        if d.firmware_version != exp:
            add(f"firmware:{d.device_uid}", f"{d.device_uid} firmware/agent", exp, d.firmware_version, "medium",
                "behaviour may differ from the tested source", APPROVAL,
                "update through the authorised bench procedure (no automatic flashing) or record the version as approved")
    # camera service ports
    for uid, port in b["camera_ports"].items():
        d = db.scalar(select(Device).where(Device.device_uid == uid))
        if d is None:
            add(f"camera:{uid}", f"camera service {uid}", f"port {port}", "not registered", "medium",
                "the portal cannot reach its picture", INFO, "start its service once (it registers itself)", approval=False)
        elif (d.component_state or {}).get("port") not in (port, None):
            add(f"camera:{uid}", f"camera service {uid}", f"port {port}", f"port {(d.component_state or {}).get('port')}",
                "medium", "two camera services could collide", APPROVAL, "fix PORT in its camera*.env")
    # backups
    try:
        from app.services.backups import read_status
        st = read_status() or {}
        if st.get("every_hours") not in (None, b["backups"]["every_hours"]):
            add("backup:interval", "database backups", f"every {b['backups']['every_hours']} h",
                f"every {st.get('every_hours')} h", "medium", "longer gap between restore points", APPROVAL, "BACKUP_EVERY_HOURS in .env")
        last = st.get("last_success")
        if last:
            age_h = (now - datetime.fromisoformat(str(last))).total_seconds() / 3600
            if age_h > b["backups"]["max_age_hours"]:
                add("backup:age", "database backups", f"< {b['backups']['max_age_hours']} h old", f"{age_h:.1f} h old",
                    "high", "the newest restore point is old", INFO, "check the backup container (`docker compose logs backup`)",
                    approval=False)
    except Exception:
        pass
    acc = _accepted(db)
    for f in out:
        if f["id"] in acc:
            f["accepted"] = {k: acc[f["id"]].get(k) for k in ("reason", "owner", "expires_at", "accepted_at")}
    _remember(db, out, now)
    return {"baseline_version": b["version"], "checked_at": now.isoformat(), "findings": out,
            "compliant": not [f for f in out if not f.get("accepted")],
            "summary": {k: sum(1 for f in out if f["class"] == k) for k in (APPROVAL, INFO, AUTO, UNKNOWN)},
            "auto_correct_whitelist": sorted(AUTO_CORRECT_WHITELIST)}


def _remember(db: Session, findings: list[dict], now: datetime) -> None:
    ids = sorted(f["id"] for f in findings)
    row = db.get(SystemSetting, "drift.history")
    hist = json.loads(row.value) if row and row.value else []
    if hist and hist[-1]["ids"] == ids:
        return
    hist = (hist + [{"at": now.isoformat(), "ids": ids}])[-50:]
    if row is None:
        db.add(SystemSetting(key="drift.history", value=json.dumps(hist), updated_at=now))
    else:
        row.value, row.updated_at = json.dumps(hist), now
    db.commit()


def history(db: Session) -> list[dict]:
    row = db.get(SystemSetting, "drift.history")
    return json.loads(row.value) if row and row.value else []


def accept(db: Session, fid: str, reason: str, owner: str, days: Optional[int]) -> dict:
    row = db.get(SystemSetting, "drift.accepted")
    items = json.loads(row.value) if row and row.value else []
    items = [i for i in items if i["id"] != fid]
    now = datetime.now(timezone.utc)
    rec = {"id": fid, "reason": reason, "owner": owner, "accepted_at": now.isoformat(),
           "expires_at": (now + timedelta(days=days)).isoformat() if days else None}
    items.append(rec)
    if row is None:
        db.add(SystemSetting(key="drift.accepted", value=json.dumps(items), updated_at=now))
    else:
        row.value, row.updated_at = json.dumps(items), now
    return rec
