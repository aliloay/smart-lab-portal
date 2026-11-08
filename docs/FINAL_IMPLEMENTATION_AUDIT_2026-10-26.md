# Smart Lab: final implementation audit, 2026-10-26

Branch `offline-router-door-photos`, local only (**not pushed**). Audited at the home setup. The cameras, robots,
door and phones were **not physically available**: hardware behaviour comes from recordings, fake devices and mocks,
and is labelled that way.

All measurements were taken on the lab laptop:
* 12-thread CPU, GTX 1650 (DirectML), Windows 11.
* Backend in Docker with 1 Uvicorn worker.
* Measurements ran on an **isolated copy backend** (127.0.0.1:8100, database `smartlab_perf_test`, restored from the
  2026-10-25 dump). Tests ran on `smartlab_test`. The live database was never written.

Status words used below:
* **PASS**: verified by a test or measurement.
* **PARTIAL**: built, but acceptance is incomplete.
* **FAIL**: missing, or broken by evidence.
* **BLOCKED**: needs hardware, credentials, an approval or a physical test.
* **NOT TESTED**: no adequate evidence.

---

## 1. Executive summary

**Finished and verified in software.** Each item below has tests and measurements on this laptop:
* camera detector and tracker upgrade (offline benchmark on our footage);
* phone-camera "Scan the lab" (fake camera);
* local voice assistant;
* UR5e Local-mode Home/Stop and automatic Home (dry run only);
* hardware stop-relay firmware (compiled, not wired);
* screen-share Stop;
* portal speed fixes;
* booking race fix;
* Excel export, Lab Health Score, advisory headcount, AAS export, Evaluation tab.

**Not verified physically.** None of the following has run yet:
* the camera services with the new defaults;
* a real phone;
* a real microphone or accent;
* the UR5e agent against the robot;
* the stop relay on the robot.

**Not built.** FANUC Home/Stop, OPC UA server, identity-fusion study, visual safety triage, whole-lab time slider,
Apple Wallet .pkpass.

**Two unresolved high-priority security findings (section 7):**
1. The live admin and staff accounts still accept the passwords printed in the public README.
2. The live portal runs an older build (`c74ee3b`, built 2026-10-21): **none of today's commits is deployed**.
   Deploying needs your sign-in for the smoke tests.

**Verdict: READY WITH DOCUMENTED LIMITATIONS** for a supervised thesis demonstration on the software side. **NOT
READY** for unsupervised robot motion (dry run only, by design) or for production use until the published passwords
are changed and the build is deployed.

## 2. Requirement matrix

