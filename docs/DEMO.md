# Demonstration guide

A script for demonstrating the portal — to a thesis committee, a supervisor,
or anyone new to it — in about 15 minutes, with or without the door hardware.

## Three kinds of demo, kept apart

| Mode | What happens | Touches the database? |
|---|---|---|
| **Live** | real door hardware on `LAB_01` | yes — real audit history |
| **Simulation page** `/demo` | the access flow animated in the browser | **no** — nothing is sent to the API |
| **Scripted end-to-end** `tests/e2e_booking_to_door.py` | drives the running API as the devices would | yes — run it only against a QA database |

Simulated events never enter the real audit trail: the simulation page has
no API calls at all, and the scripted run must point at a separate database.

## Before the demo

Put the laptop, the phone(s) and both ESP32 boards on the same Wi-Fi or
phone hotspot. Then, on the laptop:

1. Double-click `launch.bat`. It starts Docker Desktop if needed, opens the
   face server in its own window, starts the portal and opens it in the
   browser. Note the address it prints, e.g. `http://192.168.1.8`.
2. If the network changed since the boards were flashed, set the camera's
   `SERVER_IP` and the master's `BACKEND_IP` to the printed address, and the
   master's `CAMERA_IP` to the address the camera prints on its Serial.
3. Open the printed address on the phone. Nothing to install.

Check: the top bar says **System healthy**; the access monitor shows the
master controller online if the hardware is powered.

Accounts (seed data — change before any real deployment):

| Role | Email | Password |
|---|---|---|
| Student | `ali@giu-uni.de` | `Student#2026` |
| Lab staff | `ramy@giu-uni.de` | `Staff#2026` |
| Administrator | `admin@giu-uni.de` | `Admin#2026` |

Tip: use two browser profiles (student in one, staff in the other) so both
views are visible side by side.

## The script

### 1. Student books a laboratory (3 min)

1. Sign in as the **student**. Point out the dashboard: next booking, recent
   access, notifications.
2. **Book a laboratory** → choose **LAB_01** (the one with door access) →
   today → an hour starting now → purpose → **Confirm booking**.
3. Other people's bookings are already shown as *reserved* — availability
   comes from everyone's bookings, without revealing whose.
4. **Open QR**. Say: *the code contains no name, lab or time — it is an
   opaque token looked up at the moment of the scan.*

### 2. At the door (3 min) — live, if the hardware is present

1. Show the QR to the ESP32-CAM. The master validates it with the portal:
   step 1 resolves to one identity.
2. Present the matching face or fingerprint: step 2. The relay unlocks.
3. On the staff screen, the **Access monitor** updates live: QR validated →
   face accepted → access granted → door opened → door closed.
4. Click **door opened** → **Open the access session**. Walk through the
   session page: user, lab, booking, step 1 and step 2 with the identities
   they matched, result, entry versus the booked start, the door cycle.
   Point out: *exit not recorded* — the door has no exit reader, so the
   portal does not pretend to know when someone left.

**The failure worth showing:** present the student's QR, then a *different*
person's face. `IDENTITY_MISMATCH`: the door stays shut, the event is logged,
and staff get a critical notification.

### 2b. Without hardware

Sign in as **staff** → **Access monitor** → **Simulation mode** (or open
`/demo`). The page carries a *SIMULATION* banner. Play, in order:

1. *QR + face → granted* — the full chain, node by node.
2. *Someone else's QR → denied* — the identity check on the master.
3. *QR at the wrong lab → denied* — the backend's lab check.
4. *Portal unreachable → fails closed* — the master refuses without the
   backend; a crashed laptop is not an open door.

Say clearly that these are illustrations: no event is created, no audit row
is written.

### 3. Something breaks (3 min)

1. As the **student**: **Report an issue** → *Malfunction* → LAB_01 → pick an
   instrument → *High* → title and description → add a photo from the phone
   → **Submit**. A ticket `ISS-2026-…` appears at once.
2. As **staff**: the bell shows the new report; the dashboard's
   maintenance queue lists it under *High*. Open it → **Acknowledge** →
   **Assign** to yourself → **In progress** → add an internal note (the
   student will not see it) → **Resolve** with notes.
3. Back as the **student**: the timeline shows every step; the notification
   says it was resolved. Internal notes are absent.
4. Open the instrument's page: the issue now appears in its maintenance
   history and lifecycle timeline. As staff, **Record inspection** and set
   the next maintenance date.

### 4. Administration (3 min)

Sign in as **admin**:

- **Overview** — live occupancy, today's bookings, device health, and the
  laboratory maintenance summary: open, critical, in progress, resolved this
  month, average resolution time, by laboratory, by category, most-reported
  item. Every figure is computed from real rows.
- **Reports** — CSV export of the audit trail.
- **Users** — roles and the `auth_subject` that binds a portal user to the
  firmware and face-server labels.
- **Laboratory page** — the controller panel shows `NOT REPORTED` for any
  state the device has not reported, and marks last-known values as
  historical when the device is offline. Sensors say **No live sensor data**.

## Scripted end-to-end run (no hardware, QA database only)

This writes a booking and door events. Never run it against the database
you are demonstrating from.

```bash
createdb smartlab_qa
cd backend
DATABASE_URL=postgresql+psycopg://postgres:<pw>@localhost:5432/smartlab_qa alembic upgrade head
DATABASE_URL=postgresql+psycopg://postgres:<pw>@localhost:5432/smartlab_qa python seed.py
DATABASE_URL=postgresql+psycopg://postgres:<pw>@localhost:5432/smartlab_qa \
  uvicorn app.main:app --port 8001

# another terminal
E2E_API=http://127.0.0.1:8001/api python tests/e2e_booking_to_door.py
# -> 30 passed, 0 failed

# the portal against the QA API
cd frontend && VITE_API_TARGET=http://127.0.0.1:8001 npx vite --port 5174
```

## Questions that come up

**"What if someone photographs the QR?"** It is useless outside that lab and
that window, and even inside it, it is only step 1 — step 2 must be the same
person.

**"What if the server is hacked?"** It can refuse entry; it cannot grant it.
No request reaches the relay.

**"Why no exit time?"** There is no exit reader. The device API already
accepts `EXIT_RECORDED`; an exit button or reader is the only thing that
will make duration inside appear, and the portal will not estimate it.

**"Is the face recognition spoofable?"** Yes, with a printed photo — LBPH has
no liveness detection. That is why face is only the *second* factor.
