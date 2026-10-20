# Lab readiness - physical steps (prepared 2026-10-17)

Everything below needs the lab, the hardware or a person's authorisation. The software side is
deployed and tested. Stop at the first failing step and note the observation.
After the session run `py -I tools/evidence/run_evidence.py` - the report separates REAL_HARDWARE from
everything else.

Measured on 2026-10-17 from this laptop (192.168.1.200, Smart_Lab router answers at .1):
only the MC200 camera (.156) answered on the lab network. No reply from .150 (ESP32-CAM / master),
.151 (tablet), .155 (MC210), .102 (UR5e), .100 (FANUC). The three ESP32 boards (MASTER_LAB01, BIN_NODE_1,
REUSE_BIN_1) all went silent in the same minute (2026-10-12 23:51) and ENV_LAB01 on 2026-10-11 19:17 -
a common cause (unplugged / moved), not three separate faults. No code change was needed.

## 1. ESP32 boards (door controller, environment node, bins)
1. Power each board; watch its serial log for Wi-Fi join (SSID Smart_Lab). The router's 2.4 GHz channel is
   now Auto - an ESP32 in station mode follows the AP channel, nothing to change in firmware.
2. Within ~1 min each appears ONLINE on Admin -> System analytics -> System health. Their "offline"
   incidents resolve themselves when they report again (no manual resolve needed).
3. Door: one card + finger entry; the access event appears in Access & audit.

## 2. Flame detector (ENV_LAB01) - do NOT change thresholds before this
Finding from the data: 678 active readings in its whole history, 642 of them in one block on 2026-10-09
16:00-19:00 Cairo time (~100 % active then), 11 separate activations in total, never together with smoke,
temperature normal (27 C). That pattern fits sunlight / IR on the sensor in the late afternoon or a
deliberate test during bring-up - not a constantly noisy sensor.
1. Note where the node sits relative to windows and the afternoon sun.
2. Read the module's digital output with the LED: cover the sensor with your hand -> must go inactive.
3. Lighter / match at ~50 cm in front -> must go active within 1 s; remove -> inactive.
4. Shine a phone torch from 30 cm -> if this triggers it, the sensitivity potentiometer is too high or
   the sensor sees sunlight: turn the pot until the torch no longer triggers but the flame at 50 cm does.
5. Record before/after in the incident ("Log recovery action") - the portal keeps the history.

## 3. Cameras
- Camera 1 (MC210, SECCAM_LAB01, .155): ping, then Admin -> Security camera -> the picture must update;
  System health shows it ONLINE (now DEGRADED: service running, no picture).
- Camera 2 (MC200, SECCAM_LAB02, .156, works today at 7 fps): mount diagonally opposite camera 1, then
  `py tools/security_vision/floorcal.py` (floor calibration), then the tests: one person walks the room;
  two people cross paths; one person hides behind equipment for 5 s; lights off/on; fast walk. Expected:
  a known person keeps their label or becomes "unknown" - never swaps to another person's name.
  Note the measured stream delay (clock in view vs portal timestamp).

## 4. UR5e (control stays DRY RUN until step 6 is signed)
1. Cable, IP 192.168.1.102, ping; start `tools/robot_monitor/start_ur5e_monitor.bat`.
2. Twin follows joints; Robot page shows live joint values; "Driven from: Teach pendant" while jogging.
3. Run the pendant's own Home -> the master-control panel must show **Home reached** (all joints within 0.5 deg of
   -15.00, -126.00, 117.03, -80.00, 91.00, 95.27).
4. Clearance: with the operator, move to typical working poses and check the joint-space path to Home is clear
   (ceiling mount).
5. Remote mode on the pendant only if the operator agrees; Local mode must make the portal Home "refused".
6. Owner sign-off -> `ROBOT_CONTROL=live` in .env, rebuild/restart only the backend; first live test with a hand
   on the E-stop (STOP -> latched -> admin recovery; then Home from a nearby pose). Back to `dry_run` afterwards.
The portal STOP is a software stop, never a safety-rated emergency stop.

## 5. FANUC ER-4iA (monitoring only until the interface is known)
1. Pendant: MENU -> STATUS -> Version ID -> note the controller (R-30iB Mate Plus) and software version.
2. MENU -> STATUS -> Version ID -> ORDER FI (options list): look for R648 User Socket Messaging, R641 PC Interface,
   R632 KAREL, R553 HMI Device (SNPX), or PNS/UOP signal use. Photograph the list.
3. Write the HOME program (TP) on the pendant at reduced speed; record its joint values.
4. Only then design the FanucAdapter on the interface that is actually licensed. No UR commands or poses reused.

## 6. PC agent pilot (needs IT approval first)
Files: `tools/pc_agent/` - `start_pc_agent.bat`, `agent.env.example`, README (requirements, firewall: nothing inbound).
1. On one approved lab PC: `py -m pip install psutil requests pillow` (or OpenCV + numpy, already used for the cameras).
2. Copy `agent.env.example` -> `agent.env`, fill DEVICE_UID / DEVICE_KEY; run `start_pc_agent.bat` in the student session.
3. Portal: it appears under Lab Equipment -> Robots & PCs; test View screen (notice appears on the PC), monitor switch,
   View all screens, Message, Open app -> notepad, share from https://192.168.1.200 to that PC only, Stop.
Already verified on 2026-10-17 with this laptop as the admin PC (PC_ADMIN_LAPTOP, master PC): preview first frame
1.7 s, 2.2 frames/s, monitor 1/2/all switch, wall, reconnect after an agent restart (1.3 s), sharing from the browser
(to a selected PC) and from the master PC, Stop ends both, every step audited.

## 7. Inventory and incidents
- One physical count per bin (Lab Equipment -> Consumables -> Count). This is the baseline the discrepancy view needs.
- Incidents (/admin/incidents, "group similar" on): 68 open, mostly from bring-up (2-15 Oct), 20 of them two repeated
  camera warnings from one device. Triage one group at a time with a real closure reason; the 6 "Forced entry"
  (2-9 Oct) and 2 "Person in the lab with no door entry" deserve a human look first. Nothing was bulk-resolved.

## Update 2026-10-17 night (software done since the list above)
- Camera-wide grouping: from the 3rd box of one camera with the same warning within 5 s, one "camera-wide change"
  incident lists the boxes (all events still stored). Incident review with evidence: docs/INCIDENT_REVIEW_2026-10-17.md.
- Security -> Live: both cameras of a lab side by side (toggle), click one for its details.
- Lab Equipment -> Robots & PCs: Home / STOP ROBOT panel under each twin (UR5e: DRY RUN, BLOCKED until live joint
  data; FANUC: unavailable with the reason). Tab main-thread blocking 10.5 s -> 2.8 s per 10 s (panel re-render fix).
- IoT Dashboard robot fleet: compact twins no longer spill the view buttons over the card.
- Tests: backend 495 passed (incl. camera-wide test); evidence 35 pass / 12 fail (all hardware off or away).
- Docker Desktop updated itself during the session (stack stopped); the stack was started again as it was.