| # | Workstream / requirement | Status | Evidence | Files | Outstanding |
|---|---|---|---|---|---|
| 1 | Phone camera: HTTPS setup page, local CA, secure-context check | PASS (software) | CA served at /smartlab-ca.crt; private key moved out of the nginx mount (3a68d82) | frontend/src/pages/ScanSetup.tsx, tools/tls/make_local_ca.py | Real phone trust steps not tried |
| 1 | Markers -> exact record -> live card (timestamps, LIVE/STALE) | PASS (fake camera) | scan_lab.mjs PASS today: card 227-244 ms warm, 1.3 s first start; backend 13 tests | backend/app/services/scan.py, frontend/src/pages/Scan.tsx | Markers not printed / placed |
| 1 | People boxes (generic "person", never a name) | PASS (recorded footage) | scan_people.mjs today: 7.4 frames/s, rtt p50 54 / p95 95 ms, 0 errors, 0 busy | tools/security_vision /detect | Supported objects = people only (no other classes) |
| 1 | Start/Stop cleanup, hidden tab, privacy | PASS | 5/5 cycles track ended, 0 requests after Stop, hidden tab releases; frames not stored | e2e/scan_lab.mjs | |
| 1 | Real Android / iPhone compatibility, battery, network drop | BLOCKED | needs a phone on Smart_Lab | docs/SCAN_THE_LAB.md | physical test |
| 2 | Voice: local STT (faster-whisper base.en, CPU) | PASS (synthetic speech) | benchmark tiny/base/small: 0.76/1.28/5.0 s, WER 2.9/5.7/6.9 % | tools/voice/README.md | real voices/accents NOT TESTED |
| 2 | Voice: local TTS (Piper), sentence by sentence, browser fallback | PASS | e2e first audio 4.3-5.3 s after Stop; /speak 0.3-2.7 s | frontend/src/lib/voice.ts | |
| 2 | Push-to-talk, cancel, mic released, 30 s cap | PASS | voice_talk.mjs 3/3 PASS, mic_released true | frontend/e2e/voice_talk.mjs, components/ai.tsx | |
| 2 | Same permissions/tools; no door/robot commands | PASS | the transcript goes through /ai/ask or /ai/student/ask; voice routes need sign-in + hourly limit; 5 backend tests | backend/app/api/routes/voice.py | |
| 2 | Performance with cameras running | PASS (1 camera, recording) | camera 10.0 analyses/s idle and during 21 back-to-back transcriptions | tools/voice/README.md | two live cameras NOT TESTED |
| 3A | Security: seed credentials | **FAIL (live)** | read-only check: admin@ and ramy@ still accept the README passwords; the briefing now flags it (test) | backend/app/services/briefing.py | **owner must change passwords** |
| 3A | HTTPS / HTTP/2 / headers | PASS | live nginx: `http2 on`, TLS 443, CSP + Permissions-Policy, gzip, immutable assets | frontend/*.conf | |
| 3A | Secrets in the repository | PASS | no tracked .env/robot.env/camera.env/voice.env/secrets.h; key-pattern scan empty | .gitignore | |
| 3A | Privacy / retention | PARTIAL | event snapshots purged after 30 days; 1.3 GB of camera recordings kept locally with no retention; records kept indefinitely (owner's rule) | routes/security.py | owner decision on recording retention |
| 3A | Audit logging | PASS | AuditLog on robot commands, auto-home cancel, report export, voice limit rows | | |
| 3B | Evaluation section | PASS | Reliability -> Evaluation: measured / offline / not-verified rows with sources (test) | backend/app/data/evaluation.json, components/LabHealth.tsx | keep updated |
| 3C | IoT buffering + sensor quality | PARTIAL | quality per reading VALID/STALE/OFFLINE/OUT_OF_RANGE (existing); firmware queues events in RAM (32) and retries | services/environment.py, firmware/*/env_network.h | no flash store-and-forward; not changed today |
| 3D | Performance | PASS (see section 4) | | | |
| 3E | Identity fusion study | NOT TESTED / not built | camera identity rules exist; no study written today | | |
| 3F | AI agents and knowledge retrieval | PARTIAL | knowledge bench: right source 10/12, facts 10/12, lookup 165 ms, CPU model median 14 s; lab instant answers 0.04-0.21 s | tools/knowledge/agent.py --bench | Qwen vs Gemma benchmark not run; model answers slow on the CPU |
| 3G | Excel / PDF reports | PASS | Reports Centre: CSV, **Excel (.xlsx, stdlib writer, well-formed XML, About + Data sheets)**, Print/PDF | backend/app/services/xlsx.py | |
| 3H | Anomaly detection / inventory analytics | PASS (existing) | /analytics/anomalies, inventory discrepancies, asset lifecycle (existing tests) | | |
| 3H | Lab Health Score | PASS | 0-100 per lab, unknown parts left out with coverage; tests | backend/app/services/health_score.py | weights are a design choice, not validated with staff |
| 3I | Flight recorder / time-travel twin | PARTIAL | robot movements recorded and replayed in 3D (existing, e2e/robots_replay.mjs); cross-system timeline | | no whole-lab time slider |
| 3J | AAS | PASS | /api/equipment/aas.json: AAS V3.0 JSON, Nameplate + OperationalData per asset (test) | backend/app/services/aas.py | not imported into a BaSyx tool yet |
| 3J | OPC UA | not built | needs a server package + security model | | proposal |
| 3K | Hardware pilots | BLOCKED (by owner) | owner: no new hardware now; stop relay uses existing parts and is a proposal until wired | firmware/SmartLab_Robot_Stop | |
| 3L | Visual safety triage | not built | | | |
| 3M/N | Advisory emergency headcount | PASS | Emergency page: door record (named) vs largest single-camera count, advisory text (tests) | routes/labs.py /labs/headcount | |
| 3N | Wallet passes | PARTIAL / BLOCKED | "Save QR for Wallet" image/share exists; .pkpass needs an Apple Developer certificate | components/SaveForWallet.tsx | |
| 4 | Detection model selection | PASS (offline) | YOLO26s 544x960: recall 0.898 -> 0.923 on 363 reviewed people; RF-DETR-M 0.970 but 113 ms (too slow) | docs/CV_BENCHMARK_2026-10-26.md | |
| 4 | Tracking / partial body / continuity | PASS (offline) | HOTA 0.732 -> 0.779, IDF1 0.831 -> 0.874, ID switches 14 -> 12 (3 reviewed clips); part-box suppression | tools/security_vision/vision.py | not perfect; live check pending |
| 4 | Cross-camera handoff | PARTIAL | desk-pair rules and look-led pairing exist (10-21); no new cross-camera test today | | live verification |
| 4 | FPS / latency / resources | PASS (recordings) | two cameras 9.4/9.9 analyses/s, pass p95 115-129 ms (earlier today); now: 1 camera service 10.0/s, GPU 34 % | | camera services in the lab still run the OLD defaults until restarted |
| 5 | Navigation | PASS | nav_timing 40 warm visits p50 119 / p90 229 ms (baseline build p50 126 / p90 231); role matrix warm median admin 145 / staff 140 / student 100 ms | e2e/nav_timing.mjs, e2e/role_matrix_perf.mjs | /admin/access 1.1 s warm in one role-matrix trial (149-195 ms in nav_timing) |
| 5 | Polling / hidden tabs | PASS | hidden Monitor 0.77 -> 0.2 req/s, Security 0.5 -> 0.2 (only alarms stay live) | lib/api.ts, LiveCameraFeed.tsx, e2e/hidden_tab_polling.mjs | 61 page timers still exist (cheap while visible: 0.2-0.7 req/s) |
| 5 | N+1 queries | PASS | /equipment: fixed number of queries (test: <= 20 for 6 devices; was ~6 per device + all-time session scan) | routes/equipment.py | other lists not re-audited today |
| 5 | Auth contention | PASS | 20 sign-ins at once: p50 1.58 -> 0.94 s; /monitor during it p50 317 -> 156 ms, max 1167 -> 331 ms | core/security.py | |
| 5 | nginx delivery | PASS | HTTP/2, gzip (JS gz verified), immutable hashed assets | | |
| 5 | backdrop-blur / 3D / charts | PASS (existing) | 17 blur uses; Robots & PCs 60 fps after memoised 3D (10-22); perf_portal: 0 long tasks on the security page | | |
| 6 | Uvicorn workers / Redis | PASS (decision) | stay at 1 worker, no Redis: robot STOP latches, WebSocket hub and throttles are in process memory; measured load is served | | revisit with > 1 worker only with shared state |
| 6 | DB pooling | PASS | pool 20 + 20 overflow | db/session.py | |
| 6 | Booking conflict protection | **PASS (fixed today)** | bug reproduced: two simultaneous overlapping bookings were both saved; per-lab advisory lock -> exactly one (test fails without the lock) | services/booking.py, tests/test_booking_race.py | |
| 7 | Screen sharing Stop | PASS | share_stop_release 3/3: released 192-275 ms, 0 uploads after | e2e/share_stop_release.mjs | |
| 7 | Bulk PC controls / heartbeats / reconnection | PASS (existing tests) | pc_agent 14, lan_presence 5, backend equipment tests | | lab PCs not exercised today |
| 8 | Robot monitoring (read-only), timestamps, offline recovery | PASS (offline) | robot_monitor 42 tests; UR agent 20 tests; collectors stay read-only (guard test) | | |
| 8 | UR5e Home/Stop in Local mode | BLOCKED | dry run; needs commissioning with the operator (External Control host .200) | docs/ROBOT_CONTROL.md | |
| 8 | UR5e automatic Home (idle -> 20 s countdown -> Home) | BLOCKED (software PASS) | 6 agent tests; twin countdown + Cancel; off by default | tools/ur5e_control | physical commissioning |
| 8 | Portal STOP in Local mode, whoever drives | BLOCKED (software PASS) | ESP32 firmware compiled; backend 6 tests; recovery refused while a program is paused | firmware/SmartLab_Robot_Stop | wiring needs the cell owner's approval |
| 8 | FANUC Home/Stop | not built | UNAVAILABLE by design until UR5e works physically | | |
| 9 | Admin/Staff/Student access | PASS | authz sweep in the backend suite; new routes staff-only (tests) | | |
| 10 | Docs / checkpoint / config | PASS | this file, docs/PROGRESS_CHECKPOINT.md, docker-compose passes voice + robot env | | |

