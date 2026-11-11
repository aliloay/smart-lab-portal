# Smart Lab - final execution report (closure and optimisation mission)

Work done 10-11 November 2026 on the owner's laptop (Dell G3 3590). The file name keeps the date the mission was
issued. Prepared for the owner (Ali Loay) and thesis supervision.

Status words used throughout: **LIVE** = deployed and checked on the running system today; **TESTED OFFLINE** =
automated tests on this laptop; **MEASURED** = numbers taken on this laptop today; **LAB** = needs the real lab,
people and cameras (see the physical acceptance checklist); **OPEN** = not done.

## 1. Executive summary

- **Deployed and live:** all portal and backend changes (security fixes, faster tabs, streamed AI answers, read
  caches, live camera activity bar, AR multi-PC boxes). Camera services restarted on the new code.
- **Cameras:** a person the cameras named before comes back as a marked guess "Name ? (look)" after leaving the
  view or after a service restart, and is confirmed by the face; no name is ever given from a head count alone;
  the look handoff between the two cameras is in. **Simulation-tested only** - the two-person walk test is LAB.
- **Speed:** revisited portal pages paint at once from the last answer; AI text appears while it is written; the
  dashboard summary and lab catalogue are shared for 2-3 s; instant AI answers now include what the cameras see.
- **Laptop:** the bottleneck is memory, not CPU. Camera CPU work cut by ~0.5 core, ~1.5 GB of AI models no longer
  loaded at launch. **C: free space 15.2 GB -> 85.8 GB** (training data and Docker's disk moved to D:, project
  moved out of OneDrive to C:\Projects\smart-lab-portal).
- **Hardware:** no second computer is justified. If money is spent: 2 x 16 GB RAM (~3,250 EGP).
- **Not pushed, not committed** (owner decision). No door, firmware or robot action was taken.

## 2. Repository and system state

| Item | Before | After |
|---|---|---|
| Project folder | C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal | **C:\Projects\smart-lab-portal** (OneDrive copy removed; empty folder left while VS Code had it open) |
| Branch / commit | qa/browser-and-camera-docs @ fdfd1fe | same branch and commit; 58 files changed and 16 new files, uncommitted |
| Docker disk | C:\...\Docker\wsl\disk\docker_data.vhdx (67.6 GB) | **D:\DockerData** (verified: same 5 volumes, same row counts) |
| Training data | tools\vision_train\data (11 GB on C:) | **D:\SmartLabData\vision_train_data**, the old path is a link |
| C: free | 15.2 GB | **85.8 GB** |
| Portal images | built 10 Nov | rebuilt 11 Nov; rollback tags `smart-lab-portal-{backend,frontend}:rollback-20261111` |

**Backups (D:\SmartLabBackups\2026-11-11_predeploy):** database dump (43 tables), uploads and n8n volume archives,
the whole git repository with every branch (bundle), the uncommitted diff, Docker settings, row counts.
**Full project copy:** D:\SmartLabBackups\project_copy_2026-11-11 (94,096 files, byte-identical).
Git recovery branch: `backup/before-closure-2026-11-11`.

## 3. Sources and how they were used

25 Argon files in Downloads (35 distinct files by SHA-256 among 45 similar names) and the two "Master Unified
Engineering Execution Blueprint" uploads (identical, SHA-256 6957fbfe...). The Argon patch
`Smart_Lab_Optimization_Fixes_2026-11-10.patch` was **not applied**: it targets an older snapshot. Each finding was
checked against today's code.

| Argon / blueprint finding | In today's code | Decision |
|---|---|---|
| SEC-01: five door routes without device scope | confirmed | fixed (stricter than proposed: door devices only) |
| SEC-02: PC key can report as another kind | confirmed on /equipment/state | fixed |
| SEC-03: PC enrolment open by default | confirmed, and compose could not close it | fixed |
| SEC-04: token in WebSocket URL | confirmed | fixed with one-time tickets |
| SEC-05: /scan/appearance unthrottled | confirmed | fixed |
| SEC-06: issue text in AI prompt | already treated as data in the system prompt; staff-only | kept; no XML-only "fix" |
| P1-A: cross-camera naming by elimination | confirmed | fixed: needs a measured agreeing look |
| Lower MIN_DEEP_H 80 -> 48, wider floor gates, 2-pass warm-up | no evidence it is safe | rejected until measured on lab footage |
| "tools/camera/..." paths | real code is tools/security_vision | used the real paths |
| Unify on qwen2.5:1.5b with 24 h keep-alive | live already uses 1.5b; 24 h holds RAM | keep-alive not raised (RAM is the bottleneck) |
| AR: skip duplicate detector, 4 threads | the bin model is already skipped when the lab model loads | multi-instance boxes added instead |
| Composite DB indexes | no slow query measured | not added (no evidence) |
| Watchdog with auto-restart | camera restarts leave gaps | monitor-only watchdog |

