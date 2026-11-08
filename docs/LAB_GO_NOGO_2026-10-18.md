# Lab day 2026-10-18 - go / no-go checklist

Prepared 2026-10-18 00:00-02:00 from the code, the live portal and measurements on the laptop. Labels:
**SOFTWARE VERIFIED** (tests / live software checks pass), **READY FOR SUPERVISED TEST** (all that software can
check passes; the physical step is next), **PARTIAL**, **BLOCKED** (a named dependency is missing).
Nothing physical has been tested tonight: no robot moved, no door opened, no actuator driven, no board flashed.

**Stop the procedure at the first unexpected result, write it down, do not bypass a failed safety check.**

## 0. Morning, before leaving (laptop) - 15 min

| # | Step | Expected | Status tonight |
|---|---|---|---|
| 0.1 | Close apps not needed in the lab (ChatGPT, Notion, Notion Calendar, extra Chrome tabs, Edge web views) | Task Manager: memory in use < 80 % | **NO-GO risk found**: commit charge 31.7 / 33.2 GB (95 %), 1.3 GB RAM free with both camera pipelines + AI + VS Code open |
| 0.2 | Settings > Time & language > Date & time > **Sync now** | "Last successful time synchronization" = today | laptop clock is **1.3 s behind** internet time (Windows Time service stopped). Everything on the laptop shares this clock, so the portal is consistent; only comparisons with other computers are off |
| 0.3 | Plug in the charger; power plan "never sleep" while plugged in | no sleep in the lab | - |
| 0.4 | OneDrive: pause syncing for 8 h (the repo is inside OneDrive: every test / build file is re-uploaded) | OneDrive icon "paused" | OneDrive used ~12 % CPU tonight |
| 0.5 | Docker Desktop running; `docker compose ps` | db, backend, frontend, n8n, backup up (restart policy: they come back by themselves) | SOFTWARE VERIFIED (restart test below) |
| 0.6 | `py -I tools/evidence/clock_check.py` | all OK except, at the lab, "laptop vs pool.ntp.org UNAVAILABLE" (no internet there) | run tonight: backend +53 ms, database +52 ms, PC agent +20 ms |

## 1. Both security cameras (priority 1)

What changed tonight (tested offline + live on a test instance; **the two camera services still run the old
code until they are restarted - `launch.bat` / `start_security_vision.bat [camera2.env]` at the lab loads it**):
* Reconnect with exponential backoff (1 -> 2 -> 4 -> ... 30 s) and FFmpeg open/read timeouts (8 s / 5 s): a dead
  camera no longer retries every 3 s for ever, a stalled stream ends after 5 s instead of hanging inside read().
  `/health` now shows `stream.state` CONNECTING / STREAMING / STALE / RECONNECTING / OFFLINE, frame age, retry-in,
  and the service clock. Live-verified on a test instance: STREAMING on camera 2's RTSP; CONNECTING ->
  RECONNECTING (1-2 failures) -> OFFLINE (3+) on a dead address; never two connections at once (test).
* `/metrics`: process CPU was always 0 % (bug) - now real (a test instance: 151 % of 1200 %), private memory (for
  growth), and the graphics card (nvidia-smi: load, memory, temperature, P-state).
* Identity (vision.py / identity.py / crosscam.py), all with tests:
  - **door entries** name a person only if they were AT THE DOOR WHEN FIRST SEEN, after the entry, alone: two people
    in together (one badge or two) -> nobody named + PERSON_IDENTITY_REVIEW; someone already at the door or walking
    to it does not inherit the name; naming waits 1.5 s so a second person right behind is seen first;
  - **posture changes** (sit, bend, crouch, lie, stand up) keep the track (feet stay put; unique pairs only);
    crouching/lying views are never learnt into a name or used to drop one;
  - **staged association** (ByteTrack-style): a just-seen track keeps its person before a track missing for a while
    may take anyone - found with the scenario bench: a runner crossing the spot where someone had just stood took
    that old track AND its name;
  - **sharp turns at a run**: the just-seen track gets its box back (unique, close, look agrees) and the speed is
    reset (a speed from the jump overshot into the neighbour and swapped two people side by side);
  - names re-dealt after a crossing and one name on two people are raised for staff review
    (PERSON_IDENTITY_REVIEW, new alert kind) and start at look-level confidence, not the door's;
  - **cross-camera names never worked** before tonight: crosscam shared only states "CONFIRMED"/"VERIFIED", which the
    identity ledger never produces. Fixed to the ledger's real states; a test now uses them.

