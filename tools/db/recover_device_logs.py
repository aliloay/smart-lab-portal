"""
Recover access events that only exist in device logs - insert only.

  * the door controller's serial log (the serial bridge's com6.log): events the
    door tried to send while the laptop was on another network
    ("[PORTAL] event X not recorded (HTTP -1)"). Who and how come from the
    log's own lines ([STATE] -> WAIT_... (NAME / USERx), [AUTH][...], [FP]).
  * the face server's recognition_log.csv: face checks from before the
    portal recorded them.

The lines carry the time of day only; dates come from the file's last write
(the log's last line) by counting back over midnights. Every recovered row
says so in its message and in event_metadata.source, so it is never mistaken
for a live record. Rows already present (same type, same second) are skipped.

    py recover_device_logs.py --door com6.log --door-end 2026-10-05 --face recognition_log.csv > recover.sql
    (then psql -1 -f recover.sql, after a backup)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys

TZ = dt.timezone(dt.timedelta(hours=3))          # Cairo, summer time: the log's clock
LAB_ID, DOOR_DEVICE_ID, FACE_DEVICE_ID = 1, 1, 3
TAG = " (recovered from the door's log)"

LINE = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)$")
SENT = re.compile(r"\[PORTAL\] event ([A-Z_]+) not recorded")
WAIT = re.compile(r"\[STATE\] -> WAIT_[A-Z_]+ \((.+?) / (USER\d+)\)")
DENIED = re.compile(r"\[AUTH\]\[DENIED\] (.+?)\s*$")
GRANTED = re.compile(r"\[AUTH\]\[GRANTED\] (.+?) \((USER\d+)\) - (\w+)")
FP = re.compile(r"\[FP\] Matched fingerprint ID (\d+)")
STEP1 = re.compile(r"\[(RFID)\]\[UID\]|\[(QR)\]")


def door_rows(path: str, end_day: dt.date):
    raw = []
    with open(path, "rb") as f:
        for b in f:
            m = LINE.match(b.decode("utf-8", "replace").rstrip("\r\n"))
            if m:
                raw.append((int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]), m[4]))
    # days: a clock that goes back by more than an hour crossed midnight
    day, days, prev = 0, [], None
    for t, _ in raw:
        if prev is not None and t < prev - 3600:
            day += 1
        days.append(day)
        prev = t
    first = end_day - dt.timedelta(days=day)

    who = name = method = reason = fp = None
    rows = []
    decisions = []           # every [AUTH] decision the door took
    failed = []              # (kind, when) of every event the door could not send
    for (t, text), d in zip(raw, days):
        if (m := WAIT.search(text)):
            name, who = m[1], m[2]
            reason = fp = None
        elif (m := STEP1.search(text)):
            method = m[1] or m[2]
        elif (m := DENIED.search(text)):
            reason = m[1]
            decisions.append({"kind": "ACCESS_DENIED", "who": who, "name": name, "method": method, "reason": m[1],
                        "t": t, "d": d})
        elif (m := GRANTED.search(text)):
            decisions.append({"kind": "ACCESS_GRANTED", "who": m[2], "name": m[1], "method": method, "reason": None,
                        "t": t, "d": d})
        elif (m := FP.search(text)):
            fp = m[1]
        elif "[ALARM]" in text and "forced entry" in text:
            reason = "FORCED_ENTRY"
        if not (m := SENT.search(text)):
            continue
        kind = m[1]
        failed.append((kind, d * 86400 + t))
        at = dt.datetime.combine(first + dt.timedelta(days=d), dt.time(t // 3600, t // 60 % 60, t % 60), TZ)
        row = {"event_type": kind, "subject": None, "method": None, "result": None, "reason": None}
        if kind == "ALARM":
            row.update(reason="FORCED_ENTRY", message="Door opened while locked - no access had been granted")
        elif kind == "DOOR_CLOSED":
            row.update(subject=who, message="Door closed - relocked")
        elif kind == "ACCESS_GRANTED":
            row.update(subject=who, method=method or "RFID", result="GRANTED", message=f"Access granted to {name}")
        elif kind == "FINGERPRINT_ACCEPTED":
            row.update(subject=who, method="FINGERPRINT", result="GRANTED", message="Fingerprint matched")
        elif kind == "IDENTITY_MISMATCH":
            row.update(subject=who, method="FINGERPRINT", result="DENIED", reason="IDENTITY_MISMATCH",
                       message=f"Step 1 was {who} but fingerprint matched ID {fp}")
        elif kind == "ACCESS_DENIED":
            row.update(subject=who, method=method or "RFID", result="DENIED", reason=reason,
                       message=f"Denied at door: {reason}")
        else:
            row.update(subject=who, message=kind.replace("_", " ").lower())
        row.update(at=at, device_id=DOOR_DEVICE_ID, message=row["message"] + TAG,
                   meta={"source": "door serial log", "file": path.replace("\\", "/").rsplit("/", 1)[-1],
                         "recovered": True})
        rows.append(row)
    # A decision whose event the door did not report as failed (within 15 s)
    # reached the portal at the time - and was lost in the wipe.
    lost = [x for x in decisions if not any(k == x["kind"] and 0 <= w - (x["d"] * 86400 + x["t"]) <= 15
                                           for k, w in failed)]
    for x in lost:
        at = dt.datetime.combine(first + dt.timedelta(days=x["d"]),
                                 dt.time(x["t"] // 3600, x["t"] // 60 % 60, x["t"] % 60), TZ)
        granted = x["kind"] == "ACCESS_GRANTED"
        rows.append({"event_type": x["kind"], "subject": x["who"], "method": x["method"] or "RFID",
                     "result": "GRANTED" if granted else "DENIED", "reason": x["reason"],
                     "message": (f"Access granted to {x['name']}" if granted else f"Denied at door: {x['reason']}")
                                + " (recovered from the door's log: it reached the portal but was lost in the 5 Oct wipe)",
                     "at": at, "device_id": DOOR_DEVICE_ID,
                     "meta": {"source": "door serial log", "recovered": True, "lost_in_wipe": True}})
    return rows


def face_rows(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            at = dt.datetime.fromisoformat(r["timestamp"]).replace(tzinfo=TZ)
            ok = r["access"].strip().lower() == "true"
            who = r["name"] if r["name"] and r["name"] != "unknown" else None
            rows.append({"event_type": "FACE_ACCEPTED" if ok else "FACE_REJECTED", "subject": who,
                         "method": "FACE", "result": "GRANTED" if ok else "DENIED", "reason": None,
                         "message": (f"Face matched {who} (distance {r['distance']})" if ok
                                     else f"Face not recognised (distance {r['distance']})")
                                    + " (recovered from the face server's log)",
                         "at": at, "device_id": FACE_DEVICE_ID,
                         "meta": {"source": "face server recognition_log.csv", "recovered": True}})
    return rows


def q(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--door")
    ap.add_argument("--door-end", help="date of the door log's last line, YYYY-MM-DD")
    ap.add_argument("--face")
    a = ap.parse_args()
    rows = []
    if a.door:
        rows += door_rows(a.door, dt.date.fromisoformat(a.door_end))
    if a.face:
        rows += face_rows(a.face)
    print("-- generated by tools/db/recover_device_logs.py: insert only")
    for r in rows:
        user = f"(SELECT id FROM users WHERE auth_subject = {q(r['subject'])})" if r["subject"] else "NULL"
        at = q(r["at"].isoformat())
        print(f"INSERT INTO access_events (event_type, lab_id, user_id, device_id, method, result, reason, "
              f"message, event_metadata, created_at) SELECT {q(r['event_type'])}, {LAB_ID}, {user}, "
              f"{r['device_id']}, {q(r['method'])}, {q(r['result'])}, {q(r['reason'])}, {q(r['message'][:255])}, "
              f"{q(json.dumps(r['meta']))}::json, {at} WHERE NOT EXISTS (SELECT 1 FROM access_events "
              f"WHERE event_type = {q(r['event_type'])} AND date_trunc('second', created_at) = {at}::timestamptz);")
    kinds = {}
    for r in rows:
        kinds[r["event_type"]] = kinds.get(r["event_type"], 0) + 1
    first, last = min(r["at"] for r in rows), max(r["at"] for r in rows)
    print(f"-- {len(rows)} rows, {first} .. {last}: {kinds}", file=sys.stderr)


if __name__ == "__main__":
    main()
