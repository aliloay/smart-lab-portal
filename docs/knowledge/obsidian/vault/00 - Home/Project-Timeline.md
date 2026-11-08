---
type: "timeline"
generated: true
updated: "2026-11-04T00:01:22+02:00"
sources: ["git log --all", "conversation records (counts)"]
---

# Project timeline

> Generated. Commits are **verified historical** (from git). Conversation counts show when the project was discussed; what was said is in *History review* until you approve it.

## 2026-09-13
- Conversations: 3 owner / 3 assistant messages in ChatGPT - Bsc. "Smart Lab"

## 2026-09-14
- Conversations: 9 owner / 13 assistant messages in ChatGPT - Bsc. "Smart Lab", ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-15
- Conversations: 12 owner / 24 assistant messages in ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-16
- Conversations: 4 owner / 4 assistant messages in ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-17
- Conversations: 13 owner / 15 assistant messages in ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-18
- Conversations: 83 owner / 93 assistant messages in ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-19
- Conversations: 68 owner / 79 assistant messages in ChatGPT - Bsc. "Smart Lab" (1)

## 2026-09-20
- Conversations: 46 owner / 68 assistant messages in ChatGPT - Bsc. "Smart Lab" (1), ChatGPT - Bsc. Smart Lab (2)

## 2026-09-21
- Conversations: 41 owner / 49 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-09-22
- Conversations: 19 owner / 19 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-09-23
- Conversations: 46 owner / 102 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-09-24
- Conversations: 7 owner / 34 assistant messages in ChatGPT - Bsc. Smart Lab (2)
- `7ae0b83` Initial commit: Smart Lab Portal (81 files)
- `cbabba3` Add GitHub Actions workflow for Python package with Conda (1 files)

## 2026-09-25
- Conversations: 18 owner / 18 assistant messages in ChatGPT - Bsc. Smart Lab (2)
- `edbbfe0` Replace Conda workflow with project CI (4 files)
- `76814a1` README: add features, screenshots, and current setup steps (7 files)
- `1165855` test(backend): cover maintenance, traceability, privacy and live stream (4 files)
- `02bc416` feat(backend): maintenance workflow, notifications, honest session tracing (28 files)
- `7516135` fix(backend): refuse to start on an out-of-date migrated schema (3 files)
- `95cd46e` fix(deploy): allow issue photo uploads through nginx (8 files)
- `e594331` feat(frontend): smart lab platform - role experiences, maintenance, traceability (52 files)
- `e9fefcc` test: real-browser navigation test in CI (4 files)
- `f6248ee` docs: README for maintenance, traceability, tests and new screenshots (15 files)
- `c0dba97` Merge pull request #1 from aliloay/ui/final-smart-lab-polish
- `41efbd1` feat(brand): official GIU logo on the sign-in page and sidebar (5 files)
- `e2e70bc` fix(brand): keep the GIU logo's black G and flag stripe black (4 files)
- `abf52d4` test(backend): asset lifecycle, session detail and security notifications (1 files)
- `6af93fc` feat(backend): asset lifecycle, access session detail, security notifications (10 files)
- `164d96f` feat(frontend): asset lifecycle, live access session, simulation mode (12 files)
- `3021693` ui: compact equipment and maintenance-history tables; configurable dev API target (3 files)
- `a717010` test(e2e): browser workflows - booking to QR, staff booking for a user, issue with photo, simulation, phone width (3 files)
- `d0a31e7` fix(security): compare the device API key in constant time (1 files)
- `dcb79db` test: cancellation and new-report notifications; maintenance workflow in the browser (3 files)
- `96888fc` ui: never present an offline controller's last report as live (4 files)
- `0bcf179` docs: architecture, database, access flow, maintenance and demo guides (7 files)
- `baa1fe2` test(qr): judge each distance over a hand-held frame window, not one frame (1 files)
- `ae4c215` chore: ignore logs, temp files and local .env variants (1 files)
- `54451ff` fix(docker): the compose stack starts on a developer laptop in one command (3 files)
- `d988c03` ci: start the compose stack and check it from outside (2 files)
- `33a0bfa` feat: launch.bat - checks Docker, prints the LAN address, runs docker compose up (2 files)
- `8c6b8f8` docs: Docker Compose is the recommended launch, with LAN and firewall setup (2 files)
- `56b0111` ci(smoke): send a valid 16-byte WebSocket key (1 files)
- `fa0c810` Merge pull request #2 from aliloay/ui/final-smart-lab-polish
- `a9c74e2` fix(docker): one database whatever folder the stack is started from (2 files)
- `8734e1e` fix(qr): never issue a booking QR the door cannot read (7 files)
- `49e323c` Merge pull request #3 from aliloay/fix/qr-always-readable
- `2e1a2bb` feat: launch.bat brings up the whole demo - Docker, face server, portal, browser (6 files)
- `7534303` Merge pull request #4 from aliloay/feat/launch-face-server
- `0565336` ui: lighten the navy theme one notch (8 files)
- `406bbb9` Merge pull request #5 from aliloay/ui/lighter-blue
- `ade57ac` Fix 'QrAuthResult does not name a type' compile error (1 files)
- `ad1e984` Book: 'Test QR now' - book the lab from now for 30 min and open the QR (1 files)
- `bb57906` Book: 'Exact time (AM/PM)' tab to pick any start/end to the minute (1 files)
- `c6f7d03` Camera link: keep-alive face server, backoff on failed frames (4 files)
- `32a796a` Faster QR at the door: WeChat decoder fallback, faster camera polling (2 files)
- `ea2860b` test(e2e): book the latest day that still has a free hour (1 files)
- `bb37511` ui: sidebar for navigation, header for system and account, GIU quieter (2 files)
- `d2dd079` Merge pull request #6 from aliloay/ui/layout-hierarchy
- `195b9a9` Camera: smaller JPEGs and a [PERF] line; master shows CHECKING on QR (2 files)
- `2484c27` ui: cyber-glass design language, applied through the shared primitives (8 files)
- `3237e59` Merge pull request #7 from aliloay/ui/cyber-glass
- `3ac686d` ESP32-CAM: disable Nagle on the upload socket (1 files)
- `244a6c2` ui: GIU logo after sign-in - bigger, full strength, crisper outline (2 files)
- `0c900cd` Merge pull request #8 from aliloay/ui/giu-logo-clearer
- `088d75e` Report camera-side timing in the face server's stats line (2 files)
- `1b072a2` Master: unlock the door before reporting the step-2 match (1 files)
- `e99b830` TEST: camera at CIF (400x296) instead of VGA for faster uploads (2 files)
- `84e3f7a` Revert "TEST: camera at CIF (400x296) instead of VGA for faster uploads" (2 files)
- `788d26e` face_server: skip the WeChat QR decoder on frames with a face (1 files)
- `fb326dd` Master: drop the QR_SCAN report and the duplicate QR denial report (1 files)
- `9662e8e` Camera: two frames in flight to the laptop (2 files)
- `a5ad112` Master LCD: no white flash after a denial; optional user photo on grant (3 files)
- `3392be5` make_lcd_photo: robust loading, name the real format when it fails (1 files)
- `3854156` Fix white grant screen; back to one frame in flight (3 files)
- `5847a64` Master LCD: hardware SPI and a light wake instead of full resets (1 files)
- `117c426` Master: redesigned LCD screens, door alarms, component health (1 files)

