# Database

PostgreSQL, managed with Alembic. 21 tables. The models in
`backend/app/models/tables.py` are the source of truth; CI runs
`alembic upgrade head` on an empty database and then `alembic check`, which
fails if the migrations and the models disagree in any way.

## Rules that run through the schema

1. **Every lab-scoped row carries `lab_id`.** An event that cannot be
   attributed to a laboratory is useless for traceability.
2. **No biometric material.** Fingerprint templates stay in the AS608's own
   flash; face images stay in the face server's `dataset/`. The database
   stores identity references (`users.auth_subject`) and outcomes only.
3. **Every timestamp is `TIMESTAMPTZ`.** Booking windows are compared in UTC.
4. **Enums are `VARCHAR` + check constraint** (`native_enum=False`), so adding
   a value is a model change, not an `ALTER TYPE`.
5. **Unknown is `NULL`, never a default.** `devices.door_closed`,
   `devices.component_state`, `assets.last_inspected_at` and the rest are
   `NULL` until something real reports them.

## Tables

### Identity

| Table | Purpose | Notes |
|---|---|---|
| `users` | people | `role` STUDENT / LAB_STAFF / ADMIN; `auth_subject` (e.g. `USER1`) is the bridge to the firmware and face server — unique, nullable until enrolled |
| `roles` | role descriptions for the admin UI | the enum on `users` is what is enforced |
| `rfid_credentials` | card UIDs | first factor only (a UID is cloneable) |

### Facility

| Table | Purpose | Notes |
|---|---|---|
| `labs` | laboratories | `code` (e.g. `LAB_01`) is what the ESP32 sends; `has_controller` is true only where door hardware exists; `exclusive_booking`, `require_booking_for_rfid` |
| `devices` | master controllers, cameras, face server, sensor nodes | `device_uid`, `last_seen_at`, `is_online`, `door_closed` (NULL = never reported), `component_state` (JSON, NULL until firmware sends it) |
| `lab_devices` | a device additionally serving another lab | |

### Bookings and credentials

| Table | Purpose | Notes |
|---|---|---|
| `bookings` | reservations | status PENDING / CONFIRMED / CANCELLED / REJECTED / COMPLETED; `ck_booking_window` (start < end); `first_entry_at`, `last_entry_at`, `entry_count` record actual use |
| `qr_tokens` | the door credential | opaque `SLB:<22 chars>`; carries no user/lab/time — all looked up at scan; `revoked_at`, `use_count` |

### Access

| Table | Purpose | Notes |
|---|---|---|
| `access_attempts` | one row per credential presentation | security view; `denial_reason` names why; `credential_ref` is truncated, never the raw credential |
| `access_events` | the full narrative timeline | 27 event types (booking, QR, RFID, fingerprint, face, identity mismatch, access, door, exit, device, asset) |
| `access_sessions` | one occupancy span per granted entry | door open/close recorded **on** the session but do not end it; `end_reason` EXIT_RECORDED / BOOKING_ENDED / DOOR_NOT_OPENED / SUPERSEDED / NO_EXIT_TIMEOUT |

### Equipment

| Table | Purpose | Notes |
|---|---|---|
| `assets` | equipment | `asset_tag`, `name`, `category`, `lab_id`, `status` AVAILABLE / CHECKED_OUT / MAINTENANCE / RETIRED, `serial_number`, `holder_id` (current user), `checked_out_at`, `last_inspected_at`, `next_maintenance_at` |
| `asset_transactions` | the asset's usage log | `action` CHECKOUT / RETURN / INSPECTION / STATUS_&lt;new status&gt; |

### Maintenance

| Table | Purpose | Notes |
|---|---|---|
| `issues` | problem reports | `ticket_number` ISS-YYYY-NNNNNN; category, severity, status; optional `asset_id` / `device_id` / `access_event_id`, each validated to belong to the issue's lab |
| `issue_photos` | photo metadata | `stage` REPORT / BEFORE / AFTER; bytes live in storage under `storage_key` |
| `issue_comments` | discussion | `is_internal` = staff-only |
| `issue_history` | audit trail **and** timeline | every change writes one row in the same transaction |

### Operations

| Table | Purpose | Notes |
|---|---|---|
| `notifications` | in-portal messages | `kind`, `severity`, `link` (a portal route, never external) |
| `alerts` | operational alerts (device offline, …) | |
| `audit_logs` | who did what in the portal | distinct from physical access events |
| `sensor_readings` | environmental data | **structure only** — nothing writes here until a sensor node exists |

## Indexes worth knowing

Beyond primary keys, unique columns and single-column foreign-key indexes:

| Index | Serves |
|---|---|
| `ix_booking_lab_window (lab_id, start_time, end_time)` | conflict detection, availability |
| `ix_booking_user_start (user_id, start_time)` | "my bookings" |
| `ix_event_lab_time`, `ix_event_type_time`, `ix_event_user_time` | lab activity, filters, a person's timeline |
| `ix_attempt_lab_time` | security view |
| `ix_session_lab_open (lab_id, ended_at)` | "who is inside now" |
| `ix_asset_tx_asset_time (asset_id, created_at)` | asset lifecycle timeline |
| `ix_assets_next_maintenance_at` | "maintenance due" |
| `ix_issue_status_severity`, `ix_issue_lab_status` | maintenance queues |
| `ix_notification_user_unread` | the bell badge |
| `ix_sensor_lab_metric_time` | sensor charts (when data exists) |

## Migrations

```
01e33b3ee809  initial schema
392460921eaf  lab catalogue and booking entry tracking
b8d41f7a2c90  maintenance, notifications and honest sessions
c3e5a91d4b27  asset lifecycle and query indexes          ← head
```

`c3e5a91d4b27` only **adds**: five nullable asset columns, a foreign key,
two single-column and four composite indexes. It backfills `holder_id` for
items already checked out from their latest CHECKOUT transaction. It has a
working downgrade.

### Upgrading a database that holds real data

```bash
# 1. back it up first — always
pg_dump -U postgres -d smartlab -F c -f smartlab-$(date +%Y%m%d).dump

# 2. see what will run
cd backend
alembic current          # where the database is
alembic history -r current:head

# 3. apply
alembic upgrade head

# restore if ever needed:
# pg_restore -U postgres -d smartlab --clean smartlab-YYYYMMDD.dump
```

The API refuses to start against a database that is behind head, so a
forgotten migration shows up immediately, not as a half-working page.

### Checking the migrations match the models

```bash
createdb smartlab_mig
DATABASE_URL=postgresql+psycopg://postgres:<pw>@localhost:5432/smartlab_mig alembic upgrade head
DATABASE_URL=postgresql+psycopg://postgres:<pw>@localhost:5432/smartlab_mig alembic check
# -> No new upgrade operations detected.
```