## 4. Every change

### 4.1 Security (TESTED OFFLINE, LIVE)

| Fix | Files | Tests |
|---|---|---|
| Door reports accept a device's own key only for itself and only from door devices (master, door camera, face server); the shared door key is unchanged | backend/app/api/routes/access.py | test_device_keys.py +2 |
| A device's own key must report as its own kind (a PC key cannot file a robot report) | routes/equipment.py | test_pc_keys.py +1 |
| PC enrolment closed by default; `PC_ENROLL_OPEN` and `DEVICE_SHARED_KEY` passed through docker-compose; start-up warnings for open enrolment / open sign-up | core/config.py, main.py, docker-compose.yml | existing + conftest |
| Live-updates socket uses a 30 s one-time ticket (`POST /api/auth/ws-ticket`) instead of the sign-in token in the URL; nginx access log without query strings | core/ws_ticket.py, routes/auth.py, main.py, lib/live.tsx, nginx.conf, app_locations.conf | test_portal.py +1 |
| Phone box-match limited to 6 frames / 2 s per user | core/throttle.py, routes/scan.py | test_appearance.py +1 |

Owner action: set `PC_ENROLL_OPEN=true` in `.env` only while installing lab PCs.

### 4.2 GitHub CI failure (TESTED OFFLINE)

Main's CI failed on `test_qr_pipeline` (a random booking token decoded at 2 of 7 distances). Measured locally: 392
of 400 random tokens decode at 7/7 distances, 7 at 6/7, 1 at 5/7. `issue_token()` now also checks each token
through the door-camera model and draws again below 6/7, so a weak token is never issued (qr.py; 2 new tests).

### 4.3 Cameras and identity (TESTED OFFLINE; LAB for real walks)

- **Name kept after leaving / restart ("look guess"):** a person the camera named before (open door entry, or a
  face name from the last 15 min - both kept on disk across restarts) who is back in view without a name gets it
  from the stored look as a **marked guess**, shown "Ali ? (look)" and "? guess by look" on the Security page.
  Rules: clear look (<= 0.18), clearly closer than every other stored person and every other unnamed person
  (margin 0.10), alone, upright, big enough, held ~2 s. It is never shared to the other camera, never learnt from,
  yields to a new door entry, is dropped if this camera's face says someone else, and becomes a real name only
  when the face agrees or the other camera's confirmed name is on the same spot. Switch: `SMARTLAB_LOOK_GUESS`
  = on / observe / off. Files: vision.py, identity.py, crosscam.py; test_look_guess.py (9 tests).
- **Door entry -> instant name:** already in place (`Labeler._door_entries`): the person who walks in right after
  a granted entry is named; two people on one entry stay unnamed with a review note. Unchanged.
- **No naming by head count:** cross-camera "elimination" now requires a measured look that agrees; otherwise
  one `CROSSCAM_AMBIGUOUS` note. test_crosscam.py (+2, 1 rewritten).
- **Look handoff between cameras** (local commit 68b7157) brought in: a confirmed name crosses on a clear look when
  feet are hidden or the person already left the other view (12 simulated tests).
- **Live activity bar:** one line per tracked person - name or "Person N", upper-body colour, posture (standing,
  walking, seated or leaning, bending or crouching, lying), and the mapped box they are at or near ("most likely at
  UR5e"). Built from data the service already has: no new model, no extra GPU work. Shown as a scrolling LIVE bar
  under each lab's cameras and in the assistant's instant answer. Files: activity.py (new), security_vision.py,
  routes/security.py, Security.tsx, agent.py; tests test_activity.py (4), test_camera_activity.py (2).
- **Head/upper-body tracking:** the full-person detector already boxes partial people (upper body, seated, behind
  desks: YOLO26s 544x960 + zoom pass + low-confidence second stage). A separate head detector or pose model was
  **not** added: it would add GPU load to both cameras and no measurement shows a gain. The name logic above uses
  appearance and face, so it does not need the feet.
- **Half-body looks (MEASURED):** a box cut by the bottom of the picture is now a waist-up view: its crop fills only
  the top of the re-id model's input and its colours are compared shirt-to-shirt. On two lab recordings (348
  same-person pairs) the same-person distance between a full-body and a waist-up view fell from p50 0.282 / p95
  0.561 to **p50 0.170 / p95 0.453**; other people stayed at 0.59-0.66 (only 5 pairs - to be confirmed with the
  two-person lab recording). Waist-up views never update a stored identity. Switch: `SMARTLAB_PARTIAL_LOOK=off`.
  vision.py; test_partial_look.py (4).