## 3. Implemented during this audit (and the session before it)

| Commit | What |
|---|---|
| b2d6ae5 | UR5e automatic Home after idle (cancellable countdown in the twin), hardware stop relay (ESP32 firmware + backend), exact pendant steps |
| 2a0b760 | Local voice assistant (push-to-talk, Whisper, Piper), compose env for voice + robot control |
| a1470ed | **Booking race fix**, /equipment query count, sign-in hash slots, hidden-tab polling, camera frames paused in hidden tabs, Excel export, Lab Health Score, emergency headcount, AAS export |
| 53a35d0 | Evaluation tab; briefing warning for published default passwords |

## 4. Performance (measured; laptop above; copy backend unless stated)

| Measurement | Before | After | How |
|---|---|---|---|
| 20 simultaneous sign-ins: p50 / max | 1.58 s / 1.74 s | 0.94 s / 1.44 s | scratch login_burst.py, 3 rounds, slots compared 40/3/2/1 |
| /monitor during that burst: p50 / max | 317 / 1167 ms | 156 / 331 ms | same |
| Hidden tab requests/s: Monitor / Security | 0.77 / 0.5 | 0.2 / 0.2 | e2e/hidden_tab_polling.mjs |
| Page switch warm, 40 visits: p50 / p90 | 126 / 231 ms | 119 / 229 ms | e2e/nav_timing.mjs (baseline build vs current) - no regression, no gain |
| First visit per route: p50 / p90 | 411 / 561 ms | 378 / 469 ms | same |
| Role matrix warm content (median of routes) | - | admin 145, staff 140, student 100 ms | e2e/role_matrix_perf.mjs, 2 trials |
| Security page under camera feed | - | frame fetch p50 28 / p95 74 ms, frame age p50 86 ms, 0 long tasks | e2e/perf_portal.mjs |
| Booking race (2 simultaneous overlapping) | 2 saved | 1 saved | tests/test_booking_race.py |
| Voice: question -> answer / first audio | - | 3.0-3.5 s / 4.3-5.3 s | e2e/voice_talk.mjs (fake mic) |
| Phone: marker -> card / people boxes | - | 227-244 ms / 7.4 fps, rtt p95 95 ms | e2e/scan_lab.mjs, scan_people.mjs |
| Cameras (earlier today, recordings) | 7.8 / 8.9 analyses/s | 9.4 / 9.9 | docs/CV_BENCHMARK_2026-10-26.md |
| Knowledge agent | - | source 10/12, facts 10/12, lookup 165 ms, CPU answer median 14 s | tools/knowledge/agent.py --bench |

