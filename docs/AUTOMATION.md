# Automation (n8n), events and analytics

This document covers the layer added on top of the working portal: a
transactional event outbox, an automation API for n8n, twelve n8n workflows,
and the analytics behind the Operations Center. None of it changes the door.

## 1. The rule this layer never breaks

```
QR / RFID ──► FastAPI validates ──► step 1 identity ──► fingerprint / face
          ──► Master ESP32 matches the identity ──► relay
```

That path is unchanged. **n8n is not on it.** There is no ESP32 → n8n →
relay route, no endpoint that lets n8n open, lock or unlock a door, and no
workflow that cancels a booking. If n8n is down, misconfigured or deleted,
the door, booking, QR and audit trail behave exactly as before.

| Concern | Owner |
|---|---|
| Door decision, relay | Master ESP32 |
| Business rules, data, validation | FastAPI + PostgreSQL (source of truth) |
| *When* something runs, *where* its result goes | n8n |
| Charts | the React frontend, from backend aggregates |

## 2. Events: the outbox

Every relevant change stages a row in `integration_events` **in the same
transaction** as the change. If the change rolls back, so does the event.

```
request ─► state change + audit row + outbox row ─► COMMIT
                                                      │
        dispatcher thread (optional) ──POST──► n8n webhook   (pushed types)
        n8n / any consumer ─────────GET─────► /api/automation/events (all)
```

Envelope (what n8n receives):

```json
{
  "event_id": "1eed5287-f7e1-4175-9cf9-7feb8e4b4bde",
  "sequence": 42,
  "type": "access.denied",
  "occurred_at": "2026-09-26T09:14:03.120Z",
  "lab_id": 1, "user_id": 2, "device_id": 1,
  "object": {"type": "booking", "id": "17"},
  "correlation_id": "booking:17",
  "payload": {"reason": "BOOKING_NOT_STARTED", "method": "QR", "...": "..."}
}
```

* `event_id` is the idempotency key: a push retried after a timeout carries
  the same id.
* `correlation_id` ties the events of one booking, issue or device together.
* Payloads never contain secrets, tokens or biometric data.

Event types: `booking.created`, `booking.confirmed`, `booking.cancelled`,
`access.granted`, `access.denied`, `access.identity_mismatch`,
`door.opened`, `door.closed`, `door.alarm` (forced entry / held open),
`device.online`, `device.offline`, `device.component_fault`,
`asset.checked_out`, `asset.returned`, `session.exit_recorded`,
`session.ended`, `issue.created`, `issue.status_changed`.
Scan and attempt noise (`QR_SCAN`, `*_ATTEMPT`) stays in the audit log only.

**Delivery.** With `AUTOMATION_WEBHOOK_BASE` set, a daemon thread POSTs
`AUTOMATION_PUSH_TYPES` to `{base}/smartlab-{type with . → -}` with header
`X-Smartlab-Token`. It uses exponential backoff from 30 s and gives up after
`AUTOMATION_MAX_ATTEMPTS` (status `FAILED`). Everything else is `SKIPPED`
(recorded for the pull feed only). `FOR UPDATE SKIP LOCKED` stops two workers
from sending the same row, and delivered/skipped rows are pruned after
`AUTOMATION_RETENTION_DAYS`. The outbox is an integration record;
`access_events` remains the audit trail.

## 3. The automation API

Base `/api/automation`. Every call needs `X-Automation-Key:
<AUTOMATION_API_KEY>`, compared in constant time. With no key configured,
every call returns **503**, and a user JWT is not accepted. The rules live
here, in `app/services/automation.py`, so no workflow re-implements them.

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | event catalogue, pushed types |
| GET | `/events?after=&limit=&types=` | outbox feed, resume from `next_after` |
| GET | `/bookings/upcoming?within_minutes=` | bookings about to start + **lab readiness** + `reminder_sent` |
| GET | `/bookings/ended?minutes=` | just-ended bookings: attended / missed, exit observed, ready-made message |
| GET | `/bookings/{id}` | one booking + readiness |
| POST | `/bookings/{id}/remind` | the portal's own reminder, at most once per booking |
| GET | `/access/denials?lab_id=&window_minutes=` | refusal burst: `none` / `normal` / `warning` |
| GET | `/devices/offline` | offline devices, minutes silent, escalation level 1-3, audience |
| GET | `/maintenance` | overdue (per SLA), urgent unassigned, equipment due ≤ 7 days |
| GET | `/issues/{id}` | issue + bookings in that lab in the next 24 h |
| GET | `/reports/daily?day=` · `/reports/weekly?end=` | counts from recorded rows + text lines |
| GET | `/sensors/evaluate?max_age_minutes=` | latest reading per metric vs thresholds; `no_data` when none |
| GET | `/data-quality` | read-only consistency checks |
| GET | `/anomalies?hours=` | rule-based anomalies |
| POST | `/notify` | in-portal notification to a user / staff / admins, **idempotent on `dedupe_key`** |
| POST | `/alerts` | an alert, **idempotent on `dedupe_key`** |
| POST | `/runs` | "workflow X ran" → shown in the Operations Center |

