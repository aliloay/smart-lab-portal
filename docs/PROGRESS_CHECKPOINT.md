# Progress checkpoint - Smart Lab master completion mission

## Checkpoint 2026-10-20 ~21:30 (home, cameras OFFLINE) - committed, NOT pushed, nothing deployed
| Done | Evidence |
|---|---|
| Role matrix (`e2e/role_matrix_perf.mjs`, 1 trial, live portal): admin 19 / staff 16 / student 8 sidebar routes, 0 refused, 0 console errors; cold content 0.29-0.90 s, warm 52-267 ms; search 1.2-6.2 ms, right first hit for lab1/robot/fanuk/door/oscilloscope | scratchpad role_matrix.json; only failures = camera frame.jpg 503 (cameras off) |
| RBAC spot check: student GET /api/users -> 403 | live |
| Door box deepened 90 -> 110 mm (owner: more room for wires): wire gap 25 -> 45 mm; front-panel envelopes z +20; washers + 5 mm spacers added to BOM | interference.txt NO INTERFERENCES (17 bodies); check_stl 4/4 OK; body 170 x 210 x 110, 370 cm3 |
| Release ZIP refreshed (old kept as *_pre-snapfix.zip); STL-only ZIP DoorEnclosure_PrintReady_STL_2026-10-20.zip | tools/cad/door_enclosure/ |
| Tests: backend 565 passed; camera 253; robot_monitor 41; knowledge 49; tsc + vite build; search_rank 9/9 | this session |

**Blocked / physical:** print + measure the FitCoupon (inserts 3.9/4.0/4.2, pilots, LED, buzzer, glands, FP opening,
NFC read through 1.5 skin); buy 1 x M16x1.5 + 3 x PG7 glands; drawings PDF still from 90 mm (HTML regenerated);
camera walk tests; assign usernames.

## Checkpoint 2026-10-20 ~16:30 (laptop at home, cameras OFFLINE - no stream) - committed, NOT pushed
Live deploy unchanged since `f5eaeff-dirty-20261020021246` (FANUC front facing, UR5e home start, Face-ID photo
self-service, GPU gate code inactive by default). Nothing deployed this round (CAD + docs only).

| Done | Evidence |
|---|---|
| Door enclosure fit-test release: researched dimensions (4 researchers; report `reports/Door enclosure component dimensions.md`), new panel mounts (TFT on its 4 holes, PN532 islands + 1.5 skin, R307 cradle + tie, buzzer cradle), fit coupon 180 x 150, centred text, STEP export, 14 component envelopes | `tools/cad/door_enclosure/out/interference.txt` = NO INTERFERENCES (17 bodies); `check_stl.py`: 4/4 closed + manifold; drawings PDF; `docs/hardware/DOOR_ENCLOSURE.md` |
| Speaker / PAM8403 removed from the wiring record (owner) | `docs/hardware/DOOR_MASTER_WIRING.md` |
| Tests: backend 554 passed; camera 253; robot_monitor 41; knowledge 49; pc_agent 5; tsc + vite build | this session |

**Blocked / owner:** print the FitCoupon first and check the parts (DOOR_ENCLOSURE.md section 7); the 3-run
sidebar benchmark needs E2E_PASSWORD in the environment (not passed on the command line); camera walk test at
the lab (TWO_CAMERAS.md steps), PC letter -> number map, Hemaly at the door; ESPs are unpowered on purpose.


## Checkpoint 2026-10-20 ~01:00 (laptop at home, OFF the lab network) - nothing committed, nothing pushed
Deployed: `f5eaeff-dirty-20261020004125` (/api/health). Cameras restarted with the new identity code (healthy,
reconnecting - no stream off the lab network). Report: `docs/reports/SmartLab_Engineering_Dossier_2026-10-20.pdf`.