## 2026-09-26
- Conversations: 14 owner / 25 assistant messages in ChatGPT - Bsc. Smart Lab (2)
- `06fdd3a` Portal: alerts for door alarms and failed door components (6 files)
- `2463503` Face server: one-time firewall setup script and a missing-rule warning (2 files)
- `5086537` TEST: ESP32-CAM greyscale frames (GRAYSCALE = true) (1 files)
- `daa4a6a` Revert "TEST: ESP32-CAM greyscale frames (GRAYSCALE = true)" (1 files)
- `c325d43` Add Graphify MCP server configuration (2 files)
- `0dece45` Add n8n MCP server configuration (1 files)
- `fbb2c38` Automation outbox, n8n automation API and operations analytics (17 files)
- `7c4591e` Operations Center, lab usage twin, student lab time, QR states (11 files)
- `0a69283` n8n workflows, self-hosted n8n profile and automation docs (23 files)
- `e89c145` Release verification: n8n JSON exports, IPv4 n8n, reproducible setup docs (19 files)
- `20a843a` Merge pull request #9 from aliloay/claude/sharp-cray-n2ao8e
- `5269f55` launch.bat: start n8n too when automation is configured in .env (1 files)
- `baf5f6d` n8n workflows: use Header Auth for the automation key (27 files)
- `d49f7f7` AI lab assistant, maintenance priorities, trends and CSV export (36 files)
- `58f293f` Self-service student sign-up on the login page; per-role Add buttons for admins (11 files)
- `1dee180` Free local AI via Ollama, plus a student helper (12 files)
- `a11416b` WIP on claude/sharp-cray-n2ao8e: daa4a6a Revert "TEST: ESP32-CAM greyscale frames (GRAYSCALE = true)"
- `bde1c31` index on claude/sharp-cray-n2ao8e: daa4a6a Revert "TEST: ESP32-CAM greyscale frames (GRAYSCALE = true)"
- `51fce5b` Automatic door identities, serial fingerprint enrolment, chat bubble, n8n self-test (15 files)
- `24ce8d7` test-automation: explain which workflows report a run on a test event (1 files)
- `1ac0878` env examples: sign-up now gets a door identity (2 files)
- `5040a45` launch.bat: start Ollama and fetch missing AI models automatically (3 files)
- `474f069` Local AI: 8k context by default, retry at 4k if Ollama's engine crashes (4 files)
- `d88676d` Local AI: fall back to the processor when the GPU cannot run Ollama (7 files)
- `8798a8d` AI on the processor: 10-minute proxy timeout, remember GPU failure (3 files)
- `6ed667c` AI chat: sidebar button, and faster local answers (11 files)
- `ec74018` Lab access setup reminder, AI knowledge guide, separate student model (24 files)
- `a57a9f1` Docs: full system walkthrough and fresh screenshots (26 files)
- `d48eb9e` AI: student chat shares the staff model by default (8 files)

## 2026-09-27
- `616bc32` Merge pull request #10 from aliloay/claude/sharp-cray-n2ao8e

## 2026-09-28
- Conversations: 46 owner / 129 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-09-29
- Conversations: 14 owner / 14 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-09-30
- Conversations: 17 owner / 16 assistant messages in ChatGPT - Bsc. Smart Lab (2)
- `85ff25e` Master: PN532 RFID over I2C, and read-only tablet display (2 files)

## 2026-10-01
- Conversations: 3 owner / 11 assistant messages in ChatGPT - Bsc. Smart Lab (2)

## 2026-10-02
- Conversations: 38 owner / 41 assistant messages in ChatGPT - Bsc. Smart Lab (2), ChatGPT - Bsc. Smart Lab (3)
- `4b4e774` Offline lab router, live door state, automatic grant-screen photos (19 files)
- `53ca156` Portal: enroll a face from Users & roles, with live camera view (9 files)
- `cd24154` Live monitor: a full-screen wall view of every lab (8 files)
- `58e3f27` Fingerprint enrollment from the portal via device commands (14 files)
- `f8cd38e` Live monitor: every lab as an equal tile in a full-screen grid (4 files)
- `d6ff850` Face recognition: offline comparison of LBPH and SFace (3 files)
- `7bfc415` Docs: Robotics Lab architecture audit and design (design only) (1 files)
- `d2a13a6` System 1 (environment node): backend, website and firmware, pre-hardware (13 files)
- `8b6cf98` Face server: SFace (YuNet + embeddings) by default, LBPH as fallback (3 files)
- `32238c1` Face ID photos sent by the person, approved by staff (10 files)
- `ab9c252` System health: report internet separately from device health (5 files)
- `1ee7ad3` System 1: environment in lab readiness and a read-only AI tool (4 files)
- `7a6b51c` Per-device keys: each device can have its own key, scoped to itself (12 files)

## 2026-10-03
- Conversations: 55 owner / 231 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `5858d18` System 2 (consumable bins): backend, inventory page and bin firmware (14 files)
- `8112c32` System 3 (reusable smart bin): NFC items, checkout/return, bin firmware (14 files)
- `3f627fc` System 2 (robots + PCs) base; smart bin lists only bin items (19 files)
- `3bbca09` Users & roles: Enroll button opens a door-enrollment drawer (1 files)
- `cbec33f` Equipment page: the lab's four systems as tabs (4 files)
- `3dad492` n8n workflows 13-22 for the Robotics Lab (28 files)
- `c723cc9` Tablet live camera view with positioning hints, at no camera cost (3 files)
- `63e7d0c` Admin master PC controls; renumber systems to the owner's 1-4 (24 files)
- `1909a41` RFID card enrollment from the portal, staff photo upload, editable email, faster tablet view (16 files)
- `7d47c53` Ask the lab: much bigger chat panel, with a full-screen option (1 files)
- `7672f4b` Security camera: people, names from the door, watched equipment, live on every monitor tile (28 files)
- `3a4248f` Backup: working tree before the 2026-10-03 session (uncommitted emergency + master PC work) (617 files)
- `94c9163` Backup: emergency tab, master PC, Hemaly, door firmware fix (2026-10-03) (624 files)
- `4e7bd24` Emergency tab, master PC, camera name lock, bin weight check, instant AI agent and PDF reports (44 files)
- `c547b77` Emergency through n8n, fast AI answers, webcam name-lock demo (17 files)
- `737aab7` Bring-up prep: bench lab, per-device keys, staged sensors, measurement logging (28 files)

