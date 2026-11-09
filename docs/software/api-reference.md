# API reference

Generated on 9 Nov 2026 from the running backend's OpenAPI document (Smart Lab Portal 1.1.0): **329 operations on 306 paths**. The full machine-readable spec is [openapi.json](openapi.json); with the stack running, interactive docs are at http://127.0.0.1:8000/docs.

Authentication: portal users send a bearer token from `POST /api/auth/login`; ESP32 nodes and services send device or service keys (`DEVICE_API_KEY`, `AUTOMATION_API_KEY` from `.env`). Roles (student, staff, admin) are enforced per route in `backend/app/api/deps.py`.

## Groups

- [access (device)](#access-device) (7)
- [admin](#admin) (28)
- [ai](#ai) (3)
- [ai assistant](#ai-assistant) (12)
- [analytics](#analytics) (9)
- [auth](#auth) (10)
- [automation (n8n)](#automation-n8n) (22)
- [bookings](#bookings) (10)
- [device commands](#device-commands) (8)
- [emergency](#emergency) (10)
- [enrollment](#enrollment) (9)
- [equipment](#equipment) (41)
- [experiments](#experiments) (6)
- [face submissions](#face-submissions) (10)
- [incidents](#incidents) (4)
- [integration](#integration) (1)
- [inventory](#inventory) (6)
- [issues](#issues) (15)
- [labs](#labs) (14)
- [monitor](#monitor) (1)
- [notifications](#notifications) (5)
- [project knowledge (staff)](#project-knowledge-staff) (2)
- [reliability](#reliability) (15)
- [reports](#reports) (5)
- [reusable inventory](#reusable-inventory) (11)
- [robots](#robots) (16)
- [scan](#scan) (12)
- [search](#search) (2)
- [security camera](#security-camera) (24)
- [system](#system) (9)
- [workcell](#workcell) (2)

## access (device)

| Method | Path | Description |
|---|---|---|
| POST | `/api/access/deny` | Record Deny |
| POST | `/api/access/events` | Generic event sink for the master: biometric attempts, door transitions, |
| POST | `/api/access/grant` | The master reports that it HAS granted access. This opens an occupancy |
| POST | `/api/access/heartbeat` | Device liveness and door state. Auto-registers an unknown device against |
| POST | `/api/access/telemetry` | Environmental readings from a sensor node (temperature, humidity, and |
| POST | `/api/access/validate-qr` | Step 1 for a booking QR. |
| POST | `/api/access/validate-rfid` | Validate Rfid Endpoint |

## admin

| Method | Path | Description |
|---|---|---|
| GET | `/api/access-events` | The access timeline. |
| GET | `/api/access-events/export` | CSV of the audit trail, resolved to names rather than foreign keys, so it |
| GET | `/api/access-sessions` | Every occupancy session - entry, door cycle, and how it ended. |
| GET | `/api/access-sessions/lookup` | The session a moment belongs to: the latest session of this person in |
| GET | `/api/access-sessions/{session_id}` | One visit, end to end: the booking (if any), step 1 and its identity, |
| GET | `/api/alerts` | List Alerts |
| POST | `/api/alerts/{alert_id}/resolve` | Resolve Alert |
| GET | `/api/assets` | List Assets |
| POST | `/api/assets` | Create Asset |
| GET | `/api/assets/{asset_id}` | The equipment's record: where it is, who has it, when it was last |
| PATCH | `/api/assets/{asset_id}` | Update Asset |
| POST | `/api/assets/{asset_id}/checkout` | Checkout Asset |
| POST | `/api/assets/{asset_id}/inspect` | Record an inspection now, and optionally when the next one is due. |
| POST | `/api/assets/{asset_id}/return` | Return Asset |
| GET | `/api/devices` | Liveness is recomputed on read: a device that stops sending heartbeats |
| POST | `/api/devices` | Create Device |
| POST | `/api/devices/{device_id}/key` | Give one device its own key (shown once; only its hash is kept). A |
| DELETE | `/api/devices/{device_id}/key` | Revoke Device Key |
| GET | `/api/reports/access` | Daily grant/deny counts per lab. Real aggregates over real rows - if |
| GET | `/api/reports/overview` | Every aggregate the reports page draws, from real rows only. A section |
| GET | `/api/summary` | Summary |
| GET | `/api/users` | List Users |
| GET | `/api/users/next-auth-subject` | The door identity the next account would get (USERn = fingerprint slot n). |
| PATCH | `/api/users/{user_id}` | Update User |
| GET | `/api/users/{user_id}/access-setup` | User Access Setup |
| PUT | `/api/users/{user_id}/password` | Set someone's password: administrators for anyone, lab staff for |
| POST | `/api/users/{user_id}/remove` | Remove a person from use - their history stays (bookings, door entries, |
| POST | `/api/users/{user_id}/rfid` | Add Rfid |

## ai

| Method | Path | Description |
|---|---|---|
| POST | `/api/voice/speak` | Speak |
| GET | `/api/voice/status` | What the browser can use: local STT / TTS, or none (then the mic is hidden, answers use the browser voice). |
| POST | `/api/voice/transcribe` | Transcribe |

## ai assistant

| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/ask` | Ask |
| POST | `/api/ai/feedback` | Feedback |
| GET | `/api/ai/feedback/review` | Feedback Review |
| GET | `/api/ai/insights` | Insights |
| GET | `/api/ai/maintenance-priorities` | The official ranking. Deterministic - works without AI. |
| GET | `/api/ai/report` | Weekly or monthly management report (no AI needed): figures, the |
| GET | `/api/ai/status` | Status |
| POST | `/api/ai/student/ask` | Student Ask |
| GET | `/api/ai/student/status` | Student Status |
| POST | `/api/ai/summaries/{kind}` | Summary |
| GET | `/api/ai/tools` | The read-only lab tools with typed input schemas (what tools/mcp_server/server.py exposes over MCP). |
| POST | `/api/ai/tools/{name}` | One validated, audited, time-limited read-only tool call. Refusals and timeouts come back as status, not 500. |

## analytics

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/anomalies` | Rules, sensor-fault checks and statistical baselines on the real measurements (no ML - see ml_status). |
| POST | `/api/analytics/anomalies/raise` | Raise finding #index of the current scan as an incident (once per day per device/metric/kind). |
| GET | `/api/analytics/export.csv` | Recorded rows as CSV, for spreadsheets and the thesis appendix. |
| GET | `/api/analytics/kpis` | The shared KPI catalogue: id, definition, unit, source table, kind. |
| GET | `/api/analytics/labs/{lab_id}` | Typical week, recent days and environment. No per-person data. |
| GET | `/api/analytics/me` | The caller's own bookings only - never anyone else's. |
| GET | `/api/analytics/operations` | Operations |
| GET | `/api/analytics/system` | Every subsystem (door, environment, robots, consumables, cameras, PCs, automation, alerts): |
| GET | `/api/analytics/trends` | Trends |

## auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Me |
| GET | `/api/auth/me/access-setup` | What this person still needs before a lab door will open for them. |
| GET | `/api/auth/me/door-qr` | My Door Qr Status |
| POST | `/api/auth/me/door-qr` | Create My Door Qr |
| DELETE | `/api/auth/me/door-qr` | Revoke My Door Qr |
| POST | `/api/auth/register` | Admin-only: create an account with any role (student, lab staff, admin) |
| POST | `/api/auth/signup` | Self-service sign-up. Always creates a STUDENT. With |
| GET | `/api/auth/signup-config` | What the login page needs to show (or hide) the sign-up form. |
| GET | `/api/auth/username-suggestion` | firstname.lastname from a name (the sign-up and Add user forms pre-fill it). |

## automation (n8n)

| Method | Path | Description |
|---|---|---|
| GET | `/api/automation/access/denials` | Denials |
| GET | `/api/automation/ai/weekly-summary` | AI-written weekly summary for the n8n weekly report. Optional. |
| POST | `/api/automation/alerts` | Post Alert |
| GET | `/api/automation/anomalies` | Anomaly Scan |
| GET | `/api/automation/bookings/ended` | Ended |
| GET | `/api/automation/bookings/upcoming` | Upcoming |
| GET | `/api/automation/bookings/{booking_id}` | Booking |
| POST | `/api/automation/bookings/{booking_id}/remind` | The same reminder the portal raises itself - at most once per booking. |
| GET | `/api/automation/data-quality` | Quality |
| GET | `/api/automation/devices/offline` | Devices Offline |
| GET | `/api/automation/emergency/{lab_id}` | Workflow 23: a lab's emergency now, whether its door controller has |
| GET | `/api/automation/events` | Pull feed over the outbox, in commit order. Resume from `next_after`. |
| GET | `/api/automation/health` | Health |
| GET | `/api/automation/issues/{issue_id}` | Issue |
| GET | `/api/automation/maintenance` | Maintenance |
| GET | `/api/automation/maintenance/priorities` | Maintenance Ranked |
| POST | `/api/automation/notify` | Post Notify |
| GET | `/api/automation/reports/daily` | Report Daily |
| GET | `/api/automation/reports/weekly` | Report Weekly |
| GET | `/api/automation/robotics/{topic}` | Robotics Lab watch rules (n8n workflows 13-22): notification items. |
| POST | `/api/automation/runs` | A workflow reports that it ran - the Operations Center shows it. |
| GET | `/api/automation/sensors/evaluate` | Sensors |

## bookings

| Method | Path | Description |
|---|---|---|
| POST | `/api/bookings` | Create |
| GET | `/api/bookings` | List Bookings |
| GET | `/api/bookings/equipment-options` | What can be chosen for this lab and window (reserved items are marked). |
| GET | `/api/bookings/{booking_id}` | Get Booking |
| POST | `/api/bookings/{booking_id}/cancel` | Cancel |
| POST | `/api/bookings/{booking_id}/confirm` | Confirm |
| GET | `/api/bookings/{booking_id}/qr` | Render the booking's door credential. |
| POST | `/api/bookings/{booking_id}/reject` | Reject |
| GET | `/api/bookings/{booking_id}/sessions` | When this booking was ACTUALLY used. |
| GET | `/api/bookings/{booking_id}/trace` | One booking, end to end: the reservation, the credential, every step at |

## device commands

| Method | Path | Description |
|---|---|---|
| GET | `/api/access/commands/next` | The controller asks, while idle, whether a request is waiting for it. |
| POST | `/api/access/commands/{command_id}/progress` | Report Progress |
| GET | `/api/device-commands/{command_id}` | Command Status |
| POST | `/api/device-commands/{command_id}/cancel` | Cancel Command |
| POST | `/api/users/{user_id}/fingerprint/enroll` | Request Enrollment |
| GET | `/api/users/{user_id}/rfid` | The person's active cards (UIDs are identifiers, not secrets). |
| POST | `/api/users/{user_id}/rfid/enroll` | Request Card Enrollment |
| POST | `/api/users/{user_id}/rfid/remove` | Request Card Removal |

## emergency

| Method | Path | Description |
|---|---|---|
| GET | `/api/access/emergency` | Polled every second by the door controller. Read-mostly: it writes |
| GET | `/api/emergency/active` | Every signed-in user (any role): the labs with an emergency message or |
| POST | `/api/emergency/labs/{lab_id}` | Act |
| POST | `/api/emergency/labs/{lab_id}/normal` | Back To Normal |
| PUT | `/api/emergency/password` | Change Password |
| POST | `/api/emergency/pcs` | Pcs |
| POST | `/api/emergency/session` | Open Session |
| GET | `/api/emergency/status` | Status All |
| GET | `/api/insights/proactive` | Proactive suggestions (services/proactive.py): CONFIRMED findings and POSSIBLE anomalies with evidence and |
| GET | `/api/safety/triage` | Advisory safety triage (services/safety_triage.py): what to look at first, ranked, with evidence and ages. |

## enrollment

| Method | Path | Description |
|---|---|---|
| GET | `/api/enrollment/camera/snapshot` | One frame from the door camera, for the live preview while enrolling. First the frame the |
| GET | `/api/users/{user_id}/face` | Face Status |
| POST | `/api/users/{user_id}/face/auto` | Start automatic capture: the face server keeps every steady, sharp, new-looking frame of |
| GET | `/api/users/{user_id}/face/auto` | Face Auto Status |
| DELETE | `/api/users/{user_id}/face/auto` | Face Auto Stop |
| POST | `/api/users/{user_id}/face/capture` | The camera takes one frame and hands it to the face server as a sample. |
| POST | `/api/users/{user_id}/face/finish` | Retrain the face server with the new samples and mark Face ID done. |
| POST | `/api/users/{user_id}/face/reset` | Stop using this person's saved face samples (bad / few photos): the |
| POST | `/api/users/{user_id}/face/upload` | Face Upload |

## equipment

| Method | Path | Description |
|---|---|---|
| GET | `/api/equipment` | Robots + PCs with their current session. A fixed number of queries whatever the number of devices |
| GET | `/api/equipment/aas.json` | Asset Administration Shell (V3.0 JSON) of every registered asset - read-only export (app/services/aas.py). |
| POST | `/api/equipment/broadcast/frame` | A frame captured in the presenting admin's browser. |
| GET | `/api/equipment/broadcast/frame.jpg` | Latest presented frame for anyone signed in (students watch on /share); 204 = none yet, |
| POST | `/api/equipment/broadcast/start` | Admin shares their screen with the students' PCs (and anyone signed in on /share). |
| GET | `/api/equipment/broadcast/status` | Broadcast Status |
| POST | `/api/equipment/broadcast/stop` | Broadcast Stop |
| GET | `/api/equipment/broadcast/watch/frame.jpg` | Broadcast Watch Frame |
| GET | `/api/equipment/broadcast/watch/status` | Broadcast Watch Status |
| GET | `/api/equipment/master` | Who the master is now: the admin who signed in last, their device, and their lab PC (if any). |
| POST | `/api/equipment/master/claim` | Called by the web app right after an admin signs in. The admin becomes the master; the lab PC |
| GET | `/api/equipment/master/nonce` | Master Nonce |
| POST | `/api/equipment/pc/action-result` | Pc Action Result |
| GET | `/api/equipment/pc/agent-bundle` | The signed agent update (tools/pc_agent/make_bundle.py). Public code, no secrets: the signature, checked on |
| POST | `/api/equipment/pc/broadcast-frame` | A frame from the PC that presents: the admin's master PC, or a student's PC an admin accepted. |
| POST | `/api/equipment/pc/enroll` | First start of the agent from the flash-drive kit: the kit's enrollment code -> this PC's own key. The same |
| POST | `/api/equipment/pc/frame` | One JPEG of the PC's screen, accepted only while staff are watching. |
| GET | `/api/equipment/pc/lan-targets` | For tools/lan_presence: every lab PC whose agent has reported its MAC address(es), so a new PC |
| GET | `/api/equipment/pc/poll` | The PC agent asks every ~2 s: mode, whether staff are watching, and |
| POST | `/api/equipment/pc/presence` | tools/lan_presence (on the lab laptop): which lab PCs answer on the LAN right now, by MAC |
| GET | `/api/equipment/pc/wait` | The idle PC agent waits here instead of polling every second: answers {"changed": true} as soon |
| GET | `/api/equipment/pc/watch-token` | Pc Watch Token |
| GET | `/api/equipment/share-requests` | Share List |
| POST | `/api/equipment/share-requests` | A student asks to share their lab PC's screen. Only a PC whose agent proves itself can present |
| GET | `/api/equipment/share-requests/mine` | Share Mine |
| POST | `/api/equipment/share-requests/mine/stop` | The presenting student ends their own share. |
| GET | `/api/equipment/share-requests/nonce` | One-time nonce for the PC proof (as at the admin's sign-in): which lab PC the student sits at. |
| POST | `/api/equipment/share-requests/{req_id}` | Share Decide |
| POST | `/api/equipment/state` | Report State |
| POST | `/api/equipment/violations` | Report Violation |
| GET | `/api/equipment/violations` | List Violations |
| POST | `/api/equipment/{device_id}/action` | Pc Action |
| GET | `/api/equipment/{device_id}/actions` | Pc Actions |
| PUT | `/api/equipment/{device_id}/master` | Mark (or unmark) a PC as the lab engineer's master PC. |
| POST | `/api/equipment/{device_id}/message` | Send Message |
| POST | `/api/equipment/{device_id}/message/clear` | Close the messages open on this PC and cancel one not delivered yet. |
| PUT | `/api/equipment/{device_id}/mode` | Set Mode |
| GET | `/api/equipment/{device_id}/screen.jpg` | Latest frame, or 204 while the agent has not sent one yet. |
| POST | `/api/equipment/{device_id}/screen/start` | Screen Start |
| POST | `/api/equipment/{device_id}/screen/stop` | Screen Stop |
| GET | `/api/equipment/{device_id}/sessions` | Sessions |

## experiments

| Method | Path | Description |
|---|---|---|
| GET | `/api/experiments` | All experiments, or one lab's: those run on a device of that lab |
| POST | `/api/experiments` | Create |
| GET | `/api/experiments/{exp_id}` | Detail |
| POST | `/api/experiments/{exp_id}/start` | Start |
| POST | `/api/experiments/{exp_id}/stop` | Stop |
| POST | `/api/experiments/{exp_id}/trials` | Add Trial |

## face submissions

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/me/face-submission` | My Submission |
| POST | `/api/auth/me/face-submission` | Submit Photos |
| POST | `/api/auth/me/face-submission/withdraw` | Withdraw |
| GET | `/api/face-submissions` | Every submission waiting for review, oldest first (Users & roles). |
| POST | `/api/face-submissions/{sid}/approve` | Approve |
| GET | `/api/face-submissions/{sid}/photos/{n}` | The person or staff only; never public - these are photos of a face. |
| POST | `/api/face-submissions/{sid}/reject` | Refused: the person must come to the lab staff to be enrolled in person. |
| POST | `/api/face-submissions/{sid}/retake` | Not usable as they are: the person is asked to send new photos. |
| POST | `/api/face-submissions/{sid}/review` | Review Photos |
| GET | `/api/users/{user_id}/face/submission` | Pending For User |

## incidents

| Method | Path | Description |
|---|---|---|
| GET | `/api/incidents` | List Incidents |
| GET | `/api/incidents/quality` | Alert quality: grouped share, repeat rows, noisy devices and conditions, time to acknowledge / |
| GET | `/api/incidents/{incident_id}` | Get Incident |
| POST | `/api/incidents/{incident_id}/actions` | Act |

## integration

| Method | Path | Description |
|---|---|---|
| GET | `/api/opcua/snapshot` | Snapshot |

## inventory

| Method | Path | Description |
|---|---|---|
| GET | `/api/inventory/bins` | List Bins |
| POST | `/api/inventory/bins` | Create Bin |
| PATCH | `/api/inventory/bins/{bin_id}` | Update Bin |
| POST | `/api/inventory/bins/{bin_id}/count` | A physical count next to the current estimate: estimation error data. |
| GET | `/api/inventory/bins/{bin_id}/history` | Bin History |
| POST | `/api/inventory/measurements` | Stable masses from a bin node. Replies with what the LCD shows. |

## issues

| Method | Path | Description |
|---|---|---|
| POST | `/api/issues` | Create Issue |
| GET | `/api/issues` | List Issues |
| GET | `/api/issues/summary` | Issue Summary |
| GET | `/api/issues/{issue_id}` | Get Issue |
| PATCH | `/api/issues/{issue_id}` | Update Issue |
| POST | `/api/issues/{issue_id}/acknowledge` | Acknowledge |
| POST | `/api/issues/{issue_id}/assign` | Assign |
| POST | `/api/issues/{issue_id}/close` | Close |
| POST | `/api/issues/{issue_id}/comments` | Add Comment |
| POST | `/api/issues/{issue_id}/photos` | Upload Photos |
| GET | `/api/issues/{issue_id}/photos` | List Photos |
| GET | `/api/issues/{issue_id}/photos/{photo_id}/file` | Streams the stored image. Authenticated like every other route: the |
| POST | `/api/issues/{issue_id}/reopen` | Reopen |
| POST | `/api/issues/{issue_id}/resolve` | Resolve |
| POST | `/api/issues/{issue_id}/status` | Change Status |

## labs

| Method | Path | Description |
|---|---|---|
| GET | `/api/labs` | List Labs |
| POST | `/api/labs` | Create Lab |
| GET | `/api/labs/environment/all` | Every lab that has an environment node, in one request: the overview |
| GET | `/api/labs/hazards/active` | Smoke / flame alarms still open in any lab, and evacuation alarms switched |
| GET | `/api/labs/headcount` | ADVISORY emergency headcount (priority N): who the DOOR record says is inside (named, from badge/finger/QR |
| GET | `/api/labs/health` | Lab Health Score per lab (app/services/health_score.py): 0-100 + every part with its evidence; parts with no |
| GET | `/api/labs/overview` | Everything the laboratory catalogue shows, in one request, computed from |
| GET | `/api/labs/{lab_id}` | Lab Detail |
| GET | `/api/labs/{lab_id}/activity` | The lab's event timeline. Staff see all of it; a student sees only their |
| GET | `/api/labs/{lab_id}/at` | Whole-lab time slider: the lab at time t, rebuilt from recorded history only (services/lab_at.py). |
| GET | `/api/labs/{lab_id}/availability` | Reserved intervals in [start, end), for the booking picker. |
| GET | `/api/labs/{lab_id}/environment` | Latest environment reading per metric, each with its quality |
| GET | `/api/labs/{lab_id}/issues` | Open problems in a lab: titles and states, never who reported them. |
| GET | `/api/labs/{lab_id}/sensors` | Returns whatever real readings exist - which is an empty list until a |

## monitor

| Method | Path | Description |
|---|---|---|
| GET | `/api/monitor` | Wall Screen |

## notifications

| Method | Path | Description |
|---|---|---|
| GET | `/api/notifications` | List Notifications |
| GET | `/api/notifications/inbox` | The Notifications page: one page of the caller's notifications with |
| POST | `/api/notifications/read-all` | Mark All Read |
| GET | `/api/notifications/unread-count` | Unread Count |
| POST | `/api/notifications/{notification_id}/read` | Mark Read |

## project knowledge (staff)

| Method | Path | Description |
|---|---|---|
| POST | `/api/knowledge/ask` | Streams the agent's events (NDJSON): meta, step, sources, token, done. |
| GET | `/api/knowledge/status` | Knowledge Status |

## reliability

| Method | Path | Description |
|---|---|---|
| GET | `/api/reliability/alert-quality` | Alert Quality |
| GET | `/api/reliability/backups` | Backups |
| GET | `/api/reliability/briefing` | Get Briefing |
| GET | `/api/reliability/capacity` | Capacity |
| POST | `/api/reliability/diagnose` | Re-run the read-only health checks now (policy: health.recheck = allowed). Bounded by their timeouts. |
| GET | `/api/reliability/drift` | Drift Check |
| POST | `/api/reliability/drift/accept` | Accept a deviation with a reason and an optional expiry. It stays visible; the baseline is not changed. |
| GET | `/api/reliability/evaluation` | The thesis evaluation (priority B): measured before/after results with their conditions and the script or |
| GET | `/api/reliability/graph` | Graph |
| POST | `/api/reliability/graph/whatif` | SIMULATION only: the consequences of `node` failing now. Nothing is changed. |
| GET | `/api/reliability/incidents/{incident_id}/investigate` | Investigate Incident |
| GET | `/api/reliability/performance` | Performance |
| POST | `/api/reliability/performance/baseline` | Capture Baseline |
| GET | `/api/reliability/policy` | Policy Table |
| POST | `/api/reliability/policy/evaluate` | Policy Evaluate |

## reports

| Method | Path | Description |
|---|---|---|
| GET | `/api/reports-center` | Catalogue |
| GET | `/api/reports-center/asset-lifecycle` | Asset Lifecycle |
| GET | `/api/reports-center/inventory-discrepancies` | Inventory Discrepancies |
| GET | `/api/reports-center/timeline` | Timeline |
| GET | `/api/reports-center/{kind}` | Report |

## reusable inventory

| Method | Path | Description |
|---|---|---|
| PUT | `/api/reusable/assets/{asset_id}/mass` | The item's mass for the bin's weight check (None = learn it again). |
| PUT | `/api/reusable/assets/{asset_id}/tag` | Assign Tag |
| POST | `/api/reusable/checkout` | Request Checkout |
| POST | `/api/reusable/checkout-complete` | After OPEN_LID for a checkout: the bin weighed before and after. |
| POST | `/api/reusable/complete` | After OPEN_FOR_RETURN: the lid cycle finished. The return is recorded |
| GET | `/api/reusable/items` | Tagged items of a lab's smart bin. Who holds an item: staff see the |
| GET | `/api/reusable/last-unknown` | The most recent tag a bin node scanned that no item has. |
| POST | `/api/reusable/scan` | A tag at the bin. Replies with what the node does and shows. |
| POST | `/api/reusable/staff-checkout` | Staff take an item out of the bin FOR a person (e.g. their booking has |
| POST | `/api/reusable/staff-return` | Staff record that a checked-out item is back (it came back without the |
| POST | `/api/reusable/weight-change` | A settled weight change with no request running: nobody explained it. |

## robots

| Method | Path | Description |
|---|---|---|
| GET | `/api/robots` | Robots |
| POST | `/api/robots/events` | Events |
| GET | `/api/robots/stop-relay/poll` | The stop-relay ESP32 asks every 200 ms. Only that device's OWN key (not the shared door key). |
| POST | `/api/robots/telemetry` | Telemetry |
| GET | `/api/robots/{device_id}` | Robot |
| GET | `/api/robots/{device_id}/control` | Control Status |
| POST | `/api/robots/{device_id}/control/auto-home/cancel` | Any staff member cancels the automatic Home countdown (the idle clock restarts). Sends nothing to a robot. |
| POST | `/api/robots/{device_id}/control/command` | Control Command |
| POST | `/api/robots/{device_id}/control/recover` | Deliberate recovery after STOP (administrator, arm reported still). Restarts nothing. |
| POST | `/api/robots/{device_id}/control/release` | Control Release |
| POST | `/api/robots/{device_id}/control/request` | Control Request |
| POST | `/api/robots/{device_id}/control/stop` | Global STOP: any staff member, no ownership needed, whoever started the motion. Latches |
| GET | `/api/robots/{device_id}/events` | Robot Events |
| POST | `/api/robots/{device_id}/home` | HOME = the pose the robot is in NOW (the engineer put it there). Needs |
| GET | `/api/robots/{device_id}/movements` | Recent completed movements that carry their recorded path (3D replay). |
| GET | `/api/robots/{device_id}/movements/{event_id}` | One movement's recorded joint path: t (s from its start) and q (rad, J1..J6). |

## scan

| Method | Path | Description |
|---|---|---|
| POST | `/api/scan/appearance` | One phone frame -> which enclosure it LOOKS like (PROBABLE / AMBIGUOUS / UNKNOWN). A hint only: identity and |
| GET | `/api/scan/appearance/refs` | Which registered enclosures have reference photos yet (data/asset_refs/manifest.json). |
| POST | `/api/scan/ask` | One target-aware question from the live camera (typed or spoken). The target is resolved on the server |
| GET | `/api/scan/asset` | Asset |
| POST | `/api/scan/identify` | Identify |
| GET | `/api/scan/link.png` | QR of a portal address (desktop -> phone handoff). https:// portal paths only - not a general QR maker. |
| GET | `/api/scan/marker.png` | The printable marker of a registered asset (exact text = its record key). style=pack (default): the owner's |
| GET | `/api/scan/marker.svg` | Vector QR of a registered asset (responsive previews; the PNG card is for printing). |
| GET | `/api/scan/markers.json` | All markers of one kind for the markers page in one response (registry read once, artwork cached). |
| GET | `/api/scan/markers.pdf` | Every marker of one kind on A4 sheets (the pack's 2 x 4 card layout, 300 dpi). |
| POST | `/api/scan/people` | Person boxes for one phone frame. The camera service answers 429 while it is busy with another phone frame |
| GET | `/api/scan/registry` | Registry |

## search

| Method | Path | Description |
|---|---|---|
| GET | `/api/search` | Search |
| GET | `/api/search/index` | Everything the palette can find, with the words that make it relevant. `keys` = what the item |

## security camera

| Method | Path | Description |
|---|---|---|
| GET | `/api/security/cameras` | Cameras |
| GET | `/api/security/cameras/{device_id}/dataset` | Training pictures for the robot detector, kept on the laptop. |
| POST | `/api/security/cameras/{device_id}/dataset/{action}` | Dataset Switch |
| GET | `/api/security/cameras/{device_id}/frame.jpg` | The latest frame (annotated, or raw for drawing boxes). 204 = none. |
| GET | `/api/security/cameras/{device_id}/identity` | Why each person in view has (or has not) a name: state, confidence and |
| GET | `/api/security/cameras/{device_id}/recording` | Recording Status |
| POST | `/api/security/cameras/{device_id}/recording/{action}` | Recording Switch |
| GET | `/api/security/cameras/{device_id}/recordings` | Recordings |
| POST | `/api/security/cameras/{device_id}/recordings/{name}/delete` | Recording Delete |
| POST | `/api/security/cameras/{device_id}/recordings/{name}/link` | A link to play / download one recording, valid for 10 minutes. |
| GET | `/api/security/cameras/{device_id}/suggestions` | Equipment the detector finds in the picture now (monitors, laptops) as |
| GET | `/api/security/cameras/{device_id}/zones` | List Zones |
| POST | `/api/security/cameras/{device_id}/zones` | Add Zone |
| PUT | `/api/security/cameras/{device_id}/zones/{zone_id}` | Update Zone |
| DELETE | `/api/security/cameras/{device_id}/zones/{zone_id}` | Delete Zone |
| POST | `/api/security/cameras/{device_id}/zones/{zone_id}/accept` | The item's new position/look is fine: the camera relearns it. |
| GET | `/api/security/config` | Config |
| POST | `/api/security/events` | Report Event |
| GET | `/api/security/events` | Events |
| POST | `/api/security/events/{event_id}/ack` | Acknowledge |
| GET | `/api/security/events/{event_id}/snapshot.jpg` | Event Snapshot |
| GET | `/api/security/recordings/play` | Streams one recording (with Range, so the player can seek). The signed |
| POST | `/api/security/state` | Report State |
| POST | `/api/security/zones/realign` | The camera matched its moved view to the room and reports where each |

## system

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Unauthenticated liveness probe for Docker. Reveals nothing sensitive. |
| GET | `/api/system/config` | Read-only: configuration comes from the environment, not the browser. |
| GET | `/api/system/data-mode` | The provenance new records get (a RUNNING experiment overrides it). |
| PUT | `/api/system/data-mode` | Administrators only. Affects NEW records only - history keeps its provenance. |
| GET | `/api/system/health` | The System Health page: services + devices, data-source freshness, backups, a summary. |
| GET | `/api/system/services` | Every part of the lab system. Network services come from the background monitor's cache |
| GET | `/api/system/status` | System Status |
| POST | `/api/uiperf/report` | Report |
| GET | `/api/uiperf/reports` | Reports |

## workcell

| Method | Path | Description |
|---|---|---|
| GET | `/api/workcell/{robot_key}` | Newest version of each named setup. |
| PUT | `/api/workcell/{robot_key}/{name}` | Save |
