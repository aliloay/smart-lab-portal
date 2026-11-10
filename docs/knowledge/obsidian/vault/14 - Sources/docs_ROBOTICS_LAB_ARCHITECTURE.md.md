---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/ROBOTICS_LAB_ARCHITECTURE.md"
source_hash: "fe358535383aecafbf7e7741398ec17f7b67e3a932137fba73ed73eeac810616"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/ROBOTICS_LAB_ARCHITECTURE.md` - edit the original in the repository, not this note.

Systems: [[Backend and data]], [[Robots (read-only)]]

## Related
- [[tools_security_vision_README.md]] - mentioned by docs
- [[firmware_SmartLab_Consumable_Bin_README.md]] - mentioned by docs
- [[firmware_SmartLab_Consumable_Bin_SmartLab_Consumable_Bin.ino]] - mentioned by docs
- [[firmware_SmartLab_Reusable_Bin_README.md]] - mentioned by docs

# Smart Robotics Laboratory — architecture audit and design

**Status: DESIGN.** Nothing in this document is implemented in hardware yet.
Written 2026-10-02 from an inspection of the code in this repository. Every
hardware value marked *to verify* must be measured or read from the actual
module or datasheet before it is used; none is invented here. Results go in
the thesis only after the matching test in §X has been run.

Scope: extend the working Smart Lab platform into one real Robotics
Laboratory (`LAB_01`, *Robotics & Industrial Automation Laboratory* in the
database) with four systems, numbered as the project owner numbers them:

| # | System | Hardware |
|---|---|---|
| 1 | Physical environment (temperature, humidity, smoke/gas, flame, leak, motion, emergency) | ESP32 #1 |
| 2 | Non-consumables: robots (UR5e, FANUC) and lab PCs, with the admin's **master PC** | no ESP32 — Ethernet / LAN |
| 3 | Consumables (resistors, capacitors) on load cells | ESP32 #2 |
| 4 | Reusables (Arduinos, breadboards, microcontrollers) in the NFC smart bin with LCD | ESP32 #3 |

The door/access-control station stays a separate subsystem and the master
ESP32 stays the final authority for the door.

---

## A. Current system state (inspected)

| Area | What exists today | Reuse for the Robotics Lab |
|---|---|---|
| Door station | Master ESP32 (PN532 I2C 0x24 on GPIO19/18, AS608 fingerprint UART 16/17, ST7735, relay GPIO26, MC-38 reed GPIO27, LEDs/buzzer), ESP32-CAM (QR + face), tablet view at `.151` | Unchanged. Its patterns are reused: device key, heartbeat, background network task, fixed IP |
| Network | Offline router `Smart_Lab` (192.168.1.x); laptop .200, camera .150, master .151; `launch.bat` runs offline | Same LAN; new nodes get fixed IPs (§H) |
| Backend | FastAPI, 15 route modules, PostgreSQL via Alembic, WebSocket live channel, device key auth | All new APIs live here; no second backend |
| Device model | `devices` (uid, type, lab, ip, firmware, last_seen, `component_state` JSON), `DeviceType` = MASTER_CONTROLLER, CAMERA, FACE_SERVER, **SENSOR_NODE** | Environment/inventory nodes register through the existing heartbeat |
| Telemetry | `POST /api/access/telemetry` → `sensor_readings` (metric, value, unit, **server UTC timestamp**); thresholds `SENSOR_THRESHOLDS`; `/automation/sensors/evaluate` marks stale/high/low | System 2 needs no new table |
| Assets | `assets` (tag, category, lab, status AVAILABLE/CHECKED_OUT/MAINTENANCE/RETIRED, holder, maintenance dates) + `asset_transactions`; checkout/return endpoints | Reusable inventory and equipment identity |
| Commands | `device_commands` (new): portal request → device fetches while idle → reports steps | Reusable-bin lid opening, admin door request |
| Alerts | `alerts` with `dedupe_key`, notifications, live push | Environment hazards, inventory, equipment |
| Readiness | `lab_readiness()` (controller, issues, alerts, maintenance) used by n8n 09 and the AI | Extend with environment, equipment, inventory |
| n8n | 12 workflows (booking, denial intelligence, offline escalation, maintenance, daily/weekly report, **sensor thresholds**, **pre-booking check**, post-session, data quality, anomaly) | Workflows 13+ build on the same `/automation` API |
| AI | Read-only tools: list_labs, operations overview, readiness, trends, anomalies, maintenance priorities, open issues, reports | New read-only tools (§U) |
| Website | Labs, lab detail, bookings, access monitor, devices, equipment, alerts, reports, operations, users, **live monitor wall screen** | Extend, no new site |

## B. Four-system Robotics Lab architecture

Numbering follows the thesis: **System 1** core robotics, PCs and LAN; **System 2**
physical environment; **System 3** consumables; **System 4** reusables. The door
is a separate, protected subsystem.

```
                              ROBOTICS LAB (LAB_01)
 ┌────────────┬──────────────┬───────────────┬───────────────┬────────────────────┐
 │ DOOR       │ 2 ENVIRON-   │ 3 CONSUMABLES │ 4 REUSABLES   │ 1 ROBOTS & PCs     │
 │ (exists)   │   MENT       │   ESP32 #2    │   ESP32 #3    │   no ESP32         │
 │ access only│   ESP32 #1   │   weigh only  │   NFC + lid   │   UR5e · FANUC     │
 │            │   sense only │               │   + LCD       │   PC-01 · PC-02    │
 └─────┬──────┴──────┬───────┴───────┬───────┴───────┬───────┴─────────┬──────────┘
       │ Wi-Fi       │ Wi-Fi         │ Wi-Fi         │ Wi-Fi           │ Ethernet to the
       └─────────────┴──── router `Smart_Lab` ───────┴─────────────────┘ router's LAN ports
                                   │                                     (switch only if
                         laptop (server: FastAPI, DB, n8n, AI, vision)    ports run out)
                         admin master PC (portal: lock / view / message lab PCs)
