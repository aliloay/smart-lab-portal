# Architecture

How the Smart Laboratory portal is put together, and — more importantly —
where each responsibility lives and where it deliberately does **not**.

## The chain

```
 ┌──────────────┐  HTTPS/JSON   ┌──────────────┐   SQL    ┌──────────────┐
 │ React portal │ ────────────► │   FastAPI    │ ───────► │  PostgreSQL  │
 │  (browser)   │ ◄──────────── │   backend    │ ◄─────── │              │
 └──────────────┘  WebSocket    └──────────────┘          └──────────────┘
        ▲          /ws/activity        ▲   │
        │ shows QR                     │   │ identity (auth_subject) or a refusal reason
        │                              │   ▼
        │                     ┌─────────────────────┐  X-Device-Key
        │                     │    Master ESP32     │  validate-qr / validate-rfid
        │                     │  owns the relay     │  events / heartbeat
        │                     └─────────────────────┘
        │                        ▲         ▲      │
        │                RFID ───┘         │      └──► RELAY ──► door lock
        │           fingerprint (AS608)    │ /status (QR payload, face result)
        │                                  │
 ┌──────┴───────┐   frames   ┌─────────────┴───────┐
 │ phone screen │ ─────────► │     ESP32-CAM       │ ── JPEG ──► Face server (Flask,
 └──────────────┘  (QR)      └─────────────────────┘             OpenCV LBPH + QR decode)
```

| Component | Responsibility | Never does |
|---|---|---|
| **React portal** | booking, QR display, dashboards, maintenance, audit views | talk to devices |
| **FastAPI backend** | *authorises* a credential for one lab and one window, returns one identity, logs every event | drive the relay, accept biometric data |
| **PostgreSQL** | users, bookings, credentials, events, sessions, issues, notifications | store biometric templates or face images |
| **Master ESP32** | reads step 1 (RFID/QR via camera), step 2 (fingerprint/face), compares identities, **owns the lock** | trust a network message to open the door |
| **ESP32-CAM** | captures frames, forwards them to the face server | decide access |
| **Face server** | QR decoding and LBPH face recognition | know about bookings |

## The non-negotiable guarantees

1. **The backend never drives the relay.** No endpoint reaches the lock. The
   firmware writes the relay in exactly two places, both in the local state
   machine, neither reachable from network code.
2. **A QR code never unlocks the door by itself.** It is step 1 only; it
   resolves to one identity.
3. **Step 2 must match step 1.** A fingerprint or face belonging to anyone
   else is `IDENTITY_MISMATCH`, logged, and staff are notified.
4. **Backend failure fails closed.** If the master cannot reach the backend,
   `validateQrWithBackend()` returns invalid. A crashed laptop does not
   become an open door.
5. **The portal never invents data.** Unknown device state is `NOT REPORTED`;
   a missing exit is "exit not recorded"; empty sensors say "No live sensor
   data"; simulated events never enter the database.

## Backend layout

```
backend/app/
├── api/routes/     thin HTTP layer: auth, labs, bookings, access (device API),
│                   admin (users, devices, assets, sessions, reports), issues,
│                   notifications, system
├── services/       the rules — booking, access, sessions, trace, issues,
│                   storage, notifications, devices
├── models/         SQLAlchemy tables and enums (see DATABASE.md)
├── schemas/        Pydantic request/response models
├── db/             engine, session, schema_check (refuses to run behind head)
└── ws/             authenticated live stream
```

Routes validate input and check the caller; services hold every rule so the
same rule applies whether the call came from the portal or a device.

### Authentication

- **People:** JWT bearer tokens (`/api/auth/login`), passwords hashed with bcrypt.
  Role is one of `STUDENT`, `LAB_STAFF`, `ADMIN`.
- **Devices:** the `X-Device-Key` header, compared in constant time against
  `DEVICE_API_KEY`. Devices identify themselves by `device_uid` and `LAB_ID`.
- **Live stream:** `/ws/activity?token=<jwt>` — the same JWT, same scoping.

### Scoping

A student sees their own bookings, sessions, issues and notifications only.
Anything else returns **404**, not 403, so existence is not disclosed. Staff
and administrators see everything; administrators additionally manage users
and settings and can close issues.

### Live updates

Writes publish to the WebSocket **after commit** (SQLAlchemy `after_commit`
hook), so a browser never sees an event that was rolled back. Messages are
role-scoped: a student receives only their own events and notifications.

### Schema guard

On start-up the API (and `seed.py`) compare the database's Alembic revision
with the code's head and refuse to run if the database is behind, printing
`alembic upgrade head`. This prevents half-created tables on a stale database.

## Frontend layout

```
frontend/src/
├── App.tsx              routes; staffOnly / adminOnly guards
├── components/          Layout (role navigation), ui kit, Trace (access steps,
│                        entry facts, event timeline), media (photo picker)
├── lib/                 api client, auth, live WebSocket, labels, time
└── pages/               one file per screen; dashboards/ per role; issues/
```

Every page has explicit loading, empty and error states. `e2e/navigation.mjs`
(every route for every role, back/forward, reloads, rapid clicking) and
`e2e/workflows.mjs` (booking → QR, issue with photo, simulation, phone width)
run in a real browser in CI.

## Storage

Issue photos go through a `Storage` interface (`services/storage.py`). The
only implementation today is `LocalStorage` (the `UPLOAD_DIR` directory, a
Docker volume in compose). An S3/MinIO implementation can replace it without
schema changes: rows store `storage_key` and `thumb_key`, never paths.

Every upload is decoded (not trusted by extension), rotated upright from
EXIF, stripped of all metadata including GPS, scaled, and thumbnailed.
Files are served only through authenticated routes to people allowed to see
the issue.

## Deployment shape

- `docker-compose.yml`: PostgreSQL, backend (runs migrations before serving),
  frontend (static build behind nginx), n8n (profile `automation`).
- Ollama runs natively on the laptop (for its GPU); the backend reaches it via
  `host.docker.internal`. `launch.bat` starts it and fetches missing models.
- Without Docker: `uvicorn` + `vite` as in the README.
- The face server runs on the laptop next to the door and keeps working when
  the portal is down.

## Accounts, door identities and the setup reminder

Sign-up (students) and admin-created accounts get the next `USERn`
(`services/identity.py`, never reused). `services/enrolment.py` tracks
whether that person's fingerprint and Face ID are registered - confirmed by
staff - and tells the person until they are (notification, banner, Profile
checklist). The door never reads these flags.

## AI assistants

Optional, read-only, beside the chain. Staff ask through tools that reuse the
analytics functions; students get a helper that sees only their own data.
Both use a short system guide (`services/ai_guide.py`). Free local models via
Ollama or Claude with a key - see [AI_ASSISTANT.md](AI_ASSISTANT.md).

## Automation and analytics

An optional layer beside the chain, never inside it; details in
[AUTOMATION.md](AUTOMATION.md).

```
change ─► same transaction: state + access_events + integration_events
                                                    │
               dispatcher thread ──(push)──► n8n webhooks
               n8n ──(X-Automation-Key)──► /api/automation/*  (rules live here)
               n8n ──► /notify, /alerts (idempotent on dedupe_key)
browser ─► /api/analytics/*  (Operations Center, lab twin, my usage)
```

n8n decides *when* and *where*; the backend decides *what*. Nothing reachable
from n8n can open or lock a door or cancel a booking.