- **Honest limits:** appearance cannot guarantee the same person across a change of clothes, and similar clothes
  can look alike; that is why the result is a guess until the face confirms it. Measured re-ID distances and the
  partial-body change are LAB items (section 9).

Scenario bench (simulated, 14 scenarios incl. crossings, posture, 1.5 s / 4 s occlusion, camera off 10 s, two
cameras): **0 false names, 0 name switches, 0 ID switches.**

### 4.4 Portal speed (TESTED OFFLINE, LIVE)

- **Last answer first:** `api.peek()` returns the last answer of the same read for this sign-in (max 60 s, cleared
  by any write and by sign-out, never for alarms, emergency, sharing or sign-in). 9 pages paint from it at once and
  reload in the background: Admin / Staff / Student dashboards, dashboard widgets, Labs, Devices, My bookings,
  Alerts, Equipment, Users.
- **Backend read caches:** `/api/summary` 3 s and `/api/labs/overview` 2 s shared caches; a signed-in user's write
  empties them before and after the write (`ClearOnWrite`), so a change shows on the next read. Session expiry scan
  at most every 3 s instead of on a dozen GETs.

### 4.5 AI assistant (TESTED OFFLINE, LIVE)

- **Streaming:** `POST /api/ai/ask/stream` and `/api/ai/student/ask/stream` (one JSON object per line: meta,
  token, final or error). Same role checks, hourly limit and audit as `/ask`, which is unchanged. The chat shows
  the text as it is written; nginx no longer buffers /api/ai/. The one-answer-at-a-time slot is kept (cameras first).
- **Instant answers:** "what is everyone doing / who is doing what" now answers from the door records plus the
  cameras' live lines, without the model.
- **Measured:** answer model cold 8.0 s vs warm 0.4 s to a short reply; embedding model cold 1.1 s.
- **Maintenance reports through the assistant:** "the oscilloscope in LAB_01 is broken" / "report a network problem on
  PC-04" -> a proposal with lab, device, category and severity; **Confirm** files it through the normal
  `POST /api/issues` as the signed-in user (same checks and audit). Questions ("which issues are open?") are not
  mistaken for reports; booking sentences still go to bookings. agent_actions.py, ai.tsx; test_agent_issue_action.py (4).
- **Acknowledging alerts through the assistant (staff / admins):** "acknowledge the alerts", "ack alert 12", "acknowledge the
  camera alert" -> up to 5 open alerts, most severe first; **Confirm** calls the Incidents page's own
  `POST /api/incidents/{id}/actions` (staff only, audited, refused if already acknowledged). Students are told they
  cannot. test_agent_ack_action.py (3).
- Not built: image generation (no local image model is installed).
  Weekly / monthly reports, PDF and Excel exports already exist (Reports page, `/ai/report`).

### 4.6 AR scanner (TESTED OFFLINE, LIVE)

Per-class `max_instances` in detectors.json: lab PCs up to 6 boxes per frame; overlapping boxes stay one object;
registered assets stay one box. Router, switch and master node were already reported together (test exists).
**Colab round 3 package:** `D:\SmartLabData\colab\lab_r1.zip` (619 MB, 3,864 files) and
`tools/vision_train/colab_train_lab_r3.ipynb` - trains YOLO11n, YOLO11s and an augmented YOLO11n on the same data,
scores them exactly like round 1, exports the best to ONNX at 640.

### 4.7 Monitoring (TESTED OFFLINE, LIVE)

`tools/ops/watchdog.py` - checks 11 services; `--once` for a snapshot, otherwise logs only state changes to
logs/watchdog.jsonl. Restarts nothing by design (a test checks that).

### 4.8 Resource changes (MEASURED)

| Change | Evidence |
|---|---|
| Camera OpenCV threads 8 -> 2 (`--cv-threads`, `SV_CV_THREADS`); detector CPU fallback keeps 8 | two lab recordings replayed at once |
| Annotated picture drawn 10/s only while someone watches, else 1/s (`SV_IDLE_RENDER_FPS`) | same |
| Knowledge service warm-up opt-in (`KB_WARMUP=1`) | 1.5 GB held for 30 min after every launch |

## 5. Performance measurements

**Machine:** i7-9750H 6 cores / 12 threads, 2 x 8 GB DDR4-2666 (both slots used), GTX 1650 4 GB, Windows Balanced.

**At launch with the lab services up:** free RAM 1.9 GB of 15.8, commit 28.8 of 42.8 GB (heavy paging). Docker's VM
2.3 GB (capped at 6 GB), local AI models 1.5 GB on the CPU, each camera service ~0.4 GB. Largest CPU user at rest:
**OneDrive (~17 % of the machine)** syncing the project - fixed by moving the project.

