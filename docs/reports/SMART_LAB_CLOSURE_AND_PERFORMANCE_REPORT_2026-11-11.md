# Smart Lab - closure mission and performance report (2026-11-11)

Branch `qa/browser-and-camera-docs`, base commit `fdfd1fe`. **Nothing committed, pushed, deployed, flashed or
physically actuated.** Recovery point: branch `backup/before-closure-2026-11-11`, database dump and diffs in
`C:\Users\dell\smart-lab-backups\closure-2026-11-11\`.

Status words: TESTED OFFLINE = automated tests on this laptop; MEASURED = numbers taken on this laptop today;
NOT TESTED = could not be run here (reason given); LAB = needs the real lab, people and cameras.

## 1. Sources

25 Argon files in Downloads (35 distinct by SHA-256 among 45 look-alike names) and the two "Master Unified
Engineering Execution Blueprint" files (identical, SHA-256 6957fbfe...). The Argon patch
`Smart_Lab_Optimization_Fixes_2026-11-10.patch` was **not applied**: it was written against an older snapshot,
and every finding in it was checked against the current code instead.

## 2. What changed (48 files, +849 / -74, plus 5 new files)

| Area | Problem found in the code | Fix | Tests | Status |
|---|---|---|---|---|
| Door reports (SEC-01) | `/api/access/validate-qr, validate-rfid, events, grant, deny` accepted any device key: a sensor node's own key could report in the master's name | own key speaks only for itself, and only door devices (master / door camera / face server) may make door reports; shared key unchanged | test_device_keys.py (+2) | TESTED OFFLINE |
| PC / robot reports (SEC-02) | a PC's own key could file a ROBOT state report | the report kind must match the device type | test_pc_keys.py (+1) | TESTED OFFLINE |
| PC enrolment (SEC-03) | `PC_ENROLL_OPEN` defaulted to true and docker-compose never passed it, so .env could not close it | default false, passed through compose; start-up warnings for open enrolment and open sign-up | existing tests | TESTED OFFLINE |
| Live-updates socket (SEC-04) | the 8-hour sign-in token travelled in the WebSocket URL (access logs) | one-time 30 s ticket `POST /api/auth/ws-ticket`; nginx log without query strings | test_portal.py (+1) | TESTED OFFLINE |
| Phone scan (SEC-05) | `/api/scan/appearance` unthrottled (several CPU models per frame) | 6 frames / 2 s per user (one backend process, so an in-process limit is correct) | test_appearance.py (+1) | TESTED OFFLINE |
| CI failure on main | random booking token read at 2 of 7 distances through the camera model | `issue_token()` also checks the token through the door-camera model (6 of 7); measured 392/400 tokens 7/7 before | test_qr_pipeline.py (+2) | TESTED OFFLINE |
| Cross-camera naming (P1-A) | the last unnamed person could take the last free name from the head count alone | needs a measured look that agrees; otherwise one `CROSSCAM_AMBIGUOUS` note | test_crosscam.py (+2, 1 updated) | TESTED OFFLINE |
| Name after a restart (owner request) | after a service restart everyone was Unknown again | face names restored as candidates; the stored look gives back a **marked guess** "Name ? (look)" (portal: "? guess by look"); confirmed only by this camera's face or the other camera's confirmed name on the same spot; never shared, never learnt from, yields to a door entry | test_look_guess.py (9), test_vision.py (1 updated) | TESTED OFFLINE, LAB |
| Look handoff (local commit 68b7157) | feet hidden / person already left the other view | brought into the tree | 12 simulated tests | TESTED OFFLINE, LAB |
| Portal tabs | a revisited page started empty and showed its skeleton again | `api.peek()`: last answer for this sign-in (max 60 s, emptied by any write and by sign-out, never for alarms / emergency / sharing) paints first, the page reloads in the background; 9 pages | tsc + build | TESTED OFFLINE |
| Backend reads | summary and lab catalogue recomputed for every widget; session expiry scanned on a dozen GETs | 3 s / 2 s shared cache, emptied by any signed-in user's write (`ClearOnWrite`); expiry scan at most every 3 s | full suite | TESTED OFFLINE |
| AI answers | nothing shown until the whole answer was ready | `POST /api/ai/ask/stream` and `/student/ask/stream` (NDJSON), same checks, limit and audit; chat shows text as it is written; nginx unbuffered for /api/ai/ | test_ai_stream.py (6) | TESTED OFFLINE |
| AR scanner | two lab PCs in one frame = one box | per-class `max_instances` (lab PCs: 6), overlapping boxes stay one object | test_bin_detector.py (+1) | TESTED OFFLINE |
| Monitoring | no single health view of the native services | `tools/ops/watchdog.py` - **monitor only**, restarts nothing; live snapshot: 11/11 up | test_watchdog.py (3) | TESTED OFFLINE |
| Camera CPU | see section 4 | OpenCV threads 2 (`--cv-threads`), idle render 1/s | camera suite | MEASURED |
| AI memory | see section 4 | knowledge warm-up opt-in (`KB_WARMUP=1`) | knowledge suite | MEASURED |
| README | hardware captions shifted (Master missing), no AR picture | fixed; AR overlay added and labelled as composed | - | done |

Not done from the Argon / blueprint lists, on purpose or for lack of evidence: 24 h model keep-alive (RAM);
changing the default model (needs an A/B with both cameras live); lowering any identity threshold; composite DB
indexes (no slow query measured today); partial-body ReID change (the recording measurement was stopped because it
pushed the laptop to 100 % CPU during the test run; it needs a quiet machine); create-issue / acknowledge-alert AI
actions (not built yet).

## 3. Tests (this session, this laptop)

| Suite | Result |
|---|---|
| Backend full (Docker, smartlab_test) | 757 passed, 2 skipped, 1 failed: `test_robots::...disagreement_after_hold` - passed in the targeted re-run (121 passed), so intermittent timing |
| Backend, every changed / new test file after the last edits | 121 passed |
| Security vision | 320 passed; scenario bench 14 scenarios, 0 false names, 0 name switches (simulated) |
| Knowledge 49 · PC agent 40 · robot monitor 43 · UR5e control 20 · voice 6 · LAN presence 6 · relay 5 · OPC UA 3 (Python 3.12) · watchdog 3 | all passed |
| MCP end-to-end | NOT TESTED: pytest is not installed in its .venv (installing needs your OK) |
| Frontend | `tsc --noEmit` 0 errors; `vite build` OK |

The full backend suite ran before the AI streaming, cache and AR edits; those files were then covered by the
targeted run, not by a second 50-minute full run.

## 4. Performance (MEASURED today)

**Machine:** i7-9750H 6 cores / 12 threads, 2 x 8 GB DDR4-2666 (both slots full), GTX 1650 4 GB (driver 616.92),
Windows "Balanced" plan.

**At launch with the lab services up (cameras unreachable from home):** free RAM **1.9 GB** of 15.8, commit
**28.8 of 42.8 GB** (the page file is working hard). Largest: Docker's Linux VM 2.3 GB (capped at 6 GB by
`.wslconfig`), local AI models 1.5 GB held on the CPU, each camera service ~0.4 GB, OneDrive 0.4 GB.
**Largest CPU user at rest: OneDrive (~17 % of the machine)** - the whole repository, 11 GB of training data and
1.3 GB of recordings live inside the OneDrive folder, so every log, build and test write is synced.

**Camera services** were started without `--threads`, so OpenCV used 8 threads in each of the two processes.
Replay of two lab recordings at once (2304 x 1296, 25 fps input, CPU-side work only):

| OpenCV threads | render / s | CPU per camera (cores) | render p50 / p95 ms |
|---|---|---|---|
| 8 (before) | 10 | 0.65 | 20 / 30-33 |
| 4 | 10 | 0.64 | 22 / 41-42 |
| 2 | 10 | 0.60-0.62 | 19-20 / 27-28 |
| 8 | 1 | 0.50-0.54 | 21-23 / 31-34 |
| **2 (now)** | **1 when nobody watches** | **0.41** | 19-20 / 25-26 |

Saving: ~0.24 core per camera, ~0.5 core for both. Decoding the full-resolution stream is the larger fixed cost
(~0.4 core per camera). The GPU detector and re-ID were not part of this replay (they are not CPU work) - LAB
check: analysis rate should stay ~9/s per camera.

**Local AI:** answer model cold 8.0 s vs warm 0.4 s; embedding model cold 1.1 s. Warm-up at launch now off.

## 5. Hardware decision

**Verdict: SOFTWARE OPTIMIZATION HELPS; the measured bottleneck is MEMORY, not CPU. No second computer is
justified.** CPU had spare capacity at rest (cameras use the GPU); RAM was 1.9 GB free with heavy paging.

| Option | Price found (Egypt, 11 Nov 2026, not purchased) | Fixes the measured problem? |
|---|---|---|
| A. Software only (done above) + move data off OneDrive | 0 EGP | partly: ~1.5 GB RAM and ~0.5 core back, OneDrive load gone once moved |
| **B. RAM 2 x 16 GB DDR4-2666 SODIMM (32 GB)** | Crucial 16 GB 2666 at [Technology Valley](https://tv-it.com/products/crucial-16gb-ddr4-2666-mhz) EGP 1,625 each, listed in stock -> **~3,250 EGP** | **yes, directly** - doubles RAM, no new device, no new failure point. Check Dell's maximum for the G3 3590 before buying (commonly listed as 32 GB, not verified here) |
| C. Used mini PC 16 GB / SSD | [Noon Egypt](https://www.noon.com/egypt-en/electronics-and-mobiles/computers-and-accessories/computers-new/desktops/mini-pcs/) renewed from ~EGP 10,600; [Dubizzle](https://www.dubizzle.com.eg/en/electronics-home-appliances/computers-accessories/q-mini-pc/) asking EGP 6,750-9,250 (specs unstated) | would take Docker (2.3 GB) off the laptop, but costs 3x option B and adds a second machine, network link and backups to look after |
| D. Raspberry Pi 5 8 GB | [Fluxelectronix](https://fluxelectronix.com/?p=82250) EGP 7,500 listed in stock; [Makers Electronics](https://makerselectronics.com/product/raspberry-pi-5-computer/) EGP 14,000 out of stock | no: ARM, no DirectML/YOLO path, and the vision stack is the GPU's job anyway |
| E. ESP32-S3 | - | no: not a server |

Recommendation: keep the software changes, move the bulky data out of OneDrive, and if money is spent, spend
~3,250 EGP on RAM. Prices are listings found today, not quotes; confirm stock and delivery to Alexandria before
paying.

## 6. Storage

Done: Docker build cache and unused images removed (~21 GB inside Docker's disk file; the file itself only
shrinks when Docker Desktop compacts or moves it). Moved: `tools/vision_train/data` (11 GB, git-ignored) to
`D:\SmartLabData\vision_train_data` - copy verified (20,817 files, 11,265,942,718 bytes on both sides, sample
hash equal), the old path is now a junction to D:, then the C: copy was removed. **C: free 15.2 -> 25.0 GB.**
Owner: Docker Desktop -> Settings -> Resources -> Disk image location -> `D:\DockerData` moves the
67.6 GB disk file (Docker must be idle; do it after a fresh database dump).

## 7. Still open

- LAB: restart both camera services to load the new camera code; two-person walk test (look guess, handoff, no
  wrong names); confirm ~9 analyses/s per camera; phone AR test.
- Deploy: `docker compose build backend frontend` + `up -d --no-deps backend frontend` makes the portal changes
  live (owner OK; the backend running now has only the first security changes).
- Not built yet: AI create-issue / acknowledge-alert actions; partial-body ReID (needs a quiet-machine measurement
  first); model A/B with both cameras live.
- Owner decisions: commit / push; move the repository out of OneDrive; Docker disk to D:; RAM purchase.

## 8. Commands

    launch.bat                                   start everything (only what is missing)
    py tools\ops\watchdog.py --once              health of all 11 services (monitor only)
    py -m pytest -q tools\security_vision        camera tests
    docker compose run --rm --no-deps -T -v "%CD%\backend:/app" backend python -m pytest -q -p no:cacheprovider
    set SV_CV_THREADS=8 & set SV_IDLE_RENDER_FPS=15   old camera behaviour (before starting the cameras)
    set KB_WARMUP=1                              old knowledge warm-up
    set SMARTLAB_LOOK_GUESS=off                  no look guess (observe = log only)
    Roll back everything: git diff > my.patch, then compare with branch backup/before-closure-2026-11-11.