| Done | Evidence |
|---|---|
| Desk rule only continues evidence (fixes the USER1/USER5 conflict: 4 wrong-name episodes 2026-10-19) | test_desk_evidence_2026_10_19.py (fails on old code); 248 -> 253 camera tests pass |
| Coasting tracks keep names (seated flicker, NAME_ON_TWO_PEOPLE x24); hand-back from last-seen time, along the walking path | same tests + test_walk_handback.py |
| Carried-over (peer / desk) names give way to this camera's agreeing face matches (19:05 Ali/Nour case) | test_face_overrides_carried_name.py (fails on old code) |
| FANUC cell after the owner's photos: glass, doors, FANUC sticker, yellow side panels, controller, pendant, parts plate; "FANUC Robot ER-4iA" on the arm; robot right of the plate | screenshots; Front view = real front |
| Meshes compacted, same triangles: UR5e+Robotiq 10.4 -> 1.9 MB, FANUC 1.26 -> 0.26 MB (the 2026-10-19 "12.5 MB -> 75 KB" counted only index files) | scripts/compact_glb.mjs, stl_to_glb.mjs; before/after renders identical |
| Robots & PCs tab: cold 2.0 -> 1.5 s, repeat 0.78 -> 0.29 s; System tab 1.20 -> 0.27 s; Reliability 0.96 -> 0.08 s | e2e/robots_tab_perf.mjs, e2e/nav_timing.mjs |
| Bug fixed: evacuation alarm / emergency message missing on /welcome, /monitor, /wall, /report | e2e/emergency_message.mjs now passes |
| Bug fixed: a write followed by a reload within 1 s showed stale data (photo upload) | e2e/workflows.mjs 30/30 |
| Bug fixed (own regression, deployed 23:36, fixed 00:01): Welcome finale crashed (Kinova .STL through the glTF loader) | e2e/welcome.mjs 27/27 |
| Tests: backend 542 passed; camera 253; robot_monitor 41; knowledge 40; pc_agent 5; tsc + vite build; e2e on the isolated seeded copy all pass except navigation's 2 camera-503 messages (cameras stopped there); live: robot_readiness, monitor_security, reliability, welcome (admin/staff) pass | logs in the session scratchpad |
| Load (isolated, simulated): 0 errors, API p95 < 220 ms (summary 1 sample 525 ms), 2 sim cameras 6.5/6.9 fps, RSS flat | tools/perf/load_simlab.py |

**Next / owner:** walk tests at the lab (TWO_CAMERAS.md 2026-10-20 steps); a 2-person session for appearance data;
PC letter -> number map; Hemaly at the door (USER5 template IS loaded); why no ESP node reported since 04:00
2026-10-19 (power / Wi-Fi / portal address); door wiring values to measure (docs/hardware/DOOR_MASTER_WIRING.md);
**change the admin password** (it equals the public demo seed password in the repo); AI answers 51 s on CPU (owner's
GPU-for-cameras choice).


Latest checkpoint: 2026-10-14 ~16:30 (local, at the lab). Branch `offline-router-door-photos`. Nothing pushed.
Resume = read this file, `git status`, `git log --oneline -6`, then continue at "Next".

## Done (with evidence)
| Item | Evidence |
|---|---|
| UR5e collector: frozen RTDE data never shown live; NaN rejected (422, was 500); rtde_check.py | d4e5685; 22 robot tests; new tests fail on old code |
| Camera: strict DirectML detector, engines in /metrics + portal chip | d4e5685; camera tests |
| Camera re-ID fell to CPU at a busy start-up (seen live 03:00) -> re-measure before fallback, logged | d1aaa17; regression test fails on old code, passes now; 103 camera tests |
| Camera password: not on the command line any more (env), masked in logs | d1aaa17; test_masking.py; **live-checked 07:40: no process shows the camera address** |
| Visual foundation (intro, /welcome, manifest, photo folder) | 5b47851; browser checks on dev and **live** |
| n8n 01/03/05/07: owner versions recovered byte-exact, then option (b) repo = live (owner delegated) | docs/N8N_RECOVERY_2026-10-14.md; backups/n8n-recovery-20261014/ |
| Portal deployed (owner approved) | /api/health ok; DB dump backups/smartlab_before_deploy_20261014-0158.dump |
| Agent warm-up (2 h keep-alive) | portal: first word 9.1 s (was 14.3 s), done 12.2 s |
| Native knowledge graph (graph.py), used by investigate | 418 nodes / 2,186 edges, 2 s build; 4 graph tests; 40 knowledge tests; re-ID question now reads vision.py |
| Test DB isolation: advisory lock, concurrent runs wait instead of deadlocking | two parallel runs: second waited, both 11 passed |
| Claude Code toolkit audit | docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md (measured baseline: ~506 k tokens re-read per request) |