```

Each ESP32 has one responsibility and never actuates anything outside it.
Robots and PCs talk to the laptop over the LAN, not through an ESP32. The
robots are wired **directly to the router's LAN ports**; an unmanaged switch
is added only if the router runs out of ports. Whether the PCs are wired or
on Wi-Fi is still open — the agent works the same either way.

## C. Door architecture (unchanged)

Step 1 RFID/NFC or booking QR → step 2 fingerprint or face, identities must
match → master unlocks. The website, backend, n8n and AI never drive the
relay. A future admin "open door" uses `device_commands`: authenticated,
RBAC-checked, audited, time-limited request; the master fetches it, checks
it is idle and the request is fresh, and decides.

## D. Existing hardware (as stated by the project owner; not re-measured)

ESP32 dev boards ×3, 1 kg straight-bar load cells ×2, HX711 ×2 (+ acrylic
mounts), DHT22 ×1, MQ-2 ×1, 5-channel flame sensor ×1, HC-SR501 PIR ×2,
XL4016 buck converters ×3, 16×2 I2C LCD ×2, MG90S servo ×1, 2×14 mm NO reed
switch ×1, NTAG213 stickers, PN532 (one more needed for #3 — *to confirm
how many PN532 are on hand*), 12 V 10 A PSU, WAGO-type 2-in/8-out
distribution block, 6×30 mm inline fuse holders, 3 W 8 Ω speaker + PAM8403.

## E. Existing software reused (summary)

Device key + heartbeat auto-registration, telemetry endpoint, sensor
thresholds, alerts with dedupe, readiness, device commands, live WebSocket,
assets/transactions, audit log, n8n API, AI tool framework, live monitor.

## F. Database — what changes and why

Rule: extend existing tables; add a table only for a concept nothing holds.

| Need | Decision |
|---|---|
| Environment readings | **Reuse `sensor_readings`** (metric/value/unit, server time). No change. |
| Environment node identity | **Reuse `devices`** (type SENSOR_NODE). |
| Per-device credentials | **Add** `devices.key_hash` (nullable). Today every device shares one `DEVICE_API_KEY`; §39 asks for unique device authentication. Shared key stays accepted during the transition. |
| Reusable asset NFC id | **Add** `assets.nfc_uid` (unique, nullable). |
| Reusable transactions | **Extend** `asset_transactions` with `booking_id`, `device_id`, `source` (PORTAL / BIN / STAFF). |
| Consumable bins | **New** `inventory_bins` (lab, device, code, item name, unit mass, tare, reorder threshold, calibration date). |
| Bin measurements | **New** `inventory_measurements` (bin, mass_g, estimated_qty, stable flag, recorded_at) — `sensor_readings` cannot say *which bin* cleanly. |
| Withdrawals/refills | **New** `inventory_transactions` (bin, Δmass, Δqty estimate, kind, user/booking if attributable). |
| Booked resources | **New** `booking_resources` (booking, asset *or* bin, quantity requested) → BOOKED/RESERVED; ISSUED/RETURNED come from transactions. |
| Robot / PC sessions | **New** `equipment_sessions` (asset, state RUNNING/IDLE/FAULT, user, booking, start, end). Numeric robot/PC telemetry → `sensor_readings` with an asset-linked device. |
| PC exam mode | **New** `exam_sessions`, `policy_violations` (Phase 7, later). |
| Device types | **Extend** `DeviceType`: INVENTORY_NODE, ROBOT, PC (VARCHAR + CHECK, no native enum migration pain). |

All migrations additive; each one checked with `alembic upgrade` +
`alembic check` on a scratch database before it ships.

## G. Power architecture (low voltage)

```
230 V AC ──(enclosed, fused at the PSU)── 12 V 10 A PSU
  12 V ── distribution (+12 V group) ──┬─ fuse ─ XL4016 → 5.00 V → Environment ESP32 + sensors
                                       ├─ fuse ─ XL4016 → 5.00 V → Consumable ESP32 + HX711 + LCD
                                       ├─ fuse ─ XL4016 → 5.00 V → Reusable ESP32 + PN532 + LCD + servo
                                       └─ fuse ─ existing door buck
  GND ── distribution (GND group) ─────┴─ common ground to every branch