The copy database is small, so /equipment was already 44 ms. The query-count fix matters as session history grows;
the test guards it.

## 5. Tests run (2026-10-26)

| Suite | Result |
|---|---|
| Backend full (`docker compose run ... pytest`, smartlab_test) | **626 passed, 0 failed** (14 min, HEAD 53a35d0) |
| tools/security_vision | 291 passed |
| tools/robot_monitor | 42 passed |
| tools/knowledge | 49 passed |
| tools/ur5e_control | 20 passed |
| tools/voice | 6 passed |
| tools/lan_presence / tools/pc_agent | 5 / 14 passed |
| Frontend `tsc --noEmit` + `vite build` | OK |
| Firmware SmartLab_Robot_Stop (arduino-cli, esp32 3.3.12) | compiled, 71 % flash |
| e2e scan_lab / scan_people / voice_talk x3 / share_stop_release x3 | PASS |
| e2e nav_timing x2 builds, perf_portal, role_matrix_perf, hidden_tab_polling | run, numbers above |
| Booking race test without the lock (negative control) | FAILED as expected: `{1: 'OK', 2: 'OK'}` |

Not run:
* real-hardware tests (cameras live, phone, microphone, UR5e, FANUC, relay, door);
* the two-camera load run (it was run earlier today, not repeated);
* the AI model comparison (Qwen vs Gemma);
* the deploy script (needs your credentials).