| Camera CPU work per service (2304 x 1296, 25 fps replay) | CPU cores | render p50 / p95 |
|---|---|---|
| 8 threads, render 10/s (before) | 0.65 | 20 / 30-33 ms |
| 2 threads, render 10/s | 0.60-0.62 | 19-20 / 27-28 ms |
| **2 threads, render 1/s when unwatched (now)** | **0.41** | 19-20 / 25-26 ms |

Not measured today (LAB or later): live analysis rate with both cameras (target ~9/s each), AI time-to-first-word
with cameras running, load test with 50-100 users, portal navigation timings in a browser.

## 6. Tests

See SMART_LAB_FABLE_5_2_FINAL_TEST_RESULTS.md. Summary: **backend full suite 775 passed, 2 skipped, 0 failed** (12 min on an in-memory test database); camera 328 passed; knowledge 49,
PC agent 40, robot monitor 43, UR5e control 20, voice 6, LAN presence 6, relay 5, OPC UA 3, watchdog 3 - all passed;
frontend type check 0 errors, build OK, node tests 15/15 (one test brought in line with the 3 Nov PC-status rule);
MCP end-to-end not run (pytest missing in its environment).

## 7. Hardware decision

**Software optimisation helps; the measured bottleneck is memory. No second computer is justified.**

| Option | Price found in Egypt (11 Nov, listings, not quotes) | Verdict |
|---|---|---|
| Software only (done) | 0 EGP | about 1.5 GB RAM and 0.5 core back; OneDrive load gone |
| **RAM 2 x 16 GB DDR4-2666 SODIMM** | Crucial 16 GB at Technology Valley EGP 1,625 each, listed in stock: **~3,250 EGP** | fixes the bottleneck directly; check the G3 3590's 32 GB maximum first |
| Used mini PC 16 GB | Noon renewed from ~EGP 10,600; Dubizzle asking 6,750-9,250 | 2-3x the cost, a second machine to maintain |
| Raspberry Pi 5 8 GB | Fluxelectronix EGP 7,500; Makers Electronics EGP 14,000 (out of stock) | cannot run the camera AI path |

## 8. Readiness

| For | Ready? | Evidence |
|---|---|---|
| Local software demonstration | **Yes** | all suites pass, portal live and healthy, all 11 services up |
| Live laboratory demonstration | **Yes, after the checklist** | camera behaviour is simulation-tested; walk test pending |
| Final thesis defence | **Yes for software**; cite camera identity results as simulated until the walk test | |
| Deployment to another institution | **Not yet** | single-laptop setup, hand-set camera calibration, no install-from-scratch test on another PC today |

### 4.9 Developer speed (TESTED OFFLINE)

With Docker's disk on the D: hard disk the backend suite would have taken about 5 hours. `tools/ops/test_backend_fast.ps1`
runs it against a separate throw-away PostgreSQL held in memory: **7 min 44 s** for 772 tests. Live reads are not
slowed by the move (API health with a database ping ~6 ms; queries ~6 ms, served from memory); bulk writes are.

## 9. Still open

1. **LAB:** two-person walk test, camera rates, restart test, AR on a phone (checklist).
2. **Owner:** commit and push (nothing pushed); run the Colab round 3 and bring back best.onnx + test_report.json.
3. **Software, next:** confirm the half-body result and tune thresholds on the two-person lab recording; AI model A/B with both cameras live; browser
   timing run of every tab; load test on an isolated copy.
4. **Optional purchase:** 2 x 16 GB RAM.

## 10. Commands

    cd C:\Projects\smart-lab-portal
    launch.bat                                        start everything (only what is missing)
    stop_all.bat                                      stop everything (data kept)
    py tools\ops\watchdog.py --once                   health of all services
    py -m pytest -q tools\security_vision             camera tests
    docker compose run --rm --no-deps -T -v "%CD%\backend:/app" backend python -m pytest -q -p no:cacheprovider

Roll back:

    portal images:  docker tag smart-lab-portal-backend:rollback-20261111 smart-lab-portal-backend:latest
                    docker tag smart-lab-portal-frontend:rollback-20261111 smart-lab-portal-frontend:latest
                    docker compose up -d --no-deps backend frontend
    camera / AI switches (set before launch): SV_CV_THREADS=8  SV_IDLE_RENDER_FPS=15  KB_WARMUP=1  SMARTLAB_LOOK_GUESS=off
    database:       pg_restore from D:\SmartLabBackups\2026-11-11_predeploy\smartlab.dump (insert-only merge, never a wipe)
    Docker disk:    restore D:\SmartLabBackups\2026-11-11_predeploy\docker-settings-store.json.bak