```

- Fuses on **+12 V** only, between distribution and each buck. Values are
  chosen after measuring each branch's current (§X) — *not* 10 A.
- Each XL4016 is set to 5.00 V **with no load**, verified with a multimeter,
  before anything is connected.
- Verify distribution-block group isolation with a continuity test first.
- No 12 V on breadboards; enclosure, strain relief, labelled wiring.
- Servo: powered from the branch 5 V rail, not the ESP32's regulator; a
  bulk capacitor near the servo; voltage sag during actuation is measured.
- Robots, PCs, laptop, router and switch keep their own rated supplies.

## H. Network

| Node | Link | Address (fixed in firmware/OS) |
|---|---|---|
| Router | — | 192.168.1.1 (DHCP pool shrunk to .2–.100) |
| Laptop (server) | Wi-Fi today (Ethernet to the router later) | 192.168.1.200 |
| ESP32-CAM / door master | Wi-Fi | .150 / .151 |
| System 2 — environment ESP32 #1 | Wi-Fi | **.152** |
| System 3 — consumable ESP32 #2 | Wi-Fi | **.153** |
| System 4 — reusable ESP32 #3 | Wi-Fi | **.154** |
| System 1 — UR5e / FANUC | Ethernet, **directly to the router** (switch only if ports run out) | .160 / .161 (*set on the controllers*) |
| System 1 — PC-01 / PC-02 | Wi-Fi or LAN (*to decide*) | .170 / .171 |
| Admin master PC | any (it only opens the portal) | — |
| Security camera (Mercusys MC210, lab corner) | Wi-Fi | **.155** (*router reservation*) |

Internet is optional. PCs that need internet use a second interface
(university Wi-Fi) **without bridging** to the lab LAN; the lab server binds
its services to the lab network. The portal distinguishes **device offline**
(no heartbeat) from **internet offline** (no route to the outside), which
it reports separately.

## I. System 2 — Environment ESP32 #1 (first to build)

| Signal | Sensor | Interface | Notes (*to verify on the actual module*) |
|---|---|---|---|
| temperature, humidity | DHT22/AM2302 | 1-wire data, GPIO4 | Read every ≥2 s (sensor limit); report every 30 s |
| smoke/gas | MQ-2 module | **digital DO** via divider → GPIO34 | Heater needs 5 V. Many modules pull DO up to VCC: **measure DO high level**; if ≈5 V use a divider (e.g. 10 k/20 k ≈ 3.3 V). Optional analog AO → divider → ADC1 GPIO35. Warm-up period ignored. Not a certified alarm. |
| flame | 5-channel module | DO → GPIO32 (module at 3.3 V) | Supplementary "flame indication" only. Check whether it has per-channel analog outputs |
| water leak | probe module | DO → GPIO33 (module at 3.3 V) | Model chosen later |
| motion | HC-SR501 | OUT → GPIO27 | Activity indication, not a people counter; *verify OUT level is 3.3 V* |
| emergency state | existing safety signal | **optocoupler** → GPIO26 (pull-up) | Monitors only; never part of the safety circuit |

ADC1 only (ADC2 is unusable with Wi-Fi); no strapping pins (0, 2, 12, 15).

**Firmware:** same structure as the door master — fixed IP .152, heartbeat
every 30 s (device type SENSOR_NODE, `components` = health of each sensor),
telemetry every 30 s **and immediately on any hazard change** (debounced),
offline ring buffer of the last N readings sent on reconnect (timestamped by
the server on arrival; buffered age reported), DHT read failures reported as
a component fault, never as a fake value.

**Message (reuses `POST /api/access/telemetry`):**

```json
{"device_uid": "ENV_LAB01", "lab_id": "LAB_01", "readings": [
  {"metric": "temperature", "value": 24.8, "unit": "C"},
  {"metric": "humidity", "value": 47.2, "unit": "%"},
  {"metric": "smoke", "value": 0, "unit": "state"},
  {"metric": "flame", "value": 0, "unit": "state"},
  {"metric": "water_leak", "value": 0, "unit": "state"},
  {"metric": "motion", "value": 1, "unit": "state"},
  {"metric": "emergency", "value": 0, "unit": "state"}]}