## 2026-10-05
- Conversations: 93 owner / 185 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `272ce74` Door: lock on NO, buzzer back, tablet speaks prompts and alarms (8 files)
- `48dcd59` Environment node 0.1.0: all five sensor groups pass on the bench (9 files)
- `87efc91` Environment hazards go live: full-screen alarm, live status, node reporting (13 files)
- `f11d4b2` Hazards that repeat, live readings, cleaner pop-up and alerts (13 files)
- `91a6612` Tests can never touch the live database again (1 files)

## 2026-10-06
- Conversations: 69 owner / 291 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `9de6174` Staff advisories: temperature/humidity limits and motion in a closed lab (9 files)
- `f244186` Motion is a quiet blue note, CLEAR / CLEAR ALL, Enter works with autofill (7 files)
- `0205615` Camera in the portal, data recovery, assistant charts, faster portal (32 files)
- `03c6d32` Automatic verified backups with failure alerts; admins and staff manage sign-in details (13 files)
- `9c1508f` Audit 2026-10-06: status matrix, data provenance, restore test, Chapter 4 checklist (1 files)
- `bdd7659` Data provenance on every record, data mode, thesis experiments (15 files)
- `e4a31f8` Analytics test: heatmap hours compared within float precision (1 files)
- `dc58155` Web server re-resolves the backend: no 502 Bad Gateway after a backend restart (1 files)
- `ab2b942` Evacuation alarm on every screen, CLEAR ALL, actionable improvement plan, no Bad Gateway on restart (13 files)
- `d432ac5` Emergency message read aloud everywhere, Clear sound / Clear all, Notifications tab, no false smoke (26 files)
- `92ff85e` Faster wall screen and Operations Center: batched queries, small sparklines (7 files)

## 2026-10-07
- Conversations: 59 owner / 131 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `d66d935` Reusable bin: modular firmware with per-component hardware tests (32 files)
- `8dd0e90` Security camera recording for admins (local, FFmpeg); bin firmware: no hang without HX711, hxprobe (12 files)
- `e7e54c8` Recording runs until Stop in 1-hour parts; HX711 slow clock on the ESP32, hxreset/rawlog (8 files)
- `f445be4` Reusable bin: HX711 gain 64/128 (saved), live weight on the LCD in test mode, LCD test on (4 files)
- `6fb66e5` Reusable bin: no false 'HX711 stopped answering' after tare / cal / rawlog (1 files)
- `4ea4026` Reusable bin LCD: line 2 shows STABLE/moving and the reading's spread (+-g), not the gain (1 files)
- `fdd8dba` Reusable bin: HX711 recovers by itself from a stuck state (3 nonsense codes -> power-cycle) (2 files)
- `b2218b4` Find equipment: full 640 model over overlapping tiles, weak hits and containers dropped (3 files)
- `be2b8f0` Camera boxes follow the view: re-aligned automatically when the camera pans or is bumped (5 files)
- `239aab6` Robot training pictures: admin Start/Stop collecting on the security camera (7 files)
- `d193c0a` Camera move handled in seconds, without false equipment alerts (1 files)
- `87e3d46` Camera boxes: re-align from the staff-drawn anchor, only after the view settles (4 files)
- `ecac1cd` Equipment watch: background monitor scan vs named boxes; move a misplaced box from Find equipment (8 files)
- `5305bb4` Camera clock set at every start (the MC210 forgets it on power loss) (2 files)
- `d5b32c8` README: security camera pictures from the robotics lab (faces blurred) (4 files)
- `495ea08` Camera: robots show 'moving' while they move and park without 'changed'; door open/closed from the red leaf (6 files)
- `000a5c8` Camera: face names come back by look after the track is lost; robot moves logged; delete a recording (moved to deleted/) (9 files)
- `d2f2966` Camera: a face name is never given back to a small / half-hidden person (2 files)
- `6bb2523` Camera: a seated person who drops out of detection gets their name back at the same place (3 files)

## 2026-10-08
- Conversations: 100 owner / 213 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `6333d56` Snapshot before session 2026-10-08 (working tree) (604 files)
- `19fe7ef` Security hardening, identity evidence engine, camera latency instrumentation (38 files)
- `ea07683` Robots (read-only) + IoT Command Center + 3D twins (27 files)
- `ce42a5d` Robot fusion: camera optical flow in robot boxes vs telemetry (11 files)
- `6fe4238` Portal speed: every page lazy-loaded, prefetched in the background after sign-in (1 files)
- `6512ee3` Docs: Monday lab checklist, security, latency (measured at home), robots; CPU reading fix (5 files)
- `7f3b99f` React Router 7.18 (clears the 2 moderate advisories; npm audit: 0) (2 files)
- `c7b5fa8` Command Center: live lab floor plan, clock, counters, robots in the top panel; robot page: live per-joint traces, twin fills its card, reach (5 files)
- `beb6924` Robot twins from the manufacturers' real models: UR5e and FANUC LR Mate 200iD (26 files)
- `41673b8` Robots: Robotiq 2F-85 on the UR5e twin, movement replay, tool trail, wall mode, staleness fixes (31 files)
- `5a4437e` UR5e twin ceiling-mounted under a gantry plate, as in the lab (2 files)
- `6052b3a` Reusable bin: 1 kg load cell capacity, OVERLOAD warning on log and LCD (4 files)

## 2026-10-09
- Conversations: 38 owner / 85 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `6ba6c0f` Handoff 2026-10-09: booking equipment, smart bin in normal mode, personal door QR, device states (48 files)
- `4c425c4` Codex prompt in its own file (docs/CODEX_PROMPT.md); handoff prompt updated (2 files)

## 2026-10-10
- Conversations: 4 owner / 8 assistant messages in Claude Code session 3b9b3107