`/notify` accepts only automation kinds (`BOOKING_BRIEFING`,
`PRE_BOOKING_CHECK`, `SECURITY_EVENT`, `DEVICE_OFFLINE`,
`MAINTENANCE_DIGEST`, `DAILY_REPORT`, `WEEKLY_REPORT`, `SENSOR_THRESHOLD`,
`POST_SESSION`, `DATA_QUALITY`, `ANOMALY`) and portal-relative links only.
It cannot impersonate portal events such as `BOOKING_CONFIRMED`.

Configurable rules (backend env, see `backend/.env.example`):
`DENIAL_WINDOW_MINUTES`=10, `DENIAL_WARNING_COUNT`=3,
`DEVICE_ESCALATE_L2_MINUTES`=15, `DEVICE_ESCALATE_L3_MINUTES`=60,
`LAB_OPEN_HOURS_PER_DAY`=10, `LOCAL_TIMEZONE`=Africa/Cairo,
`AFTER_HOURS_START/END`=22/6,
`SENSOR_THRESHOLDS`=`temperature=16:30,humidity=20:70,co2=:1000,noise=:85`.

Sensor readings arrive at `POST /api/access/telemetry` (device key) from a
future sensor node. Until one reports, every view says **"Awaiting sensor
data"**. Nothing is simulated.

## 4. The twelve workflows

Sources: `automation/n8n/src/*.ts` (n8n Workflow SDK, generated by
`automation/n8n/gen.py`). They were validated and created in the n8n
project listed in `automation/n8n/workflows.json`. Every workflow ends in
*Record Run*, which reports to `/runs`.

| # | Workflow | Trigger | What it does |
|---|---|---|---|
| 01 | Booking confirmation briefing | `booking.confirmed` | heads-up to the student only if the lab is not in a normal state |
| 02 | Upcoming reminders | every 5 min | `/remind` for bookings starting within 20 min, once per booking |
| 03 | Access denial intelligence | `access.denied` | 1 refusal = normal; 3 in 10 min = one alert + staff notification. Never locks/unlocks |
| 04 | Device offline escalation | `device.offline` + every 5 min | L1/L2 → staff, L3 (60 min) → admins, critical; once per outage per level |
| 05 | Maintenance automation | `issue.created` + daily 08:00 | urgent issue in a booked lab → staff at once; daily digest |
| 06 | Daily report | daily 20:00 | backend report → administrators |
| 07 | Weekly report | Mondays 07:00 | with previous-week comparison |
| 08 | Sensor thresholds | every 10 min | breach → alert + staff; stale ≠ OK; no data → nothing |
| 09 | Pre-booking check | every 15 min | lab not ready within the hour → warn student and staff. **Never cancels** |
| 10 | Post-session | every 30 min | attended summary (honest about unrecorded exits) or missed-booking note |
| 11 | Data quality | daily 06:00 | read-only checks → admins if any fail |
| 12 | Anomaly detection | hourly | explainable rules → staff, once per rule / lab / day |

Anomaly rules: denial burst (sliding window), repeated identity mismatch
for the same credential, access granted out of hours, forced entry, door
held open repeatedly, device flapping (≥ 3 outages), refusals above 3× the
lab's own 7-day baseline. No ML model is used, because there is no labelled
training data. That is stated rather than faked.

## 5. Running it (verified end to end)

### Option A: self-hosted n8n next to the portal (recommended)

**1. Secrets:** in the repo root `.env` (gitignored; see `.env.example`), generate each value with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`:

```
AUTOMATION_API_KEY=<random>
AUTOMATION_WEBHOOK_BASE=http://n8n:5678/webhook
AUTOMATION_WEBHOOK_TOKEN=<random>
N8N_ENCRYPTION_KEY=<random>
```

**2. Start:**

```bash
git pull
docker compose --profile automation up -d --build
```

The normal `docker compose up` (and the launch script) does **not** start
n8n. That is intentional: the portal never depends on it. With the profile,
the editor is at http://localhost:5678 (bound to this laptop only) and n8n
reaches the API as `http://backend:8000`.

**3. Import the 12 workflows:** they are version-controlled in
`automation/n8n/json/`, mounted into the container at `/workflows`:

```bash
docker compose --profile automation exec n8n n8n import:workflow --separate --input=/workflows
```

**4. Create the two credentials in the n8n editor** (Credentials → Add). The
names must match exactly:

| Name | Type | Setting |
|---|---|---|
| `Smart Lab automation key` | Simplified Custom Auth (`httpTemplatedCustomAuth`) | template `{"headers":{"X-Automation-Key":"{{automation_key}}"}}`, value = `AUTOMATION_API_KEY` |
| `Smart Lab webhook token` | Header Auth | name `X-Smartlab-Token`, value = `AUTOMATION_WEBHOOK_TOKEN` |

Open each workflow, select these credentials on the nodes that ask for them
(the exported JSON references them by name only, never by id or value),
save, and **Publish/Activate**.

**5. Check it:** in the portal, Operations Center → *Automation (n8n)* shows
the API and push as enabled, the outbox counts and each workflow's runs.

### Option B: n8n Cloud

The same 12 workflows exist in the n8n Cloud project (`workflows.json` lists
their ids). n8n Cloud cannot reach a laptop on a private LAN, so it needs a
public HTTPS URL for the backend (for example a Cloudflare Tunnel) in place of
`http://backend:8000` in the HTTP nodes. Set
`AUTOMATION_WEBHOOK_BASE=https://<you>.app.n8n.cloud/webhook`; outbound pushes
work without a tunnel.

### Changing a workflow

Edit `automation/n8n/gen.py` (or `src/*.ts`), then rebuild the JSON:

```bash
cd automation/n8n
python3 gen.py                                  # SDK sources
npm i --no-save @n8n/workflow-sdk@0.33.1        # once
node build_json.mjs                             # src/*.ts -> json/*.json
```

`export_workflows.py` downloads the live versions from any n8n instance
through its public API (key read from the environment only).

### Release verification (2026-09-26)

Verified on the real Docker Compose stack (db, backend, frontend, n8n 2.40.7):

* Fresh volume: Alembic migrated to head (`d7a4c2e9f1b3`), seed ran, and
  `/api/health` answered directly and through nginx on port 80.
* n8n reached `http://backend:8000`; all 12 workflows imported through the CLI.
* A webhook call without `X-Smartlab-Token` → 403.
* **End to end:** 3 × real `POST /api/access/deny` → 3 outbox rows DELIVERED
  → workflow 03 → `/access/denials` level `warning` → **1** alert and **1**
  notification per staff member → run recorded in the Operations Center.
* **Deduplication:** a 4th identical refusal → the workflow ran again, still
  1 alert and 1 notification per person.
* **n8n stopped:** login, booking, QR issuance, `validate-qr` (valid), deny
  and the Operations Center all worked; the event stayed PENDING and was
  DELIVERED on the retry after n8n came back.

## 6. Failure modes

| Failure | Effect |
|---|---|
| n8n down / unreachable | Rows stay `PENDING` and retry with backoff, then `FAILED` (re-queueable). Door, booking, QR and portal unaffected. Operations Center shows the failure |
| Automation key unset | `/api/automation/*` → 503; outbox still records; pages unaffected |
| Workflow retried / run twice | `dedupe_key` makes notifications and alerts land once; reminders are once per booking |
| Backend down | n8n calls fail and n8n logs the execution error. The door already fails closed |
| Graphify unavailable | Nothing depends on it at runtime (see below) |

## 7. Analytics (Operations Center, lab twin, student view)

`GET /api/analytics/operations?days=&lab_id=` (staff),
`/api/analytics/labs/{id}` (any user, no per-person data), and
`/api/analytics/me` (the caller's own bookings only).

Honesty rules, enforced in `app/services/analytics.py`:

* **Utilisation** is booked hours ÷ (`LAB_OPEN_HOURS_PER_DAY` × days). The
  denominator is shown on the chart.
* **Time inside** exists only for sessions with an observed exit. Others
  count as "Exit not recorded", or "Session ended" when the booking closed.
* **Device availability** is drawn only as the outages the portal observed,
  from a `DEVICE_OFFLINE` event to the next `DEVICE_ONLINE`. A device that
  never reported has no figure.
* **Environment** shows "Awaiting sensor data" until a sensor node posts.
* Heatmaps are bucketed in `LOCAL_TIMEZONE`.

## 8. Graphify

What Graphify is: a service that builds a knowledge graph of a **codebase**
(local files or a GitHub repository), exposed to AI tools through an MCP
endpoint (`https://api.graphify.net/mcp`, Bearer API key). It is not a
live-data charting service.

What was done with it: nothing at runtime, by design.

* The Graphify MCP was not connected to the session that built this layer.
  No Graphify tool was available, so no graph was generated automatically.
  Nothing in this document claims otherwise.
* The portal's charts are drawn by the frontend from backend aggregates;
  they do not depend on Graphify, and no Graphify key is stored anywhere in
  the repository or the portal.
* For the thesis, use it as an architecture map: in the Graphify console,
  build a project from `github.com/aliloay/smart-lab-portal`. The graph shows
  the modules (routes → services → models), the outbox and the automation
  API as described in section 2.
* Keep the API key in your own MCP client configuration only. Never commit
  it, and revoke any key that has been pasted into a chat or document.