### Simulated identity regression (tools/security_vision/scenario_bench.py) - SIMULATED, not physical evidence
Synthetic people with ground truth through the real Tracker / Labeler / CrossCam, 7 fps, 12 scenarios x 5 seeds x 3
noise levels (body-model same-person cosine ~0.9 / ~0.7 / ~0.5; missed detections 4 / 10 / 15 %):

| result over 180 runs | normal | hard | harder |
|---|---|---|---|
| frames showing someone else's name | **0** | **0** | **0** |
| name switches | **0** | **0** | **0** |
| track id switches (track splits; the person is Unknown for a while) | 1 | 8 | 33 |

Before the fixes (same bench): hard noise "running, sharp turns" 331 wrong-name frames; "side by side" 276;
camera 2 never received a name. IDF1 0.95-0.998 (normal), named share 0.93-0.98 for people who badged in alone;
"two in on one badge" stays Unknown by design (0 % named) until the face decides. HOTA not computed. Real-world
accuracy needs the physical tests below - no claim of 100 % is made.

### Measured performance (live)
| | camera 2 alone | camera 2 + 2nd pipeline (lab recording, new code) |
|---|---|---|
| analysis rate | 6.8 /s | 6.95 /s and 6.97 /s |
| pass p50 / p95 | 58 / 88 ms | 62 / 100 ms (cam 2), 73 / 138 ms (2nd) |
| frame age at analysis p50 / p95 | 37 / 98 ms | 37 / 97 ms |
| graphics card | 33 %, 794 MB, P3 | 36 %, 1083 MB of 4096, 68 C |
Detector and re-ID on the GTX 1650 (DirectML, no CPU fallback: `disable_cpu_ep_fallback`), confirmed in
`/metrics` engines. See also the 10-minute sustained test (section 6).

### Tomorrow, in this order (stop at the first unexpected result)
| # | Step | Expected result | Go / no-go |
|---|---|---|---|
| 1.1 | Camera 1 (MC210) at the lab: laptop on Smart_Lab, `ping 192.168.1.155`, `Test-NetConnection 192.168.1.155 -Port 554` | replies, TcpTestSucceeded True | no reply -> check its power / Wi-Fi in the Mercusys app |
| 1.2 | Close the old camera windows; run `launch.bat` (or `start_security_vision.bat` and `start_security_vision.bat camera2.env`) | windows "SECCAM_LAB01" and "SECCAM_LAB02"; `[detector] YOLO26 on directml-gpu1`, `[vision] re-id on directml-gpu1` | "on the CPU" -> stop, tell Claude |
| 1.3 | Mount camera 2 diagonally opposite camera 1 (2.2-2.5 m, tilted down), power, `ping 192.168.1.156` | reply; its window shows `[camera] streaming from rtsp://***@192.168.1.156` | - |
| 1.4 | `curl http://127.0.0.1:5100/health` and `:5101/health` | `"camera": true`, `stream.state` STREAMING, fps ~7 | STALE / OFFLINE -> check the stream before going on |
| 1.5 | Portal > Security > Live, split view | both pictures move, boxes follow people | - |
| 1.6 | Draw the door box on camera 1 (and camera 2 if it sees the door) | box saved | - |
| 1.7 | Floor map: 6 tape marks both cameras see; measure x, y from ONE corner; `py floorcal.py camera.env`, then `camera2.env` | "worst fit" < 0.15 m each; restart both services; window says "floor map loaded" | > 0.3 m -> re-measure; without the map no names cross cameras (safe) |
| 1.8 | Scenario 1: one person badges in and walks in | named ~1.5 s after first seen at the door; `/identity` shows DOOR_NEW_PERSON then the name | wrong name -> **NO-GO** for identity tests |
| 1.9 | Scenario 2: two people in on one badge / two badges close together | both Unknown + a "Identity needs review" alert; named later only by face | a name by timing alone -> NO-GO |
| 1.10 | Scenario 3: two named people side by side 1 min | names stay; never swapped | swap -> NO-GO, save `/identity` |
| 1.11 | Scenario 4: they cross 5 times (also with similar clothes if possible) | names stay or become Unknown, never swapped; a review alert if names were re-dealt | - |
| 1.12 | Scenario 5: one person walks from camera 1's view into camera 2's | camera 2 shows the same name after ~1 s in the overlap (floor map needed); a stranger nearby never gets it | - |
| 1.13 | Scenario 6: sit, bend, crouch, lie down, stand up | same box/name, or Unknown - never someone else's name | - |
| 1.14 | Scenario 7: walk behind the robot / a pillar 2 s and reappear | same name back (track kept 2 s; seated 6 s) | - |
| 1.15 | Scenario 8: run, sharp turns, near another person | no swap; Unknown for a moment is acceptable | - |
| 1.16 | Scenario 9: unplug camera 2's power 30 s | camera 1 unaffected; camera 2 `/health` RECONNECTING -> OFFLINE; back by itself after power (backoff <= 30 s); portal shows offline then live | does not come back -> restart its window |
| 1.17 | Scenario 10: lights dimmed / blinds | detection continues; names kept or Unknown, not swapped | - |
| 1.18 | After each scenario: ask Claude to read `/identity`, `/metrics` (fps, pass p95, frame age, GPU, reconnects) of both | numbers recorded in the evidence log | - |