## 07:33 laptop reboot - recovered
`launch.bat` restarted everything: portal health ok, n8n 26 workflows / 0 drift, knowledge service up, Ollama
models on CPU (0 VRAM). Camera service started with the new code: **detector directml-gpu1 (24 ms), re-ID
directml-gpu1 (12 ms/crop)** - the busy-start-up fix verified live (the camera itself is at the lab: camera false).

## Running / pending
* Full backend suite: 436 passed (434 + the 2 AI-local tests after pinning OLLAMA_CPU_ONLY in conftest).
* Knowledge service runs in its own window "Smart Lab - Knowledge" (current code, restarted 07:13).

## At the lab 2026-10-14 (all recorded in docs/LAB_TEST_2026-10-15.md)
* UR5e LIVE_VERIFIED (192.168.1.102, RTDE 48 Hz, J1-J6 mapping, stale 2.0 s on cable pull, auto-recovery).
* Camera LIVE: GPU detector + re-ID; driver-crash root cause fixed (shared GPU session + GPU lock);
  analysis 7 passes/s (pass p50 85 ms, p95 106 ms); zoom finds people seated behind others.
* Identity: door naming via TEST entries (`tools/door_test_entry.py --watch-face`, window
  "Smart Lab - Door test entries"); home desk USER5 -> PC-09/PC-10; face outranks look; hand-back while
  touching. Decisions persisted in tools/security_vision/recordings/identity_log.jsonl (git-ignored).
* Scripts: stop_all.bat / restart_all.bat.

## Evening 2026-10-14 (deployed 19:14, owner approved)
* Commits 72c247d (tracking/elimination/desk guess/monitor query) and 82a76b5 (FANUC live twin, two cameras).
* Backend + frontend rebuilt and restarted (DB dump backups/smartlab_before_deploy_20261014-1912.dump);
  /monitor live 97 -> 59 ms. Camera service restarted with the new tracker (camera powered off at lab close:
  it reconnects by itself).
* FANUC ER-4iA LIVE_VERIFIED read-only at 192.168.1.100 (twin moved with the pendant; ~3 samples/s).
  To confirm: J2/J3 coupling by pose; DIAG-009 controller battery to replace.
* Camera 2 (MC200) arrives tomorrow: docs/camera-identity/TWO_CAMERAS.md.

## Waiting for the owner / hardware
* At the lab: start the camera window (loads re-ID fix + masking) -> check `re-id on directml-gpu1`.
* UR5e: **LIVE_VERIFIED** - telemetry 48 Hz, J1-J6 mapping/direction, stale in 2.0 s on cable pull, auto-recovery (docs/LAB_TEST_2026-10-15.md). Next: camera.
* Photos -> frontend/public/lab + labVisuals.ts.
* Optional (owner): CodeBurn `npx` run, Ponytail lite trial; TikTok effect needs a screen recording. All work committed (c4390ae), nothing pushed.

## 2026-10-14 night - performance mission (uncommitted, awaiting approval)
- Load test: tools/perf/load_simlab.py + ws_clients.mjs, guide docs/perf/LOAD_TEST.md (isolated DB smartlab_loadtest_test, port 8100; container removed after the run).
- Fixed: Command Center reloaded all 8 endpoints on every live status message -> safety msgs 400 ms as before, status msgs at most every 3 s (13.5 -> 9.4 req/s, /monitor 0.8 -> 0.4/s). tsc + build OK; NOT deployed.
- No backend/DB bottleneck: /monitor 22 ms idle; under load the time is host CPU contention from cameras.
- Report: docs/reports/SmartLab_Status_Report_2026-10-14.pdf. Suites: robot 32, camera 148 passed.
- Next mission: ESP32-CAM face enrollment / door recognition speed (flash of the ESP32-CAM authorised by the owner).

## 2026-10-14 late - ESP32-CAM face speed mission (uncommitted, awaiting approval)
- Automatic enrolment: face server POST/GET/DELETE /enroll/auto (device key) saves steady, sharp, new-looking frames from the door camera's /analyze stream; refuses a face that is clearly another enrolled person. Portal: /users/{id}/face/auto; preview from the face server's frame (camera /snapshot only as fallback). /enroll: 1 YuNet pass instead of 3.
- Door decision logic, threshold 0.363, master/RFID/fingerprint untouched. Face server must be RESTARTED (approval) for this to go live.
- Firmware: /enroll upload setNoDelay + timing (source only). Core 3.3.12 builds break the camera (frame buffer malloc failed, PSRAM free) -> board restored from backups/face-speed-20261014/esp32cam_flash_before.bin; camera boots OK. Needs the earlier 3.3.x core (install = approval).
- Laptop Ethernet to Smart_Lab was unplugged: no live camera<->laptop test yet.

