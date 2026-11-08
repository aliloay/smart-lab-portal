"""
Merge a backup INTO a database - insert only: nothing is deleted or overwritten.

Brings back what the backup has and the target does not (users, bookings, door
events, sessions, alerts, notifications, audit log, issues ...) and keeps
everything the target recorded since. Rows are matched on their natural key
(users by e-mail, labs by code, devices by device id, cards by UID ...);
history rows are added with their id kept where it is free in the target, else
a new one, and every foreign key - plus the audit log's text ids - is remapped.

Steps (inside the backend container, which has the login in DATABASE_URL):

  1. load the backup into a staging database and `alembic upgrade head` it
  2. python merge_backup.py --source smartlab_restore --target smartlab_rehearsal          # dry run
  3. python merge_backup.py --source smartlab_restore --target smartlab_rehearsal --apply  # rehearsal
  4. the same against the live database with --apply, with the backend stopped

Written after the 2026-10-05 test-run wipe (docs/BRINGUP_LOG.md).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict

from sqlalchemy import MetaData, and_, create_engine, func, select, text

# Rows that are "the same thing" in both databases, matched on these columns.
NATURAL = {
    "users": ("email",), "labs": ("code",), "devices": ("device_uid",), "roles": ("name",),
    "assets": ("asset_tag",), "rfid_credentials": ("uid_hex",), "inventory_bins": ("code",),
    "lab_emergencies": ("lab_id",), "lab_devices": ("lab_id", "device_id"),
    "system_settings": ("key",),
}
SKIP = {"alembic_version"}
# A unique value that means "this very record is already in the target": skip it.
SAME_RECORD = {"integration_events": ("event_id",), "qr_tokens": ("token",),
               "issues": ("ticket_number",), "issue_photos": ("storage_key",)}
# A unique de-duplication token already used by a target row: the restored row
# keeps all its data and gets a marked token.
MARK_ON_CLASH = {"alerts": ("dedupe_key", ()), "notifications": ("dedupe_key", ("user_id",))}
# audit_logs keeps the id of what it is about as text: remap those too.
ENTITY_TABLE = {
    "user": "users", "booking": "bookings", "issue": "issues", "alert": "alerts",
    "device": "devices", "lab": "labs", "asset": "assets", "rfid_credential": "rfid_credentials",
    "qr_token": "qr_tokens", "access_session": "access_sessions", "notification": "notifications",
    "security_zone": "security_zones", "security_event": "security_events",
}
LAST = ("audit_logs",)


def url_for(db: str) -> str:
    base = os.environ["DATABASE_URL"].rsplit("/", 1)[0]
    return f"{base}/{db}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="staging database holding the backup")
    ap.add_argument("--target", required=True, help="database to merge into")
    ap.add_argument("--apply", action="store_true", help="commit (default: dry run, rolled back)")
    a = ap.parse_args()
    if a.source == a.target:
        sys.exit("source and target must differ")

    src_eng, dst_eng = create_engine(url_for(a.source)), create_engine(url_for(a.target))
    ms, md = MetaData(), MetaData()
    ms.reflect(src_eng)
    md.reflect(dst_eng)

    order = [t for t in md.sorted_tables if t.name not in SKIP and t.name not in LAST]
    order += [md.tables[n] for n in LAST if n in md.tables]
    idmap: dict[str, dict] = defaultdict(dict)        # table -> {source id: target id}
    report = []
    problems: list[str] = []

    with src_eng.connect() as sc, dst_eng.connect() as dc:
        tx = dc.begin()
        for dt in order:
            st = ms.tables.get(dt.name)
            if st is None:
                continue
            rows = [dict(r) for r in sc.execute(select(st)).mappings()]
            n = Counter(source=len(rows))
            if not rows:
                report.append((dt.name, n))
                continue
            cols = [c for c in st.columns.keys() if c in dt.columns]
            pk = [c.name for c in dt.primary_key.columns]
            has_id = pk == ["id"]
            fks = [(fk.parent.name, fk.column.table.name) for fk in dt.foreign_keys]
            taken = set(dc.execute(select(dt.c.id)).scalars()) if has_id else set()
            next_id = max([0, *taken, *(r["id"] for r in rows)]) + 1 if has_id else None
            deferred = []                                    # self-references set after insert

            for r in sorted(rows, key=lambda r: r.get("id") or 0):
                row = {c: r[c] for c in cols}
                ok = True
                for col, ref in fks:
                    v = row.get(col)
                    if v is None:
                        continue
                    if ref == dt.name and v not in idmap[ref]:
                        deferred.append((r.get("id"), col, v))
                        row[col] = None
                    elif v in idmap[ref]:
                        row[col] = idmap[ref][v]
                    elif dt.columns[col].nullable:
                        problems.append(f"{dt.name} id={r.get('id')}: {col}={v} has no match in {ref} - left empty")
                        row[col] = None
                    else:
                        problems.append(f"{dt.name} id={r.get('id')}: {col}={v} has no match in {ref} - NOT restored")
                        ok = False
                if not ok:
                    n["not restored"] += 1
                    continue

                if dt.name == "audit_logs" and row.get("entity_id") and row.get("entity_type") in ENTITY_TABLE:
                    ref = ENTITY_TABLE[row["entity_type"]]
                    try:
                        old = int(row["entity_id"])
                        if old in idmap[ref]:
                            row["entity_id"] = str(idmap[ref][old])
                    except ValueError:
                        pass

                key = NATURAL.get(dt.name)
                if key:
                    found = dc.execute(select(*[dt.c[c] for c in pk]).where(
                        and_(*[dt.c[c] == row[c] for c in key]))).first()
                    if found is not None:
                        if has_id:
                            idmap[dt.name][r["id"]] = found[0]
                        n["already there"] += 1
                        continue
                same = SAME_RECORD.get(dt.name)
                if same and all(row.get(c) is not None for c in same) and dc.execute(
                        select(func.count()).select_from(dt).where(and_(*[dt.c[c] == row[c] for c in same]))).scalar():
                    if has_id:
                        found = dc.execute(select(dt.c.id).where(and_(*[dt.c[c] == row[c] for c in same]))).scalar()
                        idmap[dt.name][r["id"]] = found
                    n["same record already there"] += 1
                    continue
                mark = MARK_ON_CLASH.get(dt.name)
                if mark and row.get(mark[0]):
                    col, scope = mark
                    if dc.execute(select(func.count()).select_from(dt).where(and_(
                            dt.c[col] == row[col], *[dt.c[s] == row[s] for s in scope]))).scalar():
                        row[col] = f"{row[col]}:restored:{r['id']}"
                        n["key marked"] += 1

                if has_id:
                    if r["id"] in taken:
                        row["id"] = next_id
                        next_id += 1
                        n["new id"] += 1
                    taken.add(row["id"])
                    idmap[dt.name][r["id"]] = row["id"]
                dc.execute(dt.insert().values(**row))
                n["restored"] += 1

            for old_id, col, v in deferred:
                if v in idmap[dt.name] and old_id in idmap[dt.name]:
                    dc.execute(dt.update().where(dt.c.id == idmap[dt.name][old_id]).values({col: idmap[dt.name][v]}))
                else:
                    problems.append(f"{dt.name} id={old_id}: {col}={v} not found - left empty")
            if has_id and n["restored"]:
                dc.execute(text("SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                                "(SELECT MAX(id) FROM " + dt.name + "))"), {"t": dt.name})
            report.append((dt.name, n))

        print(f"{'table':26s} {'in backup':>9s} {'restored':>9s} {'already there':>14s}  notes")
        for name, n in report:
            notes = ", ".join(f"{k} {v}" for k, v in n.items()
                              if k not in ("source", "restored", "already there") and v)
            print(f"{name:26s} {n['source']:9d} {n['restored']:9d} "
                  f"{n['already there'] + n['same record already there']:14d}  {notes}")
        for p in problems:
            print("  !", p)
        if a.apply:
            tx.commit()
            print(f"\nCOMMITTED into {a.target}.")
        else:
            tx.rollback()
            print(f"\nDry run: nothing written to {a.target} (use --apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
