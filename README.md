# Smart Laboratory Management Portal

[![CI](https://github.com/aliloay/smart-lab-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/aliloay/smart-lab-portal/actions/workflows/ci.yml)

Booking, time-bound QR credentials, and the audit trail for the physical
two-factor access-control system.

Bachelor thesis — *Design and Development of an Intelligent IoT-Based Smart
Research Laboratory Management System*, German International University, Cairo.

---

## The one thing to understand first

**The backend never opens a door.**

It answers one question — *whose booking is this, and is it valid here and
now?* — and returns an identity. The ESP32 master still requires a fingerprint
or a face that matches **that** identity before it drives the relay. No HTTP
request reaches the lock.

This is what makes the system safe to put on a network. A compromised portal
can refuse entry; it cannot grant it.

The corollary is equally deliberate: when the backend is unreachable, a
booking QR **fails closed**. A laboratory that requires a booking does not
become an open door because a laptop crashed.

---

## Architecture

```
  Student's phone                Laboratory door
  ┌──────────────┐               ┌─────────────────────────────────┐
  │  Portal      │               │  ESP32-CAM ──── JPEG ───┐       │
  │  /bookings/  │  shows QR     │   (QR + frames)         │       │
  │     :id/qr   │ ────────────► │                         ▼       │
  └──────────────┘               │              Face server (Flask)│
         ▲                       │              OpenCV LBPH        │
         │ books                 │                         │       │
         │                       │  Master ESP32 ◄──────────┘       │
  ┌──────┴───────┐               │   ├── RFID  (step 1)             │
  │  FastAPI     │◄──────────────┤   ├── QR    (step 1)             │
  │  PostgreSQL  │ validate-qr   │   ├── Finger(step 2)             │
  │              │──────────────►│   ├── Face  (step 2)             │
  └──────────────┘  identity     │   └── RELAY ◄── only the master  │
         │                       └─────────────────────────────────┘
         │ events
         ▼
   Admin dashboard (live WebSocket timeline)
```

Four services, deliberately separate:

| Service | Role | Runs on |
|---|---|---|
| **PostgreSQL** | bookings, credentials, audit trail | server / laptop |
| **FastAPI backend** | authorization and logging | server / laptop |
| **React frontend** | student and admin portal | browser |
| **Flask face server** | LBPH recognition (unchanged) | the laptop by the door |

The face server stays a separate process on purpose: it is proven, it is
latency-critical, and it must keep working if the portal is down.

---

## Quick start — Docker

```bash
cp .env.example .env          # then edit: set real secrets
docker compose up --build
```

- Portal: <http://localhost>
- API docs: <http://localhost:8000/api/docs>

Migrations run automatically before the API accepts traffic.

Seed the demo data once the stack is up:

```bash
docker compose exec backend python seed.py
```

## Quick start — without Docker

Needs Python 3.11+, Node 20+, PostgreSQL 14+.

```bash
# 1. database
createdb smartlab

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # edit DATABASE_URL
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

### Sign in

| Email | Password | Role |
|---|---|---|
| `admin@giu-uni.de` | `Admin#2026` | Administrator |
| `ali@giu-uni.de` | `Student#2026` | Student (`USER1`) |
| `ramy@giu-uni.de` | `Staff#2026` | Lab staff (`USER2`) |

**Change these before the system goes anywhere real.**

---

## The identity bridge

`users.auth_subject` is the join between this database and the embedded
system. It must be identical in three places:

| Where | What it is |
|---|---|
| `users.auth_subject` in PostgreSQL | `USER1` |
| `authorizedUsers[].name` in the master firmware | `"USER1"` |
| the label in `dataset/` on the face server | `USER1` |

If these drift, step 2 can never be matched against step 1 and every entry is
refused. That is the correct failure direction, but it is confusing to debug —
check this first if a valid booking is being denied.

---

## Complete flow: booking to door

1. Student logs in, picks a laboratory, date and time window, states a purpose.
2. Backend checks conflicts, confirms the booking, and issues an opaque token:
   `SLB:<22 random characters>`. It contains no name, lab or time — everything
   that decides validity is looked up server-side at the moment of the scan.
3. Student opens the QR page at the door.
4. ESP32-CAM captures a frame and POSTs it to the face server, which decodes
   the QR with `cv2.QRCodeDetector`.
5. Master polls the camera's `/status`, sees a payload starting with `SLB:`,
   and calls `POST /api/access/validate-qr` with its `LAB_ID`.
6. Backend checks: token exists, not revoked, booking confirmed and not
   cancelled, booking belongs to *this* laboratory, current time inside the
   window, user active. Any failure returns an explicit reason and is logged.
7. On success it returns `auth_subject` — **one** identity.
8. Master requires a fingerprint or face matching that identity. A mismatch is
   logged as `IDENTITY_MISMATCH` and the door stays shut.
9. Only then does the master drive the relay, and report `ACCESS_GRANTED`.
10. Door open and close events are reported as they happen. The admin timeline
    shows the whole sequence live.

---

## Security properties, and how each is enforced

| Property | Where it is enforced |
|---|---|
| A photographed QR is useless outside its window | `validate_qr` compares against the live booking every scan |
| A QR for one lab will not open another | token carries `lab_id`; checked before the time window |
| Cancelling kills the credential immediately | `cancel_booking` revokes the token, not just the booking |
| A stolen card plus the thief's face is refused | master compares the biometric to the step-1 identity |
| The backend cannot open a door | no endpoint touches the relay; the firmware never calls `setRelay()` from network code |
| A dead backend does not open doors | `validateQrWithBackend` returns invalid on any failure |
| Students cannot see each other's bookings | ownership check returns **404**, not 403 — existence is private |
| Passwords are never stored | bcrypt via passlib |
| No biometric material in the database | templates stay in the AS608; face images stay in `dataset/` |

Every one of these has a test. See below.

---

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

**54 tests, against real PostgreSQL** — not SQLite, because `TIMESTAMPTZ`
comparison is precisely what must not be tested on a different engine than
production runs.

Two suites:

- `test_authorization.py` — every non-negotiable rule: QR before / during /
  after its window, wrong lab, cancelled, unknown, revoked, inactive user,
  identity mismatch, booking conflicts, and role isolation between students.
- `test_qr_pipeline.py` — the hard requirement, below.

### End-to-end

With the API running:

```bash
python tests/e2e_booking_to_door.py
```

Drives the live API over HTTP as the real components do — student logs in and
books, the QR is decoded with **real OpenCV**, the master validates it with a
device key, biometrics are reported, and the audit trail is checked for all
ten expected event types. 30 assertions.

### The QR requirement is actually tested

The camera never sees the PNG. It sees a phone screen through an OV2640,
JPEG-compressed at quality 12, at VGA, slightly off-axis. So the tests push
the rendered credential through that whole chain and decode it with the same
`cv2.QRCodeDetector` the face server uses — across distance, tilt, JPEG
quality and lighting.

Two findings came out of building it, both worth reporting in the thesis:

**Token length is an optical decision, not a cryptographic one.**

| Token | Payload | QR version | Modules | px/module at 260px |
|---|---|---|---|---|
| 32 bytes | 47 chars | 5 | 45 | 5.78 |
| **16 bytes** | **26 chars** | **3** | **37** | **7.03** |

22% more pixels per module is the difference between reliable and intermittent
decoding. 128 bits of entropy is still overwhelming for a credential that
expires within hours — guessing one is not the threat model, photographing one
is, and that is handled by the time window.

**Moiré, not weak signal, causes isolated decode failures.** At particular
distances the QR's module grid beats against the sensor grid and that frame is
undecodable — *more* blur fixes it, because blur is an anti-alias filter. It
does not matter in operation because the camera analyzes ~4 frames a second
while the person moves. It matters for tests, which is why they measure a
success rate across distances rather than asserting one lucky frame.

Measured from an actual browser render at phone resolution: **28/28** across
seven distances × four degradation settings.

---

## Firmware

`firmware/SmartLab_Master_Portal/` is the master with portal integration.
The pre-portal sketch is untouched and remains the fallback.

Set these near the top:

```cpp
constexpr bool BACKEND_ENABLED = true;   // false = exactly the old behaviour
const char *BACKEND_IP   = "192.168.1.8";
const char *LAB_ID       = "LAB_01";     // must match labs.code
const char *DEVICE_ID    = "MASTER_LAB01";
const char *DEVICE_KEY   = "...";        // must match DEVICE_API_KEY
```

What changed, and nothing else:

- portal configuration block
- `validateQrWithBackend()` — fails closed on every error path
- `reportEvent()` / `sendHeartbeat()` — fire and forget, never block the door
- the `STATE_IDLE` QR branch now distinguishes `SLB:` tokens from legacy
  payloads; legacy still works locally so the bench demo survives the portal
  being off

What did **not** change, verified by diff: all 26 safety-critical constants
(pins, `RELAY_LOCKED_LEVEL = HIGH`, `DENY_ALERT_ENABLED = false`, freshness
windows, timeouts), and the relay write sites — still exactly two, both in the
state machine, neither reachable from network code.

---

## Known limitations — state these rather than hide them

1. **No liveness detection.** A printed photo authenticates as that person.
   Inherent to LBPH. Mitigated structurally: face is only the *second* factor,
   so an attacker needs the physical credential **and** a photo of that
   specific person.
2. **Recognition depends on the laptop.** By design — the classic ESP32 cannot
   run face recognition at usable speed.
3. **Sensor data is structure only.** `sensor_readings` exists and the lab page
   renders it, but nothing writes to it until a real sensor node is deployed.
   The UI shows "No data available" rather than inventing values.
4. **Denial buzzer disabled in firmware.** Energizing it sags the 12V rail
   enough to drop the relay. Fix is a 470–1000 µF capacitor across the rail;
   see `docs/DOOR_SYSTEM.md`.
5. **Development server.** `uvicorn` directly and Flask's dev server are fine
   for a laboratory on a private LAN. A public deployment wants a proper WSGI
   or ASGI server behind TLS.

---

## Repository layout

```
smart-lab-portal/
├── backend/          FastAPI, SQLAlchemy, Alembic, tests
│   ├── app/
│   │   ├── api/routes/    auth, labs, bookings, access (device), admin
│   │   ├── core/          config, security
│   │   ├── models/        16 tables
│   │   ├── services/      access, booking, events  ← the security lives here
│   │   └── ws/            live activity broadcast
│   ├── alembic/      migrations
│   └── tests/        54 unit + 30 end-to-end assertions
├── frontend/         React 18, TypeScript, Vite, Tailwind
├── firmware/         master (portal), camera, face server
├── docs/             door subsystem reference
└── docker-compose.yml
```