Status: **SOFTWARE VERIFIED** (187 camera tests, scenario bench) / **READY FOR SUPERVISED TEST** (camera 2 live at
home; camera 1 not reachable from here). Calibration and identity accuracy: **physical test required**.

## 2. The "two cabinets" / physical systems (priority 2)
**No document in the repository calls anything a "cabinet".** The records describe one 12 V distribution
(docs/BRINGUP_LOG.md P1.4-P1.7: PSU -> master DC switch -> WAGO -> fused branches) feeding four systems. Please
confirm which two are meant; a checklist for each of the four is below (the two storage units first).

Measured tonight (from the portal's records, not physical): MASTER_LAB01 (door), BIN_NODE_1 (consumables) and
REUSE_BIN_1 (reusables) all went silent in the **same minute, 13 Oct 02:51** (Cairo), 5 minutes after the door master
rebooted (ONLINE 02:46, COMPONENT_FAULT alarm 02:47, ONLINE 02:47); the portal and n8n kept running. ENV_LAB01 has
been silent since 11 Oct 22:17. Three boards on one supply stopping together points to the supply / master switch or
the Wi-Fi, not three firmware faults - **to be confirmed at the bench**. No firmware has NTP: the server timestamps
their data on arrival.

Common steps for every system (approved procedure, meter on DC volts, nothing actuated just to pass):
| # | Step | Expected |
|---|---|---|
| a | Master DC switch OFF; check the branch fuse is in its holder, + side only (BRINGUP_LOG P1.4) | fuse present, rating written in the log |
| b | Switch ON; 12 V after the branch fuse (P1.5) | 11.5-12.6 V |
| c | Buck output at the node (P1.6/P1.7) | 4.95-5.05 V; worst sag during Wi-Fi / servo recorded |
| d | Serial monitor 115200: boot banner, reset reason, Wi-Fi joined, IP | "power-on" reset on a cold start; IP shown |
| e | `ping` the node from the laptop | replies |
| f | Portal > System Health / Lab Equipment | ONLINE, last report < 1 min |
| g | Router off 30 s, on again (network outage) | node rejoins by itself; portal OFFLINE then ONLINE; **no duplicate events, nothing actuated on reconnect** |
| h | Master switch off 10 s, on (power recovery) | node boots and reports; outputs in their safe state (door LOCKED, bin lid closed) |

Per system:
| System | Inputs to check | Outputs (only as part of normal use, never to pass a test) | Status |
|---|---|---|---|
| Consumables bin (BIN_NODE_1, bin-0.2) | load cell (tare, a known mass), NFC tag read, lid sensor | LCD text | **BLOCKED** (offline since 13 Oct) - physical check |
| Reusables bin (REUSE_BIN_1, reuse-mod-0.1) | load cell 5 kg (cal -518.04 counts/g, accuracy with independent masses NOT yet checked), reed switch (lid), NFC | lid servo MG90S moves only on a valid scan by a person at the bin; LCD | **BLOCKED** (offline since 13 Oct) |
| Environment node (ENV_LAB01, env-0.1.1) | DHT22, MQ-2, flame (5-channel), PIR | none | **BLOCKED** (offline since 11 Oct). Flame bench test: docs/LAB_READINESS_2026-10-18.md |
| Door master (MASTER_LAB01) | NFC (PN532), face via ESP32-CAM, door sensor | lock relay - **only the master opens the door**, never the portal; fail-secure on power loss (lock on NO) - confirm the mechanical/manual egress physically | **BLOCKED** (offline since 13 Oct) |

## 3. UR5e Home / STOP (priority 3) - full procedure: docs/ROBOT_CONTROL.md, "2026-10-18" section
Home = the pendant's validated program `home.urp` (load + play), reached only when joint feedback is within 0.5 deg of
J1 -15.00, J2 -126.00, J3 117.03, J4 -80.00, J5 91.00, J6 95.27 (degrees, base -> wrist 3). Software STOP is **not** a
safety-rated emergency stop.
Verified tonight (live, simulated robot, dry run): two people asking for control -> second refused (409); double
click -> DUPLICATE; STOP by an admin who does not own control -> latched; Home after STOP -> refused; every step
audited; **a latched STOP now survives a backend restart** (was cleared before - fixed, live-verified: restart 26.6 s,
still latched, marked "kept through a portal restart"); no Home is resumed after a restart; ownership is cleared.
Status: **SOFTWARE VERIFIED**; physical **BLOCKED** until steps 1-6 (network, twin, E-stops, home.urp, clearance,
dry run) pass with the operator; live only after sign-off (`ROBOT_CONTROL=live`).
Note: the simulated UR5e (UR5E_SIM) is STOP-latched by tonight's test (command ids TEST-...); recovery is refused
while its last telemetry says "moving" - clear it with the admin button when the simulator next runs.

## 4. FANUC Home / STOP (priority 4)
Verified from the controller's own page (2026-10-14): LR HandlingTool V9.30P/12, ER-4iA, Mate controller, DCS
V4.2.14; 220 installed options, DEMO list empty; remote-interface options installed: User Socket Msg R648, Socket
Messaging R636, PC Interface R641, KAREL R632, SNPX R553, Prog Num Selection J515, Robot Service Request, OPC-UA.
**Installed is not configured.** Motion stays disabled. Tomorrow: steps 1-3 of the FANUC plan in
docs/ROBOT_CONTROL.md (confirm Version ID on the pendant, monitoring check, twin within 0.1 deg), then the interface
decision with the qualified operator. Status: **BLOCKED** (interface, HOME TP program, tested stop, adapter).

## 5. PC fleet (priority 5)
Verified tonight (this laptop as the admin PC): agent 0.8 reports host name, its own IPv4 addresses (virtual
adapters filtered; never inferred from the router), agent version, foreground application, signed-in user, clock
offset (+0.02 s) - shown in Lab Equipment; screen preview first frame 2.3 s under load (0.3-1.0 s idle before);
preview audited (PC_SCREEN_VIEWED / _ENDED); visible lock = Windows Win+L (LockWorkStation), staff-only, audited,
recoverable by the student signing in. Browser tab titles/URLs: **not implemented** - needs a managed browser
extension / enterprise policy approved by IT; only the foreground application is shown.
| # | Step | Expected |
|---|---|---|
| 5.1 | Admin PC (this laptop) agent running | Lab Equipment: PC_ADMIN_LAPTOP online, agent 0.8, IPs, "Using: ..." |
| 5.2 | **IT approval** for one student PC (tools/pc_agent/README.md: Python + psutil/requests/pillow, nothing inbound) | written approval - without it stop here |
| 5.3 | Install on that PC, `agent.env` with its own DEVICE_UID / key | online within 30 s; host name + IP shown; clock offset < 2 s |
| 5.4 | View screen; monitor 1 / 2 / all; quality presets; full screen | picture < 2 s, notice visible on the student PC |
| 5.5 | View all screens (wall) | tile per PC |
| 5.6 | Share admin screen from https://192.168.1.200 (import deploy/tls/smartlab-ca.crt once into the browser's trusted roots) to that PC only | preview locally first, then "Go live"; student PC shows it with an exit; Stop ends it on the PC |
| 5.7 | Lock (visible) | Windows lock screen on the student PC; student signs in again |
| 5.8 | Unplug that PC's network 30 s | portal shows offline after ~1 min, back by itself; no queued action runs late (actions expire after 60 s) |
| 5.9 | Audit (Admin > Audit) | every view / share / lock listed with who and when |
Status: **SOFTWARE VERIFIED** (admin PC) / **BLOCKED** for student PCs (IT approval).

## 6. Reliability pass (tonight, live)
* **Concurrent users** (12 threads, no think time, + AI + PC preview + robot controls): 360 requests, **0 errors**;
  p50 575 ms / p95 1.9 s under that stress (the backend is one Python process: ~20 requests/s capacity).
  Single user: p50 36 ms / p95 99 ms. Realistic (10 users, 3 s think, + 2 live viewers x 2 cameras at 15.5
  frames/s): API p50 121 / p95 376 ms, frames p50 53 / p95 178 ms, 0 errors. Known limit: several people on the
  Live split view at once compete with the API (each viewer = ~16 frame requests/s through the backend).
* **Restart / recovery**: backend restart -> healthy in 26.6 s; PC agent reported again by itself; STOP latch kept;
  ownership cleared; no robot command resumed; PC actions expire (never run late); duplicate DEVICE_OFFLINE events
  (13 Oct: 3 per device) no longer occur (17 Oct: 1 per device).
* **Clock**: all clocks on the laptop agree (backend +53 ms, database +52 ms, PC agent +20 ms); the laptop itself is
  1.3 s behind internet time (step 0.2). ESP32 nodes and robot collectors have no clock of their own.
* **Sustained 10-minute load**: see docs/reports/reliability_2026-10-18.md.

## 7. What needs a person / hardware / approval
* Camera 1 reachability, camera 2 mounting, floor calibration, all identity scenarios (1.x).
* Which two "cabinets"; power / fuse / voltage measurements; ESP32 nodes back online; flame detector bench test.
* UR5e: cable/IP, operator, E-stop check, home.urp, clearance, sign-off. FANUC: interface decision + operator.
* Student PC agent: IT approval. Browser tab visibility: IT-approved managed extension.
* Laptop clock sync (0.2) and memory headroom (0.1): owner's choice.

## 8. Added during the day (2026-10-18, deployed)
* **Portal > Reliability**: start every lab session with the **Briefing** tab (what needs attention, linked to
  evidence); **Dependencies** shows each part's live state and what it needs (what-if = simulation only).
* **Incidents**: repeats are counted on one incident (xN), a returning condition reopens it, MITIGATED state,
  **Investigate** button (ranked explanations, correlation not proof). A camera service without a picture
  for 5 min raises one "no picture" incident that clears itself when frames return.
* **AI**: "which robots / cameras / PCs are online", "any alerts" now answer from the records in < 0.2 s. Open
  questions use the local model with 4 threads, one at a time (keeps the cameras at ~7 fps).
* **Camera services**: when started from `launch.bat` they now run at above-normal priority and print it;
  `/health` shows `stream.state`. Expect in the camera window: `process priority: above normal`.
* **Deploy**: `py -I tools/deploy/deploy.py` (tests, version stamp, smoke tests, automatic rollback).
* **Security (owner)**: change the administrator password (it is still the published seed password -
  docs/SECURITY_FINDINGS_2026-10-18.md S1).