```

Only metrics the node actually measures are sent. Quality is derived by the
backend: VALID (fresh), STALE (older than the window), MISSING (never),
DEVICE_OFFLINE (no heartbeat), OUT_OF_RANGE (outside the sensor's physical
range, e.g. DHT22 humidity > 100 %).

**Backend additions:** on telemetry, hazard metrics (smoke, flame,
water_leak, emergency) raise a CRITICAL alert at once with a dedupe key and
resolve it when the state clears; temperature/humidity keep the threshold
rules. Live push to pages; the monitor tiles show the hazards.

## J. System 3 — Consumable smart bin (ESP32 #2)

Path: removable bin → weighing plate → 1 kg load cell (mounted per its
design, one end fixed, load end free) → fixed base. Nothing else touches the
plate. HX711 → ESP32 (2 GPIOs) → 16×2 I2C LCD (address **scanned**, not
assumed; supply voltage and pull-ups checked before deciding on a level
shifter).

Quantity model `n̂ = round((m − m₀) / u)`, with m₀ the empty mass and u the
calibrated mean unit mass — a **model**, reported with its measured error.
The node sends a measurement only when the reading is **stable** (variance
below a measured noise band for a set time); the backend turns stable step
changes into transactions (WITHDRAWAL / REFILL), attributed to the current
access session in the lab when there is exactly one — a correlation, never
an accusation. Booked vs actual vs additional are kept apart.

Calibration and tests (tare, known weights, repeatability, noise, drift,
step response, settling time, minimum detectable change, safe range) come
**before** quantity estimation. Bin 1: 10 kΩ resistors; bin 2 (capacitors)
only after bin 1 is validated.

## K. System 4 — Reusable smart bin (ESP32 #3)

PN532 (external) reads the item's NTAG213 UID → backend resolves
`assets.nfc_uid` → checks status and the user's session/booking → lid opens
through a `device_commands` request (`OPEN_LID`) the bin node fetches → servo
press–hold–release → reed switch confirms LID_OPEN / LID_CLOSED → asset
transaction recorded. Internal load cell = presence cross-check only.

Checkout design (§14 options): **Option A + C** — the user selects the asset
in the portal *and* scans its tag at the bin; the transaction completes only
when the scanned UID matches the selected asset. This avoids guessing which
item left the bin. Duplicate scans within an anti-repeat window (to be set
from measured read behaviour) are ignored. NFC UID = identifier, not
authentication.

## L. Servo / lid mechanism

MG90S + rigid push rod pressing the bin's existing push-to-open button.
Angles, hold time, travel and force are **measured on the actual bin**; a
stronger actuator only if MG90S fails a measured test. The lid path is
mechanically separate from the weighing path: no servo, lid, cable or
housing force reaches the load cell.

## M. System 1 — UR5e (read-only)

Ethernet directly to the router (a switch only if ports run out). Investigate **RTDE** (Universal Robots' real-time
data exchange interface). A collector on the laptop subscribes read-only and
writes state changes to `equipment_sessions` and numeric values to
`sensor_readings`. The fields used (robot mode, safety mode, program state,
joint positions, I/O) are confirmed against **this controller's software
version** before they are relied on. No commands to the robot; no AI or n8n
path to it.

## N. System 1 — FANUC

First identify: controller model and version, installed software options,
Ethernet interface. The protocol is chosen only after that. Until then the
equipment page shows it as *not integrated*.

## O. System 1 — PCs and the admin master PC

On the lab LAN (wired or Wi-Fi, to decide). A small authenticated agent
(`tools/pc_agent`, per-device key) reports heartbeat, CPU, RAM, disk,
network, logged-in user and session state every 30 s, and polls the portal
every 2 s for staff actions. Exam mode compares running program names with a
configurable list; violations are logged and staff notified; no automatic
penalty from a heuristic. Visible to staff only; retention limited (§W).

**The admin is the master PC.** It needs nothing installed: from the
portal (Equipment → 2 · Robots & PCs) staff can, per PC or for all PCs:

| Action | How it works | Audit |
|---|---|---|
| **Remove access** | mode `LOCKED`: the agent locks the PC (Win+L) and locks it again within ~2 s if anyone unlocks it, until access is given back; also survives an agent restart | `PC_ACCESS_REMOVED` |
| **Give access** | mode back to `NORMAL`; the person sees a notice | `PC_ACCESS_GIVEN` |
| **View screen** | only while the viewer is open: the agent shows a notice on the PC and sends ~2 frames/s (1280 px JPEG) to the portal's memory; stops ~6 s after the viewer closes; nothing is stored | `PC_SCREEN_VIEWED` |
| **Message** | a short text shown in a pop-up on the PC within ~2 s | `PC_MESSAGE_SENT` |

Limits, stated rather than hidden: the agent must run **in the signed-in
user's session** (Task Scheduler "At log on", not a service), otherwise it
cannot lock or see the screen; a user with admin rights can stop it. Screen
view is view-only — for full remote **control** use Windows RDP shadowing
(`mstsc /shadow:<session> /v:<pc> /control`, needs Windows Pro on the lab
PCs) or a VNC server; both can be launched from the master PC alongside the
portal. Tested on the development laptop with lock and pop-ups stubbed
(2026-10-03): lock re-applied every 2 s while LOCKED and stopped after
NORMAL, message delivered once, screen frames ~1.5/s at ~64 KB each, stopped
after the viewer closed.

## O2. Security camera (all systems)

A fixed Wi-Fi camera (Mercusys MC210, RTSP/ONVIF, 2K) high in a corner, read
by `tools/security_vision` on the laptop: people detected (YOLOX-S, CPU) and
tracked; a name only when the door makes it certain (first seen in the door
area right after a door entry, or the last unnamed person), else *Unknown*;
people seen vs inside per the door (possible tailgating / nobody entered);
a box per fixed item (PC, robot) learnt when clear and flagged when moved or
moving with nobody at it. Events with a snapshot, acknowledged by staff;
no continuous recording. Each lab tile on the Live monitor streams its lab.
Measured: face server latency 36.5 ms with it running vs 35.3 ms without.
Details and limits: `tools/security_vision/README.md`.

## P. Website changes

- **Robotics Lab page** (extends Lab detail): Environment card (temperature,
  humidity, smoke, flame, leak, motion, emergency with quality), Equipment,
  Inventory, Maintenance, Readiness.
- **Inventory**: consumable bins (mass, estimated qty with error band,
  reserved, available, reorder) and reusable assets (NFC UID, status, holder,
  booking, due back).
- **Equipment** split into the four systems (tabs 1–4 plus the register),
  with robot/PC live state, sessions and the master-PC controls.
- **Live monitor** tiles gain environment hazards and readiness.
- **Booking** gains optional resource requests.

## Q. Database changes — see §F (all additive).

## R. API changes

| Endpoint | Purpose |
|---|---|
| `POST /api/access/telemetry` (exists) | environment readings |
| `POST /api/access/heartbeat` (exists) | all nodes |
| `GET /api/labs/{id}/environment` | latest value + quality per metric |
| `POST /api/inventory/measurements` (device) | stable bin readings |
| `GET/POST /api/inventory/bins` (staff) | bins, calibration metadata |
| `POST /api/inventory/nfc/scan` (device) | resolve a scanned tag for the bin |
| `POST /api/assets/{id}/checkout|return` (exists, extended) | NFC-confirmed transactions |
| `POST /api/equipment/telemetry` (collector) | robot/PC state |
| `GET /api/equipment/{asset}/sessions` | usage |

All device endpoints require the device key; all user endpoints the JWT and role.

## S. n8n (13+)

13 environment abnormal · 14 smoke/gas · 15 flame · 16 water leak · 17
environment node offline · 18 consumable below reorder · 19 unexpected stock
change · 20 asset overdue · 21 asset damaged · 22 robot offline · 23 robot
alarm · 24 robot activity outside a booking · 25 PC offline · 26 exam
violation · 27 readiness warning · 28–32 usage/inventory/utilisation/
maintenance reports · 33 telemetry anomaly · 34 energy (future). Each reads
the `/automation` API, dedupes on the existing keys, and never touches a
safety-critical control.

## T. Analytics

Lab: utilisation, attendance, no-shows, late entry, busiest hours. Robots:
run/idle time, utilisation, faults, downtime. PCs: uptime, usage,
violations. Consumables: depletion, consumption rate, reorder forecast,
abnormal withdrawals. Reusables: checkout frequency, overdue, damage.
Environment: trends, excursions, motion vs bookings. Windows: 7/28/90 days,
semester, custom. All computed from stored records only.

## U. AI (read-only)

New tools: `get_environment` (history + quality), `get_inventory_status`,
`get_consumption`, `get_asset_loans`, `get_equipment_usage`,
`get_equipment_faults`. Each returns its time range and source; answers
separate OBSERVED / ANALYSIS / RECOMMENDATION. No tool writes, unlocks,
commands a robot or changes inventory.

## V. Security

Unique device ID + (new) per-device key, heartbeat, scope (a sensor node may
only post telemetry for its lab), audit log for every admin action, RBAC on
every user endpoint, NFC as identifier only, robots read-only, AI and n8n
read-only toward safety controls, door decisions only on the master.

## W. Privacy

Role-based visibility (names inside a lab: staff only — already so),
minimum data (PC agent: no keystrokes, no screenshots by default; screen
sharing only on explicit, logged request), retention (telemetry aggregated
after a set period; PC activity details purged after the exam/session
window), transparent exam policy shown to students, audit of who viewed
what.

## X. Testing plan (no value here is a result)

| System | Measure |
|---|---|
| Environment | DHT22 vs a reference instrument, repeatability, update interval; MQ-2 warm-up and DO behaviour; flame/leak/PIR detection and false triggers; emergency input; sensor→DB latency; reconnect |
| Power | each buck's no-load and loaded voltage, branch currents (→ fuse values), servo sag |
| Consumable bin | calibration curve, error %, repeatability, noise, drift, settling, minimum detectable change, n̂ vs real count per component type |
| Reusable bin | NFC read rate, distance, orientation, duplicate suppression, lid open/close time and success rate, checkout/return success, end-to-end latency |
| Robots/PCs | telemetry rate, state classification, offline detection, reconnect |
| End-to-end | sensor→DB→page, inventory→page, alert→n8n latency; AI answers checked against DB facts |

## Y. Implementation order

0. This audit ✔ — 1. Power distribution (verify, then fuse) — 2. Environment
node: backend hazard rules + environment card + simulator (no hardware
needed), then firmware, then bench validation — 3. Consumable bin #1 →
calibration → quantity tests → bin #2 — 4. Reusable bin — 5. UR5e — 6.
FANUC (after identification) — 7. PCs and exam mode — 8–11. Website, n8n,
analytics, AI — 12. Energy (future). Regression test of the door after
every step.

## Z. Risks and failure modes

| Failure | Detection | Behaviour / fallback |
|---|---|---|
| Environment node offline | no heartbeat > 90 s | tile "environment offline", readings marked STALE, alert; never shows old values as current |
| Sensor fault (DHT read fails) | component flag | that metric MISSING; others continue |
| MQ-2/flame/leak triggered | telemetry | CRITICAL alert, notification, red tile; physical safety systems unaffected |
| Consumable node / HX711 / load cell lost | heartbeat / component flag | bin stock frozen at last stable value, marked STALE |
| Reusable node offline / lid fails / reed disagrees | command timeout / reed state | request FAILED, staff notified, no transaction recorded |
| Duplicate NFC scan | anti-repeat window | ignored, logged |
| UR5e / FANUC / PC offline | collector timeout | equipment OFFLINE, session closed with reason |
| Master offline | heartbeat | door still works locally (RFID + fingerprint); portal shows offline |
| Laptop / backend down | nodes' requests fail | door keeps local operation; nodes buffer; nothing actuates |
| Router down | all nodes offline | door local only; recovery on reconnect |
| n8n / AI down | health checks | automation/AI features off; core unaffected |
| Internet down | external check | no effect on core; optional services marked unavailable — separate from device offline |

## Open questions for the owner (needed before wiring)

1. MQ-2 module: does DO swing to 5 V? (measure) Any onboard divider?
2. 5-channel flame module: pinout (5 analog + 1 digital?) and supply range.
3. Water-leak sensor: which model?
4. Emergency signal: which existing circuit, and is an optocoupler input acceptable to the lab?
5. LCD backpacks: supply 5 V or 3.3 V? (I2C scan + pull-up check)
6. How many PN532 boards besides the door's?
7. UR5e: PolyScope version; FANUC: controller model/software options.
8. PCs: OS, and whether a managed exam browser is allowed.
9. Router LAN ports free for the robots (a switch is needed only if they run out); PCs wired or Wi-Fi?
10. Lab PCs: Windows edition (Pro allows RDP shadowing for remote control), and may the agent start at log-on?

