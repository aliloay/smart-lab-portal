---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/STATUS_OVERVIEW_2026-10-06.md"
source_hash: "90334858e7e32ce5abb68681f0b652d3bbcf36f9a6317673548e7d034fa51503"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/STATUS_OVERVIEW_2026-10-06.md` - edit the original in the repository, not this note.

Systems: none

# Smart Lab System Overview

As of 6 Oct 2026

The Intelligent IoT-Based Smart Research Laboratory runs end to end on a local network: door access, environment sensing and a security camera feed one portal with live monitoring, reports and an AI assistant. The door and environment node are validated on the bench; the camera runs against the portal and moves to the lab network next.

## How the parts connect

```
 Door (Master ESP32)          Environment node (ESP32)       Security camera (Mercusys MC210)
 RFID / QR -> fingerprint     DHT22, 2x PIR, 5-ch flame,     RTSP stream (local only)
 or face, lock relay,         MQ-2 gas                            |
 reed switch, buzzer, TFT          |                              v
   |        ESP32-CAM ---> Face server (laptop, port 5000) <-- Camera service (laptop, 127.0.0.1:5100)
   |                       YuNet + SFace templates              YOLOX people + equipment, tracking,
   v                                                            names by door + face, zones
 Portal backend (FastAPI + PostgreSQL, Docker) <-------------------+
   |  devices report with device keys; the backend never drives the lock
   v
 Website (React): staff and students, live over WebSocket; tablet at the door; phones on the LAN
 AI assistant: own agent (exact answers from records) + local model qwen2.5:3b (Ollama)
```

## Status by subsystem

| Subsystem | State | Verified by | Open |
| --- | --- | --- | --- |
| Door access (Master ESP32) | Hardware validated on the bench | Card, finger, face and QR entries; lock, buzzer, LEDs, tablet prompts | 12 V supply split; device key rotation (needs a reflash) |
| Environment node (LAB_01) | Live in the portal | All 5 sensor groups; flame and gas alarms reached the portal over the lab network | PIR false triggers; MQ-2 calibration |
| Security camera (MC210) | Live in the portal, home Wi-Fi | 1280x720 at ~20 fps; detection 3/s; face match USER1 cosine 0.72 vs 0.26 next person | Move to the lab network; test PC detection on real monitors |
| Portal + AI assistant | Running (Docker, laptop) | 365 backend tests, 24 camera tests, browser tests | Uncommitted changes; HTTPS needed for microphone features |
| Data | Restored and protected | 3 Oct backup merged; 183 events recovered from device logs | Automated nightly backups |

## Door access control

- Two-step entry: RFID card or booking QR code, then fingerprint or face (ESP32-CAM + laptop face server).
- Lock on the relay's normally-open contact, driven through a BC557 transistor from 3.3 V; locked by default on boot.
- Reed switch for door state; detects forced entry, door held open, identity mismatch, wrong finger or face.
- TFT shows the granted person's photo; the tablet page speaks prompts and plays alarms.
- Emergency modes set from the portal: hold open, lockdown, evacuation alarm. The Master ESP32 stays the final door authority.

## Environment monitoring

- DHT22 temperature/humidity, two PIR motion zones, a 5-channel flame board, MQ-2 smoke/gas (indicator, no ppm).
- Flame or smoke: full-screen red alarm with siren on every open portal page, EMERGENCY MODE and CLEAR.
- Heat or humidity above limits: orange advice to staff (ventilation, air conditioning); motion: silent blue note.
- Live green/red status per sensor; offline detection with one alert per outage.

## Security camera

- Detects and tracks people (YOLOX-S on the laptop CPU), keeps each name on the right person through crossings.
- Names come from the door entry and from the face server's enrolled faces: a face-named person shows "not entered" until the door confirms the entry; "verified" when door and face agree; a card-sharing alert when the face contradicts the badge.
- Equipment boxes per PC or robot: alerts when an item is moved, missing, or moves with nobody there; "Find PCs automatically" proposes a numbered box per monitor/laptop.
- Events with snapshots (deleted 30 days after staff check them); live wall of all labs, full screen, detection boxes on/off.
- The stream is never open on the network: the service listens on the laptop only and frames reach staff through the portal.

## Portal and AI assistant

- Bookings with QR codes; RFID, fingerprint and face enrolment; Access & audit log; Operations Center.
- Live monitor (wall screen): every lab's door, lock, occupancy, alarms, camera, and a Details window per lab.
- Maintenance tickets with photos, devices, equipment and inventory, smart bins, alerts, notifications, users and roles, emergency tab.
- Weekly and monthly reports with the previous period, coloured charts, repeated problems with recommendations; printable to PDF.
- AI assistant: the portal's own agent answers reports, any date range, door history and charts exactly from the records; the local model handles open questions and must state the period it checked.

## Data and verification

- Every door event, sensor reading, alert, booking and camera event is stored; the goal is the largest possible dataset for analysis and reports.
- On 5 Oct 2026 test runs wiped the live database; the 3 Oct backup was merged back (insert only) and 183 events were recovered from the door's and face server's logs. Tests now run only against a separate test database.
- Verification: 365 backend tests, 24 camera tests, browser tests for the monitor, camera wall, report link and chat charts.

## Next steps

1. Automated nightly database backups, keeping 30 days.
2. Move the camera to the lab network; test automatic PC detection on the real lab PCs.
3. Commit the current work; replace the default device key (door reflash after the 12 V split).
4. Emergency mode: adjustable siren volume, typed messages spoken by the tablets, alarms on phones; HTTPS for voice notes.
5. Camera analytics: PC usage per person and per PC, occupancy over the day, a door-area box for instant names.
6. Assistant: scheduled weekly PDF by email (n8n), per-person and per-PC questions, sensor trend charts.
7. Environment node: PIR tuning, MQ-2 calibration, escalation of unacknowledged alarms.