## 2026-10-12
- Conversations: 119 owner / 320 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `c946c94` Camera: YOLO26s on ONNX Runtime at 640, 8 threads, fast box loop, in-use/passing rules, whole-picture flicker filter, robot work area, HOME  (4 files)
- `3896870` Camera names: best-match reacquire with rivals, face min 0.50; bench QR+face entry bridge (4 files)
- `7a1930c` Camera: a name is never on two people at once (2 files)
- `ffaa684` Face ID: remove saved face photos (archived, not deleted) and capture again (4 files)
- `c12a970` Camera identity: faces cut from the detection frame (skip touching people, drop stale), look frozen while touching, place hand-back narrowed (3 files)
- `e5904e4` Users: Remove user (disabled, credentials revoked, history kept), show-removed toggle (4 files)
- `23773a3` Face ID: remove-photos button on the closed card too (1 files)
- `eb72f92` Camera: detector conf 0.35 (seated people), stricter look reacquire 0.18 (2 files)
- `3ae3275` FANUC: label the confirmed ER-4iA / R-30iB Mate Plus; 3D shape marked as unverified stand-in (1 files)
- `c589f7f` Camera: a lost name comes back only with that person's own face match (owner's rule) (2 files)
- `b2a8b09` Robots in Equipment: live twin + joint bars; offline PREVIEW posed with the bars (drawing only); FANUC ER-4iA label, approximate pneumatic g (13 files)
- `0397aed` UR5e: always-on read-only RTDE monitor (robot.env UR5E_IP), started by launch.bat; auto-reconnect (3 files)
- `b8b2402` Robots: hold a link and drag (preview), J7 gripper, full view, 11 lab PCs from the camera; Robots menu entry only for students (4 files)
- `73b1710` Robots: grab any part, whole arm follows (IK, preview only); robots no longer listed twice (4 files)
- `f265146` Face server: enrolment before security-camera identify (no queue), YuNet face finding for enrolment, timing logged (1 files)
- `a47604a` Audit: ESP32-CAM state probed directly, health pill names offline controllers, face archive git-ignored (4 files)
- `fceaf8d` Face enrolment quality gate: one face, size, sharpness, no repeats; reason shown in the portal (3 files)
- `5178ee0` Labs: names/locations per owner, CAD lab retired (data kept), experiments inside each lab, door parts not lab equipment; usage charts with a (13 files)
- `f57ecb2` IoT Dashboard: wall in this tab or (on click) a new tab (1 files)
- `5b3f7cc` Labs: equipment gallery with free-licence model photos (credited, not our lab); Devices hides demo robots, shows Not configured addresses (25 files)
- `b555b72` Labs: equipment gallery first on every lab page; per-lab items from the owner's list (UR5e, FANUC, 8x S7-1200, Proteus PCs, Power lab tanks/ (7 files)
- `fe97267` Operation Center: titled X/Y axes on every chart, refresh at most every 15 s, no re-animation; Access & Audit debounced filtered reload; e2e (4 files)
- `6918880` System Devices: Screens card - door tablet link (Master ESP32), IoT wall in this tab or new tab, lab-network and this-computer addresses (1 files)
- `0ff23a5` Equipment gallery: fixed 4:3 photo frames so a tall photo no longer stretches the row (1 files)
- `b8b8b88` Lab page: equipment gallery directly under the lab title card (1 files)
- `118759f` Robotics Lab gallery: owner's own photos of the UR5e, FANUC ER-4iA and lab PCs (cropped, no people, metadata stripped) (6 files)
- `506ea57` nginx: gzip text responses (JS bundles 3-4x smaller, event lists ~15x) (1 files)
- `ef7f544` RFID: several cards per person (up to 5 on the door), remove one chosen card or all; revoked rows kept (5 files)
- `d2effa8` Consumable bin: fix crash on 'show' (float printed as %ld shifted the varargs; strlen on garbage) (1 files)

## 2026-10-13
- Conversations: 27 owner / 113 assistant messages in ChatGPT - Bsc. Smart Lab (3), Claude Code session 3b9b3107
- `833da46` Consumables: book NET, confirmed changes - lifting the container books nothing until it is back, a value must repeat before it counts, quant (3 files)
- `4367a69` gitignore: n8n.cloud export backup (duplicates automation/n8n/json) (1 files)
- `7ed95b5` Consumables: book whole pieces only when a reading sits cleanly on a count (drift/settling between counts ignored); notification '2 pcs take (7 files)
- `b141fe2` Consumables: count from the zero seen at the last lift (load-cell drift no longer leaves a count between two numbers and stuck) (2 files)
- `56e38b3` Consumable bin: report every 1 s so the portal confirms a change within ~1 s (1 files)
- `c3a7c80` Consumables: zero from a lift counts only when two empty-platform readings agree (1 files)
- `07d0375` Consumables: count by change (container stays on the scale), container zero follows creep between changes; recalibration restarts from the n (2 files)
- `ff8658f` Reusables: staff tabs 'Take an item' (bin opens for a chosen person, weight confirms) and 'Return an item' (recorded staff return with note) (9 files)
- `6dc509a` Reusables: staff take several items in one lid opening; the weight decides how many left (k of n recorded) (4 files)
- `6d83475` Security camera: YOLO26 on OpenVINO (CPU) - 105 ms/frame vs ~160 ms with ONNX Runtime, same people found on 23 lab frames; falls back to ONN (2 files)
- `68cf304` Reusables staff tabs: lists refresh every 4 s, on live events and after an error (a stale list offered an already-returned item) (1 files)
- `ed56b8d` Security camera: YOLO26 on the graphics card via DirectML (GTX 1650: 33 ms/frame end-to-end vs ~160 ms CPU, same people on 23 lab frames); f (2 files)
- `457a3ff` Security camera start: set up the DirectML (graphics card) and OpenVINO engines automatically when missing (1 files)
- `7d0d5b5` SecurityCam engine audit: isolated per-device benchmark, DirectML placement check, real-frame parity and per-stage replay tools; 7 engine-se (5 files)
- `d83c168` Lab test checklist for 2026-10-14 and robot.env example (UR5e IP, read-only) (2 files)
- `a2ae4cd` Lab checklist: re-ID check (1 files)
- `8b48ae1` Re-ID: fix cv2.dnn batch bug (embeddings wrong once the number of people changed) - one crop at a time; run on the GTX 1650 via DirectML, ON (4 files)
- `9471fdb` Re-ID pre-rollout audit: 7 more tests (correspondence, crowd changes, one failure, batch 1, GPU start-up failure), old-vs-new regression evi (3 files)
- `1b4e268` Knowledge platform (local): source registry with secret redaction, Obsidian vault generator, n8n workflow catalogue + drift, BM25 search, lo (9 files)
- `4087c29` Knowledge platform: live n8n state (read-only export, n8n defaults normalised), system hub notes, doc wikilinks, inactive n8n drafts, next-p (5 files)
- `1f4f59d` Knowledge history: local importers (git, Claude Code transcripts, ChatGPT export/share), secrets from .env/camera.env redacted, owner-review (3 files)

