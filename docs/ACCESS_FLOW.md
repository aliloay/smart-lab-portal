# Access flow

From a booking to a person standing inside the laboratory, and what the
portal records at each step. Firmware and wiring details are in
[DOOR_SYSTEM.md](DOOR_SYSTEM.md).

## Who decides what

| Decision | Made by |
|---|---|
| Is this QR/card valid **here, now**, and whose is it? | backend |
| Does the fingerprint/face belong to **that** person? | master ESP32 (with the face server's result) |
| Unlock the door | master ESP32 — only after both steps agree |

The backend returns an identity or a refusal. It never returns "open", and
nothing it sends can drive the relay.

## Step by step

```
 student          portal/backend             ESP32-CAM + face server       master ESP32         door
    │  book  ────────►│ conflict check,             │                           │                │
    │                 │ CONFIRMED (or PENDING),     │                           │                │
    │                 │ issue SLB:… token           │                           │                │
    │ ◄──── QR ───────│                             │                           │                │
    │ ── show QR at the door ────────────────────►  │ decode QR                 │                │
    │                 │                             │ ── payload via /status ──►│                │
    │                 │ ◄──────────── POST /api/access/validate-qr (LAB_ID) ────│   STEP 1       │
    │                 │── valid + auth_subject ──────────────────────────────── ►│                │
    │                 │   (or valid=false + reason)                              │                │
    │ ── finger / face ──────────────────────────────────────────────────────► │   STEP 2       │
    │                 │                             │ face result ─────────────►│ compare with   │
    │                 │                             │                           │ step-1 identity│
    │                 │ ◄──────────── events: FACE_ACCEPTED, ACCESS_GRANTED ────│ ── relay ─────►│ unlocked
    │                 │ ◄──────────── DOOR_OPENED, DOOR_CLOSED ─────────────────│                │
```

### Step 1 — credential

`POST /api/access/validate-qr` (or `validate-rfid`), authenticated with
`X-Device-Key`. The backend checks, in this order, and stops at the first
failure, logging the named reason:

1. device known (`DEVICE_UNKNOWN`)
2. token exists (`TOKEN_UNKNOWN`)
3. token not revoked (`TOKEN_REVOKED`)
4. token belongs to **this** laboratory (`WRONG_LAB`)
5. booking not cancelled (`BOOKING_CANCELLED`) and confirmed (`BOOKING_NOT_CONFIRMED`)
6. user active (`USER_INACTIVE`)
7. now inside the window (`BOOKING_NOT_STARTED` / `BOOKING_EXPIRED`)

Success returns the user's `auth_subject` (e.g. `USER1`) — one identity. For
RFID the card must be known and active; if the lab sets
`require_booking_for_rfid`, an active booking is also required
(`NO_ACTIVE_BOOKING`).

### Step 2 — biometric

The master asks for a fingerprint (AS608) or a face (ESP32-CAM → face
server). The result is compared with the step-1 identity **on the master**.
A different person is `IDENTITY_MISMATCH`: logged, the door stays locked,
and staff get a critical notification.

### Grant, door, session

- `POST /api/access/grant` records `ACCESS_GRANTED`, opens an
  **access session**, and stamps the booking's `first_entry_at` (once) and
  `last_entry_at` (every entry).
- `DOOR_OPENED` / `DOOR_CLOSED` are recorded on the session. **They do not
  end it.** The door closing behind someone is part of the entry.
- `POST /api/access/deny` records `ACCESS_DENIED` with its reason and tells
  the person (de-duplicated to one notification per minute); security
  reasons also notify staff.

### How a session ends

| `end_reason` | Meaning | Shown as |
|---|---|---|
| `EXIT_RECORDED` | an exit was reported by a device | exit time and duration inside |
| `BOOKING_ENDED` | the booking window closed | "exit not recorded" |
| `DOOR_NOT_OPENED` | unlocked, relocked, never opened | "door not opened" |
| `SUPERSEDED` | the same person entered again | "superseded by a later entry" |
| `NO_EXIT_TIMEOUT` | card entry with no booking, no exit after `MAX_BOOKING_HOURS` | "exit not recorded" |

Duration inside is displayed **only** for `EXIT_RECORDED`. The current door
has no exit reader, so today most sessions honestly say the exit was not
recorded.

## Fail-closed behaviour

Every branch of `validateQrWithBackend()` in the master firmware:

| Failure | Result on the master |
|---|---|
| portal integration switched off (`BACKEND_ENABLED = false`) | booking QR refused (`BACKEND_DISABLED`) |
| no Wi-Fi | refused (`NO_NETWORK`) |
| backend unreachable, timeout, or any non-200 status | refused (`HTTP_<code>`) |
| reply does not positively contain `"valid":true` | refused, with the backend's reason |
| valid, but no `auth_subject` to bind step 2 to | refused |
| face server down | the face step cannot succeed; fingerprint remains the other step-2 option |

Legacy (non-`SLB:`) QR payloads and RFID with local authorisation keep working
offline, exactly as before the portal existed — that is the bench fallback.

## Where to see it in the portal

| Screen | What it shows |
|---|---|
| **Booking details** `/bookings/:id` | the credential, both steps with their identities, result, first entry vs. booked start, door cycle, all sessions of the booking |
| **Access session** `/sessions/:id` | one entry end to end: user, lab, booking, step 1 and step 2 with identities, result, entry, door opened/closed, exit **only if recorded**, duration only then; each event opens a detail drawer |
| **Access monitor** `/admin/access` | live event stream and sessions; any door event links to its session |
| **Laboratory** `/labs/:id` | controller state; `NOT REPORTED` for anything the device has not reported; last-known values marked as historical when the device is offline |

Students can open only their own bookings and sessions (others are a 404).

## Simulation

`/demo` (staff and admins) plays the same flow with invented events, entirely
in the browser: nothing is sent to the API and nothing is written to the
database, so simulated events can never mix with the real audit trail. See
[DEMO.md](DEMO.md).