## 2026-10-16 - ALIoT upgrade, round 1 (deployed, uncommitted)
- System analytics: `GET /api/analytics/system?days=` + `/analytics/kpis` (backend/app/services/system_analytics.py) - daily series for door, environment, safety sensors, robots (SIM labelled), consumables weight, inventory tx, camera events, PC hours, n8n deliveries, alerts; freshness live/stale/offline/never per source; KPI catalogue. Page /admin/system (frontend/src/pages/SystemAnalytics.tsx), sidebar "System analytics".
- AI agent: staff intent "system" answers data-source health + 7-day totals from system_analytics (no LLM), link to /admin/system.
- Demo /demo: 12 scenarios in 5 groups (door, smoke, evacuation, robot, bin, n8n, vault, AI) - still client-only, nothing recorded.
- Lab page door scene (components/visual.tsx DoorSchematic): red door opens only when reported open; lights = real device state.
- nginx: /api/knowledge/ 600 s, unbuffered (fixes "network error" on long investigations).
- Tests: backend 461 passed; new tests/test_system_analytics.py (4). DB dump before deploy: smart-lab-backups/smartlab-before-system-analytics-*.dump.
- Next: Reports Centre (CSV/PDF per subsystem), cross-system incident timeline, inventory discrepancy view, PC telemetry adapter (IT approval pending).

## 2026-10-17 - readiness round (performance, AI speed, UR5e master controls, PC actions, lab images)

Deployed and checked on http://192.168.1.200 (backend + frontend rebuilt; db/n8n/cameras untouched).
- Lab images: Power (LAB_08), Design (LAB_09), Fashion (LAB_11) card + hero + gallery; Power gallery has no SCADA item.
- Performance root causes: (1) `/system/status` probed the internet inline (2 x 1 s timeouts, holding a DB
  connection) -> background thread; (2) face-server / ESP32-CAM probes inline every 15 s (1.0 s spikes on
  `/devices`, `/labs/{id}`) -> background refresh; (3) DB pool 5+10 for ~20 parallel dashboard requests -> 20+20;
  (4) duplicate identical GETs (summary x2, system/status x3) -> shared in-flight GETs in `lib/api.ts`.
  Measured: login->app 3.6 s -> 0.95 s; `/api/devices` 40 sequential calls all 18-45 ms (was 1.0 s spikes);
  sidebar navigation route 80-130 ms, data 140-200 ms median. Scripts: `frontend/e2e/perf_routes.mjs`, `perf_nav.mjs`;
  results `docs/reports/perf_before.json`, `perf_after.json`.
- AI: project/technical questions answered from the knowledge index ("lookup", cited passages, no model):
  ~100-110 s -> 0.12-0.45 s. Lab-data questions already instant (30-100 ms). KB rebuild is incremental (208/7449 chunks).
- UR5e master controls (DRY RUN - nothing sent): verified Home pose [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27] deg,
  Home via URScript movej in live mode only, state from joint feedback, global STOP (any staff, latch, priority),
  admin recovery, E-stop disclaimer. FANUC separate (UNAVAILABLE). docs/ROBOT_CONTROL.md has the lab checklist.
- PC actions: open/close approved app, lock, log off / restart / shut down (admin, confirmed, 60 s warning),
  QUEUED/EXECUTING/COMPLETED/FAILED/EXPIRED from the agent's own result; audited. No PC enrolled yet.
- Tests: backend 466 + new (robot control 29, equipment 13) pass; tools: robot 37, knowledge 40, vision 163; tsc + vite build OK.
- Open: physical validation at the lab (UR5e cable/IP + commissioning, FANUC interface, MC210 camera 1 at uni,
  PC agent install on lab PCs). ROBOT_CONTROL stays dry_run until the owner signs off.

## 2026-10-17 (afternoon) - 8 upgrades round (all deployed on http://192.168.1.200)