## 2026-10-14
- Conversations: 66 owner / 311 assistant messages in Claude Code session 3b9b3107
- `a39ac3a` Local agent: lookup/answer/investigate routes, compact evidence + streaming (first word 6.8 s vs full answer 24-68 s), fixed read-only tools (5 files)
- `200ad01` Project knowledge in the portal (admins/staff): local knowledge service on 127.0.0.1:5199 (streaming, key-protected), backend proxy route, c (16 files)
- `f658619` AGENT.md: embedding model status (1 files)
- `d4e5685` Lab readiness 2026-10-15: UR5e collector never shows frozen RTDE data as live (link check, controller-timestamp dedupe, finite 6-joint valid (10 files)
- `5b47851` Visual foundation: post-login welcome intro (CSS, skippable, once per sign-in, ?intro preview, reduced-motion off), Smart Lab home /welcome  (11 files)
- `651e2e3` Graphify assessment (read-only): recommend native graph layer; nothing installed (1 files)
- `8f00d14` Knowledge agent: warm both models at service start, keep loaded 2 h (first question no longer waits for a model load) (2 files)
- `0a73c6a` n8n 01/03/05/07: repository now matches the live definitions (owner chose option b; live unchanged; previous versions in history and backups (4 files)
- `d1aaa17` Native knowledge graph (graph.py, evidence on every edge) used by investigate; camera: re-ID GPU choice survives a busy start-up, camera add (15 files)
- `c4390ae` CLAUDE.md (short project rules + map, from the toolkit audit); checkpoint: final night state (2 files)
- `3f5ba52` Checkpoint: final wording (1 files)
- `eb025f3` Checkpoint: reboot recovered via launch.bat; re-ID on GPU after a busy start-up verified live; no camera address in process list (1 files)
- `f6ca236` UR5e live: RTDE telemetry and digital twin verified at the lab (192.168.1.102, 48 Hz) (2 files)
- `d8abb81` UR5e LIVE_VERIFIED: joint-by-joint mapping, cable-pull stale in 2.0 s and automatic recovery, from the portal's event log (2 files)
- `046dae8` UR5e monitor: console prints a movement summary (path length) instead of the full trajectory; the path still goes to the portal (1 files)
- `c2da330` Camera: an error in one analysis pass is logged and analysis continues (it stopped for good at the lab after 45 passes); reported fps drops  (2 files)
- `381286f` Camera start script refuses a second copy while port 5100 is in use (two services ran at the lab; the new one served nothing) (1 files)
- `b0376e4` Camera live at the lab: GPU engines verified, analysis-stall fault and double-start found and fixed, 60 s stable at 5 fps with 0 errors (1 files)
- `956fe26` stop_all.bat / restart_all.bat (close every Smart Lab window, docker compose stop - data kept); PCs: a standing person in front is not 'in u (4 files)
- `d2de096` Camera: fix NVIDIA driver crash (nvwgf2umx.dll access violation, 4x at the lab) - equipment search shares the live detector's GPU session in (2 files)
- `a25cfbd` Camera: switch off console QuickEdit at start - a click in the window blocked print() and froze analysis with no error (1 files)
- `f88a970` Lab record: camera driver-crash root cause, reproduction, fix and live verification (1 files)
- `c1215c0` Camera: name tags never cover each other (neighbour's 'Unknown' was drawn over Nour's name at the lab); named people drawn on top, tags kept (2 files)
- `94f1099` Identity: the face outranks the body look in the crossing fix - a track whose current face votes agree on its name keeps it, nobody takes a  (2 files)
- `c372d32` Lab record: identity swap (crossing fix overruled face) - evidence, cause, fix (1 files)
- `dfc2557` Lab test while the lock is not installed: door_test_entry.py (TEST entry, device DOOR_TEST, no door opened; --watch-face follows the door ca (3 files)
- `5e47123` Door naming: a new person counts as entering when their box overlaps a widened door zone (lab: entry recorded but the detector first saw the (2 files)
- `9950717` door_test_entry.py --exit: close a wrong test entry the normal way (EXIT_RECORDED, kept); used for USER3 after a door-camera false match (1 files)
- `f4f78f2` Door test: each door-camera recognition refreshes the test entry (10 s); camera logs every new person at the door with the waiting entries a (2 files)
- `5369db9` Detector: re-measure the GPU before falling back to the CPU (idle GPU woke slowly at start-up -> openvino-cpu, 2 fps and broken tracks at th (2 files)
- `d1160eb` Identity: hand a lost name back to the only new person at that place even while they touch a neighbour, if the look matches (lab: Ali lost h (3 files)
- `45e87ed` Camera: zoomed re-detection inside unusually wide person boxes and where a named person was just lost - finds a person seated behind another (3 files)
- `2128015` Camera: zoom one person box per pass in turn as well (a width ratio missed Ali behind Nour at 0.67) (1 files)
- `f6ced49` Identity: home desk (owner's rule) - Eng. Hemaly's desk PC-09/PC-10 names him, only after the door or his face placed him in the lab and onl (4 files)
- `e977fbf` Door note written once per person (was every pass while standing in the door zone) (1 files)
- `98dcee8` Desk naming needs the person AT the desk at the desk's scale (front-row person overlapping the desk in 2D took Hemaly's name); max 2 zooms a (3 files)
- `b3e7dbe` Fix syntax error from the previous commit (identity log newline); 129 tests pass (1 files)
- `e7391c8` Camera speed: re-ID between 2 s refreshes only for people touching someone (all 8 every pass cost 63 ms); round-robin zoom every 3rd pass; t (3 files)
- `785b1cb` Camera metrics: tracking time split into re-ID / tracker / naming (track_parts_ms_p50) (1 files)
- `b5242e0` Camera speed: no re-ID for people under 80 px (their look is never judged; 13 people cost 138 ms); test (2 files)
- `c7499fe` Camera speed: zoom at a lost spot only when another person's box covers it (occlusion); an empty spot means they left (detect p50 140 ms wit (1 files)
- `c0862ec` Camera speed: one zoom per pass by priority (occluded lost spot > wide boxes in turn > round-robin); detect_main / zoom timed separately in  (1 files)
- `fcb4a99` Lab record: afternoon camera speed and identity work with measurements (1 files)
- `8409180` Camera: analysis 7 passes/s (was 5) - measured 6.96-6.99 fps, pass p95 106 ms, GPU 36 %, 0 errors with 4 people (1 files)
- `a67c981` Checkpoint: lab results 2026-10-14 afternoon (1 files)
- `9d424aa` Identity: a desk name yields to a newer door entry - the desk-sitter becomes Unknown and the person walking in gets the name (owner's rule); (2 files)
- `8c1dec3` Identity: locked profiles beat the desk - no desk naming while a named person was just lost at that desk, nor for someone whose look fits an (2 files)
- `7d15266` Desk naming: 2 desk-widths sideways (Hemaly sits beside his monitor box, 35 px off; front row still stopped by the size check); test with th (2 files)
- `b8561d4` Camera: drop thin duplicate boxes inside a person before tracking (19 px strip inside Hemaly's box made 'two people at the desk'); half-hidd (3 files)
- `842776e` Desk naming: only a CLEAR look match to another profile blocks it (an owner without a locked look was blocked by any profile) (1 files)
- `72c247d` Tracking: still tracks survive 6 s, look gate after gaps (fragmentation 12->4 on real footage); fresh-only elimination; desk names drawn as  (10 files)
- `82a76b5` FANUC ER-4iA live twin (read-only HTTP GET of /MD/CURPOS.DG, real page format, motion on robot's own joints, twin-only J2/J3 coupling, Schun (17 files)
- `802638b` Checkpoint: evening 2026-10-14 deploy, FANUC live, camera 2 next (1 files)

## 2026-10-15
- Conversations: 51 owner / 179 assistant messages in Claude Code session 3b9b3107
- `f365f5e` Dashboard performance and chart axis titles (8 files)
- `f7ded03` Robot control groundwork: ownership, checks, audit; UR5e Home as dry run only (10 files)
- `ff248fe` Face ID: automatic enrollment from the door stream, one detector pass (7 files)
- `96b98e9` Robotics Lab: cinematic card, technical gallery, Room 214 (5 files)
- `ea53d55` Digital twin: virtual workcell, modelled collisions, views and full view (15 files)
- `f5eaeff` Checkpoint: performance and face-speed missions (1 files)
- `8e6fa64` Login, welcome, navigation and the new Smart Lab symbol (9 files)

## 2026-10-16
- Conversations: 2 owner / 4 assistant messages in Claude Code session 3b9b3107

## 2026-10-17
- Conversations: 9 owner / 249 assistant messages in Claude Code session 3b9b3107

## 2026-10-18
- Conversations: 19 owner / 166 assistant messages in Claude Code session 3b9b3107

## 2026-10-19
- Conversations: 96 owner / 330 assistant messages in Claude Code session 3b9b3107

## 2026-10-20
- Conversations: 25 owner / 212 assistant messages in Claude Code session 3b9b3107
- `010f62c` snapshot before 2026-10-20 master mission (1935 files)
- `b8c5bdb` Door enclosure fit-test release, Face-ID self-service, camera-first GPU gate, docs (292 files)
- `a3a0da3` Evening dossier 2026-10-20: enclosure release, AI CPU vs GPU measurement (12 files)
- `3ac976c` Faster navigation: non-blocking 3D shader compile, hover pre-load, lighter Sessions tab (9 files)
- `de46ad9` Smart search, usernames, per-photo face review, instant Welcome skip (39 files)
- `07804cf` CAD: sketch snapping off during build (fixes FP test opening 21x16.2 -> 21x19 and missing 2nd R307 tie slot, found by an independent SolidCr (19 files)
- `c74ee3b` Door box 110 mm deep (wire gap 25 -> 45 mm), rebuilt body + assembly; washers/spacers in BOM; checkpoint with role-matrix and test results (48 files)

## 2026-10-21
- Conversations: 51 owner / 272 assistant messages in Claude Code session 3b9b3107
- `818fd65` Lab PCs on/off over the LAN by MAC (no agent needed): tools/lan_presence collector, /equipment/pc/presence, PC cards + Lab PCs grid; agent r (20 files)
- `66fa726` Door box: owner's 0.3 mm fit rule (Neptune 4) - M3 3.3, slots 3.3, keyhole 4.3, LED 5.3, buzzer 12.3, glands 12.8/16.3, pockets +0.3; insert (42 files)
- `f63cb59` Live PCs and sharing: admin = master on sign-in, instant Stop (410 + share_state push), pc_state pushes, students share after admin approval (42 files)
- `9eae4df` Open tabs pick up new portal versions (reload on next page change + banner); share preview keyed per share so it can never stay on 'Waiting  (4 files)
- `3c3faac` Share screen tab in the sidebar (all roles); shared screen visible inline on old Chrome (no aspect-ratio: explicit heights + @supports fallb (4 files)
- `aa0d739` Robots & PCs scrolling: 3D redraws only on real value changes, memoized twin, no drawing off screen, 3D starts on click / resting pointer (n (2 files)
- `bf0264e` Cameras: no view anchor / box re-alignment for 3 min after the stream (re)connects - PTZ power-on sweep re-aligned camera 2's boxes to the w (2 files)
- `2a7e934` Security boxes: smallest box 0.5 % of the picture (was 2 % in the page, 1 % in the API) - far monitors on camera 1 could not be boxed; page  (2 files)
- `e1e8528` Camera /state lists the current boxes only (deleted boxes stayed listed until a restart; the portal was not affected) (1 files)
- `0da62db` Checkpoint: cameras re-boxed by real PC numbers, two-camera PC links PC-05..13, PTZ start guard, thesis snapshots (local only) (1 files)
- `869d867` Cameras: same-desk pairing - a person seated alone at a linked PC (owner-verified desk_map.json, PC-05..13) on both cameras is the same pers (4 files)
- `f2b2884` Robots & PCs smooth: movement list draws the newest 40 (was up to 1000 rows = 77 % of the tab's elements), tab kept mounted after the first  (5 files)
- `5d76dfa` Cameras: boxes under 8 px are compared over an 8 px area (Security_Camera_2 stayed learning); Hemaly's desk = PC-04 + PC-01 after the renumb (3 files)
- `72bedff` Door TEST watcher: entry only when the door camera agrees (same name 2x within 5 s, no other name within 10 s) and the recognition is fresh  (2 files)
- `d6cf0ef` Cameras analyse up to 10 a second (was 7): measured 9.1 / 8.6 per s, GTX 70-76 %, 70 C, frame age unchanged; live views 25 ms pause (~15 pic (3 files)
- `b3dc744` Cameras: desk guesses (Eng. Hemaly? / TA? (desk), shown only), PC in use held only by a seated person, look tie-break for close floor pairin (10 files)
- `02cb119` Cameras: the look leads close pairings (measured: veto above 0.65, clear match at or below 0.40 with a 0.20 margin pairs up to 2 m and may c (3 files)
- `f69a037` Checkpoint 2026-10-21 18:45 (lab closing): two-camera naming results and open items (1 files)

## 2026-10-22
- Conversations: 1 owner / 5 assistant messages in Claude Code session 3b9b3107
- `a436443` Robot twin: static scene parts memoized (a joint update re-renders the arm only) - not yet measured/deployed; smoothness E2E can drive both  (3 files)
- `42c198f` PC in use from seats + LAN power (camera prefers the PC that is on; seat_capture.py records seats), PC tiles: Seated - PC off / Off; UR5e Lo (10 files)
- `497f39c` Checkpoint 2026-10-22: fixes deployed, next lab steps (1 files)
- `c22adad` Freeze recorder: staff browsers report long frames (> 150 ms) with Chrome Long Animation Frames attribution + page context; memory only, adm (6 files)

## 2026-10-24
- Conversations: 56 owner / 131 assistant messages in Claude Code session 3b9b3107
- `02b2da9` Door box: coupon result - NFC card reads through the 1.5 mm skin (owner, printed coupon) (1 files)
- `e9f1dfd` Door box: owner's caliper measurements + 0.3 (NFC 42.85 x 40.52, LED 5.0, buzzer 12.2, TFT glass 33.7 x 43.4 / PCB 57.7, buck, relay 57.66 x (1 files)
- `9918bfa` Door box: fingerprint stands out 15 mm (20.0 x 23.5 opening, sleeve, back stop, clamp screw), LCD landscape centred, raised text 8/9 mm; bod (3 files)

## 2026-10-25
- Conversations: 6 owner / 49 assistant messages in Claude Code session 3b9b3107

## 2026-10-26
- Conversations: 26 owner / 257 assistant messages in Claude Code session 3b9b3107
- `9409a09` Cameras: YOLO26s 544x960 + ByteTrack-style low-confidence stage + new-track threshold + part boxes + 416 zoom model (reviewed lab clips: HOT (21 files)
- `3a68d82` Scan the lab: phone camera in the AI assistant - QR asset markers decoded on the phone (exact record key, never appearance), live asset card (23 files)
- `b2d6ae5` UR5e Local mode: automatic Home after idle (cancellable countdown in the twin, same guarded path, off by default); hardware STOP relay on th (15 files)
- `2a0b760` Voice in the AI assistant: push-to-talk (Talk in the launcher or the mic) -> local Whisper base.en on the CPU (1.3-1.5 s, one at a time, cam (11 files)
- `a1470ed` Audit fixes + priorities: booking race closed (per-lab advisory lock; two simultaneous overlapping bookings were both saved), /equipment fix (20 files)
- `53a35d0` Evaluation tab (priority B: measured before/after with conditions and sources, unmeasured items shown as such); briefing flags accounts stil (7 files)
- `5be385b` Final implementation audit 2026-10-26 (verdict: ready with documented limitations; backend 626 passed) + checkpoint (2 files)
- `cf81823` OPC UA server (read-only): portal snapshot feed (key, no personal data) mirrored into an OPC UA tree every second; localhost anonymous, LAN  (8 files)

## 2026-10-27
- Conversations: 24 owner / 228 assistant messages in Claude Code session 3b9b3107
- `922187c` Portal: camera 2 on the IoT Dashboard floor plan (own status + people count, never summed); screen share no longer waits forever when the sh (10 files)
- `a970cc1` Security + launcher + local AI: no published passwords (seed from SEED_*_PASSWORD or random, set_password.py hidden prompt + audit, docs cle (22 files)
- `6307d85` Scan the lab: people boxes on by default (owner) (2 files)
- `d1bd5a7` Scan the lab: picture QR markers (the icon IS the code: camera, shield, robot arm, door, PC, server, sensor, bin, tool; halftone modules, er (8 files)
- `3634647` Live camera target layer: structured live data per asset (UR5e six joints in deg + velocity, TCP, robot/safety mode, LIVE/STALE/OFFLINE/NO_T (3 files)
- `6c6dc25` Owner fixes: lab floor with the real PC numbering (engineer desk PC-01/04, front desk PC-02 + PC-03 removed, central table PC-05..09 and PC- (4 files)
- `a70512f` Markers redesigned: dark navy cards with circuit traces and a category glow, the asset motif built into the QR modules (robot arm, camera, d (7 files)
- `b929c62` No more blank-then-appear: robot stills ship with the portal (instant picture on every browser/address, also in Full view, until the 3D has  (5 files)
- `1848fe3` Live Smart Lab camera: live chips pinned to each marker / person in the picture (positioned every frame, smoothed), tap to select, expanded  (15 files)
- `bc843aa` Asset-shaped QR markers: the code itself forms the object (camera body + viewfinder + lens ring of real modules, door frame + leaf + handle, (4 files)
- `b2bd04f` Checkpoint 2026-10-27 14:10: live camera + shaped markers deployed (1 files)
- `b592794` Offline acceptance test: tools/offline/offline_check.py (proves the internet is unreachable before a round counts; 13 local checks a minute  (2 files)
- `2084ffc` Enclosure appearance matching (hint only): local ORB + RANSAC against owner reference photos (backend/data/asset_refs, manifest of the 4 enc (6 files)
- `cc35347` Live camera: 'Which box is this?' - one frame against the enclosure photos, shown as a hint only (scan the marker for identity and live data (2 files)
- `91e0636` Advisory safety triage (15.2): one ranked list per lab from camera + robot + door + environment + access records (P1 hazard / robot moving w (6 files)
- `0c691ff` Owner's QR marker pack integrated: payloads checked against the live registry - 6/8 exact (CAM_LAB01, FACESRV_01, MASTER_LAB01, PC_ADMIN_LAP (20 files)
- `6d32b08` IoT Dashboard wall redesign: one-row header (5 columns - Portal/Esc, title, scope, health, clock + full screen; nothing wraps), three column (4 files)
- `2b79386` Whole-lab time slider backend (15.3): GET /labs/{id}/at?t= - the lab at time t rebuilt from recorded history only (door sessions open at t,  (3 files)
- `796d2b2` Owner fixes: spoken answers on the laptop (audio unlocked inside the click, one reused player, first sentence synthesised alone, 'Play answe (12 files)
- `c709197` Object-shape markers in the owner's Canva reference look: silhouette filled with dark module texture on white, category-colour outline (Open (1 files)
- `138762d` Phone live camera: spoken answers on iPhone (voice status read on every device, not only where recording works - answers had fallen to the b (3 files)
- `f27be41` 10 object-shaped QR images delivered (SmartLab_10_Scannable_QR_Images.zip): payload manifest from the live registry (6 pack payloads verifie (2 files)
- `88a9b37` Illustrated asset markers (owner: door ajar with the QR on the door, 3D 6-axis robots, camera lens = QR): 10 drawings around the real flat Q (13 files)
- `eef3a26` Faster portal + more instant answers. Scrolling: no live backdrop blur behind every card / top bar / sidebar / lab chips and the page light  (8 files)
- `024ebb5` Markers: the owner's 10 object pictures with the real QR in each white panel (door: sticker below the handle), upscaled 6x with the QR drawn (13 files)
- `f6f1d1f` Agent upgrades: proactive suggestions (CONFIRMED offline / low stock / recurring vs POSSIBLE sensor anomaly / occupancy change, evidence + t (12 files)
- `c99893c` Answer feedback (thumbs up/down, audit log, anonymised staff review by route); Project knowledge citations show each source's last-change da (8 files)
- `58e477c` Reliability briefing: cache only the service probes 30 s (the briefing itself stays per call - it marks repeated items); full suite 704 + fi (1 files)
- `6ff1904` Phone scan: camera / face / appearance / voice-transcribe calls run on worker threads instead of the event loop (they held every other reque (3 files)
- `71bf051` Instant 'how to improve / what is wrong with <device>' from its own records (status, 30-day use, faults, robot events, alerts + playbook ste (21 files)
- `971e9f1` Assistant books and cancels: 'book LAB_01 tomorrow 10-12' / 'cancel my booking' -> an instant proposal (no model) with Confirm; Confirm call (5 files)
- `0ffe811` Navigation: pointing at a sidebar link also downloads that page's code, idle prefetch starts at 0.4 s (was 1.5 s); System analytics keeps th (4 files)
- `358bbb5` Load: short shared caches (one computation per key, concurrent callers wait for it) for the wall screen 2 s, camera list 2 s, issue summary  (11 files)
- `1dd5c19` Instant: 'open maintenance issues' phrasings (+ explicit critical count) and 'tell me about <lab>' (free/booked, inside, environment; alerts (3 files)
- `8f893a0` Backend concurrency: the sync-route worker threads (40) equalled the DB pool (40) - the auth dependency held a connection while the route wa (7 files)
- `b8fafe9` Welcome page: 3D scenes stay once built (were rebuilt - WebGL + shaders - every time they scrolled back in); no backdrop blur, no colour fil (3 files)
- `a4ff01b` AI model down: fail fast with the real reason (connect timeout = not running; a model known down < 20 s ago answers at once), health probe c (1 files)

## 2026-10-28
- Conversations: 42 owner / 151 assistant messages in Claude Code session 3b9b3107
- `59330b0` Phone camera: Tell me more + mic float on the camera picture (owner: had to scroll down to press them) (1 files)
- `0c05768` Box look-up: runs by itself every 3 s while no marker is in view (owner: 'it did not detect it, only the QR'), result shown on the picture;  (2 files)
- `f297c6b` Phone camera: switching camera clears the selected target; a selected person who left the picture no longer blocks the marker in view (owner (1 files)
- `02df347` Phone camera: box verdict fades after 5 s (a bin verdict stayed on screen over the owner's face); the automatic box check really runs every  (1 files)
- `9ef06ec` Box look-up draws a dashed frame around the matched points (owner: message but no frame); visual AI plan (owner's 12-class round one, data r (6 files)
- `4f935eb` Visual AI round one tooling: prepare.py (video -> frames per session, near-duplicates skipped; session-based 70/15/15 split with frozen 12 c (2 files)
- `83753e1` Status report 2026-10-28 (1 files)
- `af6fbbb` Phone camera: 'Tell me more' under a fresh box look-up verdict answers at class level (what it looks like, unconfirmed, scan the marker for  (1 files)
- `42d09cf` Phone camera: a failed marker lookup retries after 2 s (was 5 s) - the owner's test hit a 30 s backend restart (1 files)
- `a92f2a2` Box look-up frame wraps the WHOLE object: the owner-checked whole-station box of the matched reference photo is carried into the phone frame (2 files)
- `1be41ab` Box look-up learns only the object (reference keypoints inside the whole-station box): the owner's face had matched the bin at 58 points thr (4 files)
- `37498f7` Phone camera Refresh: stopping speech now finishes the pending answer (the paused player never fired 'ended' - the page stayed on 'Speaking. (2 files)
- `28a772a` Phone camera Refresh: automatic box check waits 6 s after Refresh (the bin still in view was re-found at once), 'Refreshed' note (1 files)
- `f6516b4` Phone camera: watchdog resumes the live video when iPhone Safari pauses it as the spoken answer plays (picture stuck on the bin), also on Re (1 files)
- `ac177c6` Phone camera Refresh = Stop + Start camera (same camera): speech, frames, verdicts, tracks, selection and the voice panel all reset - a clea (1 files)
- `036a9f0` Phone camera: Live history under the camera - one timed line per new detection (person / named person with face %, QR read, look-alike recog (1 files)
- `bdf968f` Live history: a symbol per asset type (robot, door, cameras, PC, bins, environment, PLC, ...) and a face for a named person (1 files)
- `2d1927b` Phone camera: speech no longer cut mid-answer (the video watchdog waits while an answer plays and resumes the video after it; speech paused  (2 files)
- `605c654` Phone camera: live caption of the spoken answer on the picture; mic state shown on the picture (red while listening, clear message if blocke (1 files)
- `4a8ebcf` Phone camera: glass controls on the live picture (switch camera, pause, which box, stop at the side; refresh, Tell me more, mic at the botto (2 files)
- `006e9e9` Phone camera: re-layout the video on every new stream/size (iPhone drew a switched camera small); glass buttons without backdrop blur (lag o (2 files)
- `f938b5b` Bin reference 28: side view at ~1 m with the QR turned away (owner's 5:55 test, 8-17 points) (1 files)
- `019213b` Phone camera: live captions type each sentence in step with the voice (revealed by audio playback position; browser voice by word boundaries (2 files)
- `bf7f1ca` Responsive portal: shared rules (controls never wider than the screen, long ids wrap, data tables scroll inside their card on phones, 40 px  (7 files)
- `8a7f088` Touch targets: header controls 40 px, inline text links and link-buttons get a taller tap area on coarse pointers (1 files)
- `62117c7` Fix letter-by-letter text on phones (overflow-wrap anywhere shrank flex items to one letter; now break-word, ids/mono only anywhere) + audit (8 files)
- `31a1262` vision_train: fetch_drive.sh polls the owner's Drive folder and downloads the training zip into data/raw_owner (git-ignored) (1 files)
- `7d66d27` click_everything: phones/tablets open pages by address (closed menu made link clicks wait 30 s), status dots no longer count as loading, wai (1 files)
- `6239ce1` CLAUDE.md: when to use the chrome-devtools / context7 MCPs, e2e scripts, gh and psql (MCP audit 2026-10-28) (1 files)
- `fa3c699` fetch_drive.sh: drop --remaining-ok (not a gdown option; every poll failed) (1 files)

## 2026-10-29
- Conversations: 33 owner / 116 assistant messages in Claude Code session 3b9b3107
- `a962057` Reusable-bin detector behind "which box?" + phone-path speed-ups (17 files)
- `7075d8e` Deploy bin detector (round-3 YOLO26n, ONNX 9.8 MB, conf 0.6): unseen scenes 14/15, no-bin 5/429 (patches 0/8, lab frames 0/221, COCO 5/200); (3 files)
- `8059f78` Checkpoint 2026-10-29: bin detector live, round 4 training, Windows Update restarts (1 files)
- `7fe4e9d` Bin detector: round-4 YOLO11n (+ lab-camera negatives), conf 0.4 - unseen 14/15, no-bin 0/429 (top no-bin score 0.19), live 14/15 / 0/44 at  (2 files)
- `05b787e` Checkpoint 2026-10-29 17:10: round-4 YOLO11n deployed (0/429 false) (1 files)
- `b52291d` CLAUDE.md: local n8n MCP (n8n-lab) is read-only; write/run tools denied in user settings (1 files)
- `312ce6c` Colab notebook for one-object training (default TP-Link switch): Drive zip -> HEIC->JPG (no GPS) -> YOLO-World boxes + contact sheets -> YOL (3 files)
- `d0bbe92` Colab notebook: videos in the zip are used too (2 frames a second) (3 files)
- `fdda4dd` Fix alert deadlock (one advisory lock for all alert writes - per-fingerprint locks deadlocked on two camera alerts and stalled the backend); (2 files)

## 2026-10-30
- Conversations: 3 owner / 9 assistant messages in Claude Code session 3b9b3107

## 2026-11-02
- Conversations: 16 owner / 74 assistant messages in Claude Code session 3b9b3107
- `9074905` Monitoring-only robots, several detectors at once, bin round 5 + router/switch model (22 files)
- `fa47ebd` Lab-wide dataset (12 classes): contact-sheet review rejections, bin/switch/router from the hand-checked rounds (no train/test leak), cameras (3 files)
- `d84c21d` AGENTS.md / GEMINI.md: shared rules for Claude (implementation) + Gemini (review-only, docs/reviews), separate worktree (3 files)
- `873d7c1` Fixes from the Gemini review (docs/reviews in review/gemini): zoom crop = the on-screen part (portrait kept full height), zoom reset on stop (4 files)

## 2026-11-03
- Conversations: 67 owner / 275 assistant messages in Claude Code session 3b9b3107
- `f5ac0ab` P0/P1 post-lab fixes (Gemini MASTER-HANDOFF-20261103, verified item by item) (16 files)
- `0985cd4` allow_firewall.bat: fix the Python-path quoting that stopped the script before any rule was written (owner's admin run 2026-11-03); rules ve (1 files)
