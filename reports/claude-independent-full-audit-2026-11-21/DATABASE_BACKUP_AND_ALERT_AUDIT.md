# Database, backup and alert audit

- **Access:** read-only SELECTs through `docker compose exec -T db psql -U smartlab -d smartlab` at 19:08–19:20 local.
- **No writes.** Alerts were not resolved and the pending user was not approved.

## Current data compared with the historical report

| Item | Historical (brief) | **Now (LIVE)** |
|---|---|---|
| Users | 10 (9 active, 1 pending) | **10: 9 active** (1 ADMIN, 2 LAB_STAFF, 6 STUDENT) **+ 1 inactive STUDENT** (the pending approval demo) |
| Labs | 11 | **11** (10 active; LAB_10 inactive) |
| Bookings | 26 | **26**; 0 pending; **0 overlapping** active bookings per lab (self-join check) |
| Access events | 2,384 | **2,437** |
| Consumables bins / items | 1 / 2 | **1 / 2** (10 kOhm resistors, Screws [selected]) |
| Open alerts | 272 | **4 open**. 264 were resolved through the audited API on 21 Nov (checkpoint; IDs in `D:\SmartLabData\db_dumps\alerts_resolved_20261121_ids.txt`). 819 alerts in total |
| Devices | – | 26 (5 ESP32, 2 security cameras, face server, 14 PC rows, 4 robot rows) |
| Audit log rows | – | 28,571 (of which 9,257 are `AUTOMATION_RUN`) |
| Notifications | – | 7,502 (541 today) |
| DB size | – | 117 MB (sensor_readings 53 MB / 219k rows; inventory_measurements 77,856 rows) |
| Alembic head | – | `a7b3c9d1e240` (bin items, additive) |

### The 4 open alerts

| ID | Title | Created (UTC) |
|---|---|---|
| 1107, 1108 | Security camera: no picture | 11-20 19:41, still recurring (11 occurrences) |
| 1109 | Repeated refusals at LAB_01 | 11-20 19:45 |
| 1128 | ADMIN-LAPTOP: PC agent was stopped and restarted | 11-21 13:50 |

All four are real current conditions.

### Inconsistent alert rows (F-13, P3)

- IDs 549, 551 and 636 have `state='OPEN'` while `is_resolved=true`. They date from 12–17 Oct, before the `@validates("is_resolved")` sync in `models/tables.py:569`.
- No code path bypasses the validator today: there are no `update(Alert)` bulk statements.
- **Owner decision:** fix them through an audited one-row update, or leave them.

## Online status correctness

- **SECCAM_LAB01/02:** `is_online=t` with a fresh `last_seen`, while the camera has no picture. The API derives DEGRADED from `source_ok=false`, which is correct in the UI. Raw DB consumers, such as the OPC UA snapshot, use `device_out` too (`opcua.py`), which is good.
- **FACESRV_01:** `is_online=f`, never seen. Its state is probed live by the backend, which is correct in the UI.
- **3 retired TEST PCs:** `component_state.state='RUNNING'`, but offline by heartbeat age. This is cosmetic.

## Retention

- `sensor_readings` and `inventory_measurements` grow without pruning. inventory_measurements runs at about 18.5k rows/day while the bin is active. At 117 MB this is not a problem for the thesis; recommend downsampling after 30 days, later.
- `audit_logs`: a third of the rows are automation runs. Consider logging only runs with findings, or changes.

## Backups (VERIFIED FROM CODE + LIVE)

### Service

- Defined in `docker-compose.yml:35-105`.
- Every 6 h (`BACKUP_EVERY_HOURS`), the service waits by wall clock (survives suspend) and runs `pg_dump -Fc` followed by a `pg_restore --list` validation.
- It retries in 5 min on failure.
- It also writes a daily `tar` of `/uploads`.
- The healthcheck is based on the age of `backup_status.json`.

### Status

- `backup_status.json`: ok, last success **2026-11-21 15:58 UTC**, `auto_smartlab_20261121_1758.dump` (5,112 KB).
- I confirmed the header is `PGDMP` and the TOC lists 44 TABLE DATA entries (`pg_restore --list` inside the backup container, read-only).
- **Failures:** 2 logged (11-20 19:25 and 19:32 UTC, "connection refused" during DB restarts), each recovered at the next retry.

### Problems (F-09, P2)

- **No retention:**
  - `./backups` holds **103 auto dumps** since 6 Oct, plus **daily uploads tarballs of about 300 MB each**, in 6.2 GB on C:.
  - It is also mixed with about 250 hand-made code backup files (for example a 70 MB `vision.py.broken-20261012`).
- **Encryption:**
  - `BACKUP_PASSPHRASE` is empty (all files are `.dump`, none `.enc`), so dumps are unencrypted.
  - **The uploads tarball is never encrypted, even when a passphrase is set.** The code encrypts only the dump.
  - The uploads hold `security/5` (2,137 files), `security/12` (947), issue photos and more: camera snapshots of people.
- **Off-disk copies:**
  - Only manual pre-deploy dumps exist on D: (`D:\SmartLabData\db_dumps`: 6 dumps, latest `before_alert_cleanup_20261121.dump` and `predeploy_live_answers_20261121.dump`).
  - There is no automatic copy to a second disk.
- **Restore evidence:** only TOC validation. **No test restore** into a scratch database was found or performed.

### Recommended (owner decides the periods)

1. Keep daily dumps for 14 days and weekly for 8 weeks; keep uploads tarballs for 7 days.
2. Encrypt the uploads tar with the same passphrase logic.
3. Copy nightly to `D:\SmartLabData\db_dumps\auto\`.
4. Monthly restore test: `docker run --rm postgres:16-alpine` with `pg_restore` into a temporary DB, then compare row counts.
5. Move the code backups out of `./backups`.