- System health: background probes (`app/services/health_monitor.py`, parallel, every 10 s) - /system/services and
  new /system/health never wait on a probe; ONLINE/DEGRADED/STALE/OFFLINE/UNKNOWN/SIMULATION, last OK, failing since,
  guidance; robot collector without joints = DEGRADED. Page: System analytics (top).
- PCs: viewer picks monitor (agent enumerates monitors) + quality/fps; view start/end audited; sharing to selected PCs;
  browser sharing = picker -> local preview -> Go live. Agent 0.5. No remote keyboard/mouse (documented: RDP shadow).
- Incidents: migration a9d4e7c1b305 (additive: alerts.state/ack/owner/resolution + incident_notes), applied after a
  verified dump + restore drill (smartlab_restore_drill: counts match, upgrade/downgrade/upgrade OK). Page /admin/incidents.
- Anomalies: rules + sensor-fault + robust 7-day baseline on ENV_LAB01 (no ML - documented). Found: flame detector active
  in 17% of readings over its history. /analytics/anomalies cached 60 s.
- Reports Centre (Reports page): 7 exports (CSV / print-PDF, source + warnings), cross-system timeline (co-occurrence =
  timing only), inventory discrepancies, equipment lifecycle (overdue / maintenance / faults).
- Security: authorization sweep test over all 258 API routes (anonymous refused); login throttle already existed.
- Evidence: `py -I tools/evidence/run_evidence.py` -> docs/reports/evidence_<ts>.md/json (classes REAL_HARDWARE /
  LIVE_SYSTEM / OFFLINE / SIMULATION). Latest: 32 pass, 12 fail (devices off/away), 9 n/a, 2 simulation.
- AI: project questions 0.13-0.45 s cited lookup; full answers stream sources at 0.1-1.3 s, first word 8-17 s (CPU model).
- Tests: backend 492 passed; tools 37/40/163; tsc + vite OK.

## 2026-10-17 (evening) - continuation round
- PC agent 0.6: Pillow-free capture (Windows GDI + OpenCV, already installed), DPI-aware monitors, 1 s poll.
  Live-verified with this laptop as the admin/master PC (PC_ADMIN_LAPTOP, id 13): preview first frame 1.7 s, 2.2 fps,
  monitor 1/2/all, wall, close stops frames, agent restart -> frames again in 1.3 s, browser share to a selected PC,
  master-PC share (first frame 0.5 s), Stop ends both; audit rows present. `start_pc_agent.bat` + agent.env(.example).
  Fix: "View all screens" now shown when the only PC is the master PC.
- Anomalies: fixed Row.t bug in sensor series (timestamps were rows); flame finding now states activations and the
  longest run. Flame history: 642/678 active readings in one 3 h block on 2026-10-09 16-19 h - check physically.
- Incidents page: "group similar" + provenance labels (display only; nothing resolved).
- AI: knowledge agent k 4 -> 3 (bench 13 q: facts 9/12 -> 10/12, median first word 8.5 -> 4.4 s, total 12.9 -> 7.5 s);
  answer cache in serve.py (same question + same index version -> instant). Eval set +2 questions (UR5e Home, STOP).
- Backend: backup status read cached by file mtime; refresh_liveness throttled 3 s (LIVENESS_THROTTLE_S; tests 0).
- Evidence: 35 pass, 12 fail (all hardware off/away), 7 n/a, 2 simulation. Lab steps: docs/LAB_READINESS_2026-10-18.md.

## 2026-10-17 (night) - camera-wide incidents, split live view, robot controls in Equipment, fleet card fix
See docs/LAB_READINESS_2026-10-18.md "Update 2026-10-17 night" and docs/INCIDENT_REVIEW_2026-10-17.md.

## 2026-10-18 - reliability, identity, robots readiness, AI vs cameras (deployed; uncommitted)
Start here next time: docs/OPERATIONS.md (runbook), docs/LAB_GO_NOGO_2026-10-18.md (physical tests),
docs/BACKLOG.md (open items), docs/SECURITY_FINDINGS_2026-10-18.md.
* Robots: UR5e Home = pendant program `home.urp` (load + play, completion from joint feedback); readiness
  checklist; STOP latch survives backend restarts (audit log); FANUC identity + 220 installed options from the
  controller's own SUMMARY.DG (DEMO list empty), motion BLOCKED; 10-step plans in docs/ROBOT_CONTROL.md.
