"""
Backup + isolated restore drill - never touches the production database except to READ it.

    py -I tools/evidence/restore_drill.py [--migrate-test]

1. pg_dump of production (custom format) -> backups/smartlab_drill_source_<stamp>.dump
2. integrity: pg_restore --list must succeed (entry count recorded)
3. restore into a NEW database smartlab_drill_<stamp> (never an existing one; smartlab_restore_drill and
   every other database are left alone), timed = the recovery time for this data size
4. compare every table's row count with production at dump time (tables written in between may differ:
   reported, not hidden)
5. --migrate-test: run `alembic upgrade head` on the restored copy, then downgrade one step and upgrade
   again (the migration must be reversible), with timings
Writes docs/reports/restore_drill_<stamp>.json. Database passwords never appear in the output.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STAMP = time.strftime("%Y%m%d_%H%M%S")
DRILL_DB = f"smartlab_drill_{STAMP}"


def dc(*args, input_=None, timeout=900):
    t = time.perf_counter()
    r = subprocess.run(["docker", "compose", *args], cwd=REPO, capture_output=True, timeout=timeout, input=input_)
    return r, round(time.perf_counter() - t, 2)


def psql(db, sql):
    r, _ = dc("exec", "-T", "db", "psql", "-U", "smartlab", "-d", db, "-tAc", sql)
    return r.stdout.decode().strip()


def counts(db):
    tables = psql(db, "select tablename from pg_tables where schemaname='public' order by 1").splitlines()
    out = {}
    for t in tables:
        out[t] = int(psql(db, f'select count(*) from "{t}"') or 0)
    return out


def main():
    res = {"stamp": STAMP, "kind": "LIVE_SYSTEM (isolated copy)", "drill_db": DRILL_DB}
    existing = psql("smartlab", "select datname from pg_database").splitlines()
    assert DRILL_DB not in existing, "drill database name already exists - refusing"
    # 1-2. dump + integrity
    dump_in = f"/tmp/{DRILL_DB}.dump"
    r, s = dc("exec", "-T", "db", "pg_dump", "-U", "smartlab", "-Fc", "-f", dump_in, "smartlab")
    res["dump_s"] = s
    res["dump_ok"] = r.returncode == 0
    prod = counts("smartlab")
    r, _ = dc("exec", "-T", "db", "pg_restore", "--list", dump_in)
    res["integrity_ok"] = r.returncode == 0
    res["toc_entries"] = len([x for x in r.stdout.decode().splitlines() if x and not x.startswith(";")])
    host_copy = os.path.join(REPO, "backups", f"smartlab_drill_source_{STAMP}.dump")
    cid = subprocess.run(["docker", "compose", "ps", "-q", "db"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    subprocess.run(["docker", "cp", f"{cid}:{dump_in}", host_copy], cwd=REPO, capture_output=True)
    res["dump_file"] = os.path.relpath(host_copy, REPO)
    res["dump_kb"] = round(os.path.getsize(host_copy) / 1024) if os.path.isfile(host_copy) else None
    # 3. restore into a new database
    psql("smartlab", f'create database "{DRILL_DB}"')
    r, s = dc("exec", "-T", "db", "pg_restore", "-U", "smartlab", "-d", DRILL_DB, "--no-owner", dump_in)
    res["restore_s"] = s
    res["restore_exit"] = r.returncode
    res["restore_errors"] = [x for x in r.stderr.decode().splitlines() if "error" in x.lower()][:5]
    # 4. compare
    drill = counts(DRILL_DB)
    diff = {t: {"production_now": prod.get(t), "restored": drill.get(t)}
            for t in sorted(set(prod) | set(drill)) if prod.get(t) != drill.get(t)}
    res["tables"] = len(drill)
    res["rows_restored"] = sum(drill.values())
    res["count_mismatches"] = diff
    res["alembic_version_restored"] = psql(DRILL_DB, "select version_num from alembic_version")
    # 5. migration test on the copy
    if "--migrate-test" in sys.argv:
        mig = {}
        url = f'DATABASE_URL="${{DATABASE_URL%/*}}/{DRILL_DB}"'
        backend = ["run", "--rm", "--no-deps", "-T", "-v", f"{REPO}\\backend:/app", "backend", "sh", "-c"]
        for step, cmd in (("upgrade", "alembic upgrade head"), ("downgrade", "alembic downgrade -1"),
                          ("upgrade_again", "alembic upgrade head")):
            r, s = dc(*backend, f"{url} {cmd}", timeout=600)
            mig[step] = {"exit": r.returncode, "s": s, "version": psql(DRILL_DB, "select version_num from alembic_version")}
        mig["alerts"] = int(psql(DRILL_DB, "select count(*) from alerts") or 0)
        mig["alerts_with_fingerprint"] = int(psql(DRILL_DB, "select count(*) from alerts where fingerprint is not null") or 0)
        mig["alerts_occurrences_1"] = int(psql(DRILL_DB, "select count(*) from alerts where occurrences = 1") or 0)
        res["migration_test"] = mig
    # the portal reads this (./backups is mounted read-only into the backend): last verified restore
    ok = bool(res["dump_ok"] and res["integrity_ok"] and res["restore_exit"] == 0 and res["tables"] > 0)
    if "migration_test" in res:
        ok = ok and all(v.get("exit") == 0 for k, v in res["migration_test"].items() if isinstance(v, dict))
    status_doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z") or None, "stamp": STAMP, "ok": ok,
                  "dump_s": res["dump_s"], "restore_s": res["restore_s"], "tables": res["tables"],
                  "rows": res["rows_restored"], "count_mismatches": len(res["count_mismatches"]),
                  "drill_db": DRILL_DB, "report": f"docs/reports/restore_drill_{STAMP}.json"}
    from datetime import datetime as _dt, timezone as _tz
    status_doc["at"] = _dt.now(_tz.utc).isoformat()
    with open(os.path.join(REPO, "backups", "restore_drill_status.json"), "w", encoding="utf-8") as f:
        json.dump(status_doc, f, indent=1)
    out = os.path.join(REPO, "docs", "reports", f"restore_drill_{STAMP}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))
    print("written", os.path.relpath(out, REPO))


if __name__ == "__main__":
    main()