## 6. Outstanding work

1. **Change the admin and staff passwords** (Users & roles). Then deploy:
   `py -I tools/deploy/deploy.py` with SMARTLAB_EMAIL / SMARTLAB_PASSWORD set. Add VOICE_KEY and UR_AGENT_KEY to `.env`
   first.
2. Restart both camera services in the lab, so the new detector and tracker defaults are used. Then run a live check.
3. UR5e commissioning (docs/ROBOT_CONTROL.md):
   * install `portal_200` and `portal_control.urp` on the pendant;
   * run the agent in dry run, then live, with a hand on the E-stop;
   * then `UR_AUTO_HOME=on`.
4. Stop relay: bench test with a multimeter. Then wire it into SI0/SI1, after the cell owner approves.
5. Real phone test, with printed markers. Real voice test with lab members' accents.
6. FANUC Home/Stop, once the UR5e works physically.
7. Not built: OPC UA, identity-fusion study, visual safety triage, whole-lab time slider, .pkpass, flash
   store-and-forward in the firmware, Qwen vs Gemma benchmark.

## 7. Security and safety findings

| Severity | Finding | State |
|---|---|---|
| HIGH | Live admin@giu-uni.de and ramy@giu-uni.de accept the passwords published in the public README | **open**. The briefing now shows it; changing credentials is the owner's action |
| HIGH | Live portal is 5 commits behind (booking race fix not live) | **open**. Deploy needs the owner |
| MEDIUM | Camera recordings (1.3 GB) have no retention limit | owner decision (conflicts with "never delete data") |
| FIXED | Booking race allowed double bookings | fixed (a1470ed) |
| FIXED (earlier) | CA private key mounted into nginx | fixed (3a68d82) |
| SAFETY | Automatic Home moves the robot without a button press | off by default. It runs only while our pendant program plays, only from verified poses, and only after a visible, cancellable countdown. The cameras do not check for a person at the arm. Owner decides |
| SAFETY | Stop relay is not safety-rated | stated in the UI and docs. The pendant E-stop stays the E-stop |

No robot motion, door action, safety configuration change, n8n change or push was made. Every robot path ran in
dry run or against mocks.

## 8. Git

* Branch `offline-router-door-photos`, HEAD = the commit that adds this report (on top of 53a35d0), not pushed.
* Uncommitted: the owner's `.env.example`, `frontend/e2e/command_center.mjs` and 54 CAD files (untouched), plus
  untracked owner material (reports, figures). Nothing of the owner's was modified.

## 9. Verdict

**READY WITH DOCUMENTED LIMITATIONS.** The software is implemented and tested on recordings, fakes and mocks. Two
owner actions are needed before it can be called production-ready: change the published passwords, and deploy.
All physical behaviour still needs supervised lab tests: robots, relay, phone, microphone, and live cameras on the
new defaults.