* Cameras (tested offline + live test instance; take effect when the camera services restart): reconnect
  backoff + FFmpeg timeouts + stream states; real CPU / private memory / GPU in /metrics; above-normal priority;
  identity: door entries need "at the door when first seen, alone", posture changes keep the track, staged
  association, crossing re-deals flagged for review, cross-camera states bug fixed. Simulated bench
  (tools/security_vision/scenario_bench.py): 180 runs, 0 false-name frames, 0 name switches.
* Incidents: grouping by fingerprint (occurrences, last seen, reopen), MITIGATED state, escalation on repeats,
  alert quality; migration d5e8b2c4f917 (additive) applied after an isolated restore + migrate drill.
  Fixed: resolved camera alert broke the next camera event (HTTP 500); stale offline incidents; camera "no
  picture" incident.
* Reliability centre (/admin/reliability): briefing, dependency graph + what-if (simulation), drift vs
  backend/app/config_baseline.json, request performance + objectives, alert quality, backups + restore drill,
  action policy; incident investigation (ranked explanations, correlation not proof); global search (Ctrl+K);
  sidebar regrouped (no page removed; Robots + Reliability added).
* AI: status questions answered from the records (44-142 ms instead of ~50 s); LLM 4 threads, one answer at a
  time (camera analysis held 6.6-6.9 fps during an answer vs 4.6 avg / 1.7 min before); knowledge embed
  keep-alive 2 h.
* Tools: tools/evidence/clock_check.py, restore_drill.py, run_evidence.py (extended), tools/deploy/deploy.py
  (version stamp, smoke tests, automatic rollback).
* Evidence run 2026-10-18 11:22 UTC: PASS 41, FAIL 13 (all physical devices not connected here), NOT_AVAILABLE
  7, SIMULATION 3, PHYSICAL_VALIDATION_REQUIRED 4, BLOCKED 1 (docs/reports/evidence_20261018_112213.md).

### 2026-10-18 14:50 - final deploy + engineering dossier
* Backend suite 529 passed / 0 failed (18 min, smartlab_test).
* Deployed with `tools/deploy/deploy.py`: version `f5eaeff-dirty-20261018144505`, quick tests, schema at head, 7 smoke checks, no rollback.
* Post-deploy load: single user p50 31 / p95 80 ms; 10 users + 2 live viewers p50 65 / p95 271 ms, frames p50 44 / p95 91 ms, 0 errors (`docs/reports/perf_final_20261018.json`).
* Dossier: `docs/reports/SmartLab_Engineering_Dossier_2026-10-18.pdf` (14 pages) from `docs/reports/dossier/*.html` + `evidence_index.json`; renderer `frontend/e2e/dossier_pdf.mjs`.
* Still open (owner / lab): admin password, camera-service restart (new code), clock sync, physical tests (LAB_GO_NOGO), ESP32 offline queue, commit.

### 2026-10-18 evening - ESP32-CAM rebuilt from source (kept), bin-0.3 on the consumables bin
* ESP32-CAM (COM7) now runs the repository source built with **esp32 core 3.2.1** (board `esp32:esp32:esp32cam`,
  installed in an isolated arduino-cli data dir; the main 3.3.12 install is untouched). Measured: 2.7-2.9 frames/s,
  upload+reply 360 ms, 0 failed (old binary: 2.17-2.65 frames/s, 394-463 ms). 2 frames in flight tested: 2.77 frames/s
  but 637-662 ms round trip + failures -> 1 kept. Backups: `backups/esp32cam-20261018/` (before + kept image).
* Consumables bin (COM9) runs **bin-0.3** (loaded-creep following, restart keeps the count, correct hx711 flag);
  backup `backups/bin-flash-20261018/`. Count re-anchored to the owner's 30 (audited).

### 2026-10-18 late evening - full system on the bench
* Live f5eaeff-dirty-20261018232259 (migration b7c3e1f9a204 index). Backend 539, vision 213, e2e ALL PASS.
* All five ESP32 boards reporting; door Face ID path verified physically (3 grants, 2 correct denials).
* Open: master fingerprint/LED/camera-poll flapping on laptop USB power (check common ground / power from the
  5 V buck); security-camera services to restart for the new tracking code (owner: tomorrow); camera 1 + robots
  at the university. Report: docs/reports/speed_and_fixes_2026-10-18_evening.md.
