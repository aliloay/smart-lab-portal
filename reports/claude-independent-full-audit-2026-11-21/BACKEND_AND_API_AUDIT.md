# Backend and API audit

- **Scope:** `backend/app`, made up of 32 route modules (11,025 lines), about 70 services, `core/`, `deps.py`, models and 31 alembic migrations.
- **Live schema head:** `a7b3c9d1e240` (matches the repo).
- **Tests:** `tools\ops\test_backend_fast.ps1` gave **887 passed, 3 skipped** in 601 s (`evidence/backend_tests.log`).
  - Skipped because the inputs are not mounted in the throwaway container: the eval question set (`test_ai_router.py:14`), the n8n workflow copies (`test_automation_kinds.py:17`), plus one more.
  - There were 26 deprecation warnings (`HTTP_422_UNPROCESSABLE_ENTITY`). They are harmless.

## 1. Authorization sweep (VERIFIED FROM CODE)

- **Method:** I wrote an AST scan (`scratchpad/audit_routes.py`) that lists every route lacking `get_current_user`, `require_roles`, `require_device` or an equivalent check.
- **Unauthenticated routes found:**
  - `auth.py`: `/login`, `/signup`, `/signup-config`, `/username-suggestion`. These are public by design.
  - `equipment.py:1102` `/pc/enroll`: an HMAC enrolment code, plus `PC_ENROLL_OPEN` (default false), plus refusal of ADMIN devices. Correct.
  - `equipment.py:1172/1182` broadcast watch status and frame: a short-lived in-memory watch token issued only to device keys. Correct.
  - `opcua.py:41` `/snapshot`: `X-OPCUA-Key` with constant-time compare, 503 when unset. Correct.
  - `security.py:912` `/recordings/play`: a signed JWT link. **See F-01.**

### F-01 (P1): recording-link token works as an admin session

- `routes/security.py:906` issues `jwt.encode({"typ":"recording","dev":..,"name":..,"sub":str(admin.id),"exp":+10 min}, SECRET_KEY, ALGORITHM)` and returns it in a URL query string.
- `core/security.py:72-77` `decode_access_token` decodes any token signed with `SECRET_KEY` and never checks `typ`.
- `api/deps.py:25-39` `get_current_user` requires only `"sub"` in the payload, then loads that user. The role comes from the DB, so the user is an admin.
- **Result:** the recording URL token is a 10-minute admin Bearer token. URLs end up in browser history and nginx access logs.
- The emergency token (`services/emergency.py:72`) uses `"emg"`, not `"sub"`, so it is not affected.
- **Fix:**
  - Add `"typ":"access"` in `create_access_token`.
  - In `get_current_user`, reject any payload whose `typ` is not `"access"`.
  - Allow a short migration window for already-issued tokens, or force re-login.
  - Add `tests/test_token_types.py`: a recording token gets 401 on `/api/admin/users`.

### Device authentication (`deps.py:71-110`)

- **Shared key:** `DEVICE_API_KEY`, compared in constant time. It can be disabled with `DEVICE_SHARED_KEY=false`.
- **Per-device keys:** SHA-256 hashed. `device_scope()` prevents impersonation.
- **Lab PC keys:** restricted to `/api/equipment/*`.
- **Door reports:** limited to door devices (`access.py::_door_scope`).
- These checks are sound.

### Robot control

- **Live check:** `docker compose exec backend printenv ROBOT_CONTROL` returns `off`. LIVE-VERIFIED.
- **Adapters (`services/robot_control.py`):**
  - The `Adapter`, `FanucAdapter` and `URAdapter` paths all return `UNAVAILABLE` unless `ROBOT_CONTROL` is `dry_run` or `live`.
  - `live` additionally needs the UR agent in the same mode: two sign-offs.
  - `controller_mode()` defaults to UNKNOWN, which blocks commands.
- **Verdict:** safe.

## 2. User registration and approval (VERIFIED FROM CODE + tests)

1. **Sign-up (`auth.py:129-200`):**
   - Domain allow-list and a per-IP hourly cap, counted from audit rows.
   - Creates a `STUDENT` with `is_active = not SIGNUP_REQUIRES_APPROVAL`.
   - Writes a `USER_SIGNUP` audit row.
   - Sends `notify(admin_ids)` with severity warning and a link to `/admin/users`.
2. **Admin list (`admin.py:299-313`):** `pending_approval` = inactive, has a `USER_SIGNUP` row, and has **no** `USER_UPDATED`/`USER_REMOVED` row.
3. **Approve:** `PATCH /admin/users/{id}` with `is_active=true` (admin only; lab staff cannot change `is_active`). It writes a `USER_UPDATED` audit row containing the changes.
4. **Login of an inactive user:** returns 403 "Account is disabled" (`auth.py:65`), after the password check, so it does not enumerate accounts.
5. **Session after deactivation:** `get_current_user` rejects `is_active=false` on every request. Existing tokens die at once. Good.

### Weaknesses (F-17, P3)

- A lab-staff edit of a pending student's name or email creates `USER_UPDATED`. The account then drops out of "pending" and looks merely disabled, so the approval request is lost.
- A pending user is told "Account is disabled" rather than "waiting for approval".
- With `AUTO_ASSIGN_AUTH_SUBJECT`, a pending sign-up already reserves the next `USERn` door identity.
- There is no explicit reject action (reject = remove = `USER_REMOVED`), and no notification to the user on approval. That is acceptable on a local-only network.

### Live data

- 10 users: 9 active, 1 inactive STUDENT. This matches "1 pending (ahmed left pending for the approval demo)".
- I did not change it.

## 3. Device status and staleness (`services/devices.py`)

- `DEVICE_STALE_SECONDS = 90`.
- `device_out()` derives the state:
  - `NO_DATA` / `ONLINE` / `OFFLINE`.
  - **Camera:** DEGRADED when `source_ok` is false.
  - **Robot:** DEGRADED when a non-simulation robot has no `q` and no `robot_mode`.
  - **Face server and entry camera:** probed in a background thread every 15 s.
- **LIVE check:**
  - SECCAM rows have `is_online=t` with fresh `last_seen`, but `component_state.source_ok=false`, so the API shows DEGRADED. Correct.
  - Robots were last seen 3 days ago, so OFFLINE. Correct.
- The **robot UNKNOWN/STALE guard** is still correct in code:
  - `robot_collector.py:281-290` sends `TELEMETRY_STALE` once, then lets `last_seen` expire.
  - The frontend `robotLive.tsx:17-23` forces OFFLINE after 30 s and TELEMETRY_STALE after 3 s.
- **Presenter timeout:**
  - `pc_control.py:107` `PRESENTER_GONE_S = 90`.
  - `VIEWER_TIMEOUT_S = 6`, `FRAME_MAX_AGE_S = 5`, `BROADCAST_FRAME_MAX_AGE_S = 6`, `SHARE_REQUEST_TTL_S = 300`.
  - Present and sensible.

### Alert state consistency (F-13, P3)

- The ORM validator `models/tables.py:569-575` now forces `state='RESOLVED'` whenever `is_resolved=True`.
- No `update(Alert)` bulk statements were found, so nothing bypasses it.
- Three legacy rows (549, 551, 636 from October) still have OPEN/true. This is a data leftover, not a live bug.

## 4. Data access, performance and indexes

- **Indexes:** present on hot paths, for example `ix_sensor_lab_metric_time`, `ix_event_lab_time`, `ix_notification_user_unread`, and `ix_inventory_measurements_bin_time`.
- **Sequential-scan leaders:**
  - `security_zones` (365k scans) and `assets` (240k) are tiny tables, so this is irrelevant.
  - `sensor_readings`: 158 sequential scans over 16.9 M tuples in total, against 2.39 M index scans. That is occasional full reads, probably analytics. Low priority.
- **DB size:** 117 MB in total.
  - `sensor_readings` is 53 MB (219k rows).
  - `inventory_measurements` holds 77k rows and grows about 18k/day while the bin is active (about 1 Hz). Consider downsampling after 30 days.
- **N+1:** `list_users` loads all `USER_SIGNUP` and `USER_UPDATED` audit IDs on every call. That is fine at 10 users.
- **In-memory state:**
  - `_watch_tokens` is pruned on each issue.
  - `_uid_ids` is bounded by device count.
  - The login throttles and robot ownership live in process memory, which is lost on restart. That is by design.
- `/api/health` returned in 14 ms with `database:true` and a version stamp.

## 5. Contracts

- **Frontend:** `tsc` passes against `lib/api.ts`. The running images equal HEAD.
- **Firmware → backend:** the master (`portal-1.2`), env (`env-0.1.1`), bin (`bin-0.6`) and reuse (`reuse-mod-0.5`) all report, and their `firmware_version` in the DB matches the source strings. LIVE-VERIFIED.
- **n8n → backend:** `/api/automation/*` is used by 23 workflows. Runs are recorded in `audit_logs` (`AUTOMATION_RUN`, last at 17:21 UTC, 0 failures in 7 days).

## 6. Not verified

- Authenticated endpoint latency (I used no credentials), WebSocket reconnect behaviour under load, and concurrency races beyond the existing tests.
- The 25-concurrent-login result is historical.
