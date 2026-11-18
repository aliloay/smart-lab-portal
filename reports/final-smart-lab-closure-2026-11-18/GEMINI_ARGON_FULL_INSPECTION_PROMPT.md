# GEMINI (Antigravity, Argon, max reasoning): SMART LAB, FULL PROJECT INSPECTION: WHAT IS LEFT TO DEVELOP?

You are starting a fresh chat. You have no memory of earlier sessions, so read before you judge.
This is a **read-only inspection**. Your job is to find everything in the Smart Research Lab project that is unfinished, broken,
missing, inconsistent, untested, undocumented, or weaker than it should be for a BSc thesis defense and exhibition,
and to return a precise, prioritised list with evidence.
Do not fix things yourself unless a section below explicitly allows it.

## 1. Project and locations
- **What it is:** BSc thesis (German International University, GIU). One local system for a robotics lab:
  - FastAPI portal + React/TS/Tailwind frontend + Postgres (Docker Compose);
  - two AI security cameras;
  - 4 ESP32 sensor nodes (door/master, environment, consumables bin, reusable bin) + ESP32-CAM;
  - UR5e and FANUC digital twins (read-only telemetry, OPC UA);
  - lab-PC agents + relay (screen wall, screen share, message, maintenance, exam);
  - local AI assistant (Ollama qwen2.5:1.5b + knowledge vault);
  - n8n automations, phone AR, voice.
  - Everything runs on one Dell G3 laptop (16 GB, GTX 1650), local network only.
- **GitHub (public):** https://github.com/aliloay/smart-lab-portal
  - **GitHub is BEHIND the laptop.** Nothing from 11–19 Nov is pushed. The source of truth is the local repo.
- **Main checkout (live camera, robot and knowledge services run from here):** `C:\Projects\smart-lab-portal`
  - branch `fix/pre-lab-hardening`, HEAD `fc18c99` or newer;
  - it has uncommitted owner/Claude work: never modify, stash, reset or checkout in this folder.
- **Your own worktree:** `C:\Projects\smart-lab-argon` (currently `opt/gemini-final-giu-capacity-2026-11-18` @ 559263d).
  - To inspect the latest code there: `git -C C:\Projects\smart-lab-argon checkout --detach fix/pre-lab-hardening`.
  - Detached is fine; a branch checked out elsewhere cannot be checked out twice.
- **Other worktrees** (`git worktree list`), all read-only for you:
  - `C:\Projects\smart-lab-portal-opt` (opt/claude-app-performance-2026-11-17, now merged);
  - `C:\Projects\smart-lab-release` (release RC 17 Nov);
  - `C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-review` (review/gemini).
- **Data and media:** `D:\SmartLabData` (junction for training data; Docker disk `D:\DockerData`).
  - Lab-day folders: `lab_2026-11-17`, `lab_2026-11-18`.
  - Showcase build: `showcase_2026-11-19`.
  - Backups: `kb_backup_*`, `n8n_backup_*`, `model_backups`, `firmware_backup*`, `main_untracked_backup_20261118`.
- **Thesis, earlier videos, CAD, photos:** `C:\Users\dell\OneDrive\Desktop\Bsc\` (e.g. `ONECORE_LAUNCH_VIDEO\`, `Digital Twin_Ur5e .mp4`, `Camera_lab_testt.mp4`).
- **Obsidian / knowledge vault:** `C:\Users\dell\SmartLabKnowledge\vault`.
  - Index and embeddings in `C:\Users\dell\SmartLabKnowledge\data`.
  - Code: `tools\knowledge` (kb.py, agent.py, serve.py on :5199, graph.py).
- **n8n:**
  - repo copies of the 23 workflows: `automation\n8n\json\01..23-*.json`;
  - live n8n: http://127.0.0.1:5678 (container currently stopped; do not start it).
- **Firmware:** `firmware\` (SmartLab_Master_Portal, SmartLab_Environment_Node, SmartLab_Consumable_Bin, SmartLab_Reusable_Bin(_Modular), SmartLab_Robot_Stop, ESP32CAM_Vision_FAST, face_server).
  - The ESP32-CAM must be built with Arduino core **3.2.1**; 3.3.x gives "Camera init failed".
- **Services and tools:**
  - `tools\security_vision` (cameras, Python 3.14, DirectML, :5100/:5101);
  - `tools\robot_monitor`, `tools\ur5e_collector`, `tools\opcua` (Python 3.12, read-only);
  - `tools\pc_agent`, `tools\relay`, `tools\lan_presence`;
  - `tools\voice` (Piper/Whisper :5320);
  - `tools\deploy\build_images.ps1` (stamped builds);
  - `launch.bat`.
- **Read these first:**
  - `CLAUDE.md` (project rules);
  - `docs\PROGRESS_CHECKPOINT.md`;
  - `docs\ROBOT_CONTROL.md`, `docs\VISUAL_FOUNDATION.md`, `docs\LAB_TEST_2026-10-15.md`;
  - `docs\defense\*`;
  - `reports\` (all subfolders, newest first: `final-smart-lab-closure-2026-11-18`, `gemini-final-giu-capacity-optimization-2026-11-18`, `live-lab-finalization-2026-11-18`, `final-integration-release-2026-11-17`, `final-optimization-2026-11-17`);
  - `git log --oneline -60`.
- **Quick answers:** `py tools\knowledge\agent.py "<question>"` and `py tools\knowledge\graph.py related <path>`.

## 2. Hard safety rules (breaking any of these fails the task)
1. **Robots and door:**
   - Never send anything that moves a robot: no OPC UA writes, no start/reset/mode/safety changes. Robot control adapters stay UNAVAILABLE.
   - Never open the door or trigger locks, relays, alarms or emergency mode.
   - Never change door firmware, auth or credentials. Never flash any board.
2. **Database:**
   - Never write to, reset or truncate the live `smartlab` DB. Read-only `SELECT`s via `docker compose exec db psql` are allowed.
   - Tests only against `smartlab_test` or the in-memory fast runner.
3. **n8n:** never start, edit, activate, deactivate or run n8n workflows. Inspect the JSON files only.
4. **Containers, services, git:**
   - Do not restart, rebuild or redeploy containers or services; Claude is deploying in parallel.
   - Do not kill camera or robot windows.
   - Do not push to GitHub. Do not commit in the main checkout.
5. **Privacy and secrets:**
   - Never print or copy secrets: `.env`, `camera.env`, `camera2.env`, `robot.env`, `voice.env`, keys, RTSP URLs, passwords, tokens.
   - Write "present / missing / looks valid", never the value.
   - No photos of people, faces, phone numbers or private PC screens in anything you write.
6. **Data and machine:**
   - Never delete anything: data, accounts, audit logs, backups, models, footage. The owner's rule is "data is the product".
   - Do not install packages or download models.
   - Cameras have GPU priority. Do not run heavy CPU/GPU jobs; Claude is rendering a video and benchmarking the AI. Light unit tests are fine.

## 3. Inspect literally everything
For each area: what exists, what works (with evidence), what is unfinished or fake, what is untested, what is not documented,
and what a professor or exhibition visitor would notice. Areas:

1. **Portal pages and navigation:**
   - every route in `frontend/src` and every sidebar item;
   - dead links, empty states, loading states, mobile layout, dark/light theme;
   - role-based access (student / staff / admin), wording, consistency;
   - animations (framer-motion lazy load), performance, the welcome/login design.
   - Use the test copy only: frontend :5176 / backend :8100. If you must look at the live portal (https://127.0.0.1), look only and never click door/robot/emergency/PC-control buttons.
2. **Backend:**
   - every router in `backend/app/api/routes`;
   - auth/RBAC, subnet and device-key protection, input validation, error handling, pagination;
   - audit log, build stamp (`/api/health` version and `/version.json`; should not say "unstamped");
   - test coverage gaps (≈820 backend tests).
3. **Security cameras:**
   - identity (face, door entry, staff confirm), cross-camera numbering, seats/desks per PC, robot operator spots;
   - floor map, crossing re-deal, false names;
   - what is still guesswork. Tests: `py -m pytest -q tools/security_vision`.
4. **4 ESP32 nodes + ESP32-CAM:**
   - firmware completeness vs the portal contract, heartbeats, offline detection, OTA;
   - calibration (load cell), NFC, reed switch, LCD;
   - `FIRMWARE_HOME_FOLLOWUP.md`.
   - Nodes are at the owner's home and untested since the firmware changes. Say what must be tested on hardware, step by step.
5. **Digital twins and robots:**
   - UR5e/FANUC twin rendering, liveness (UNKNOWN/STALE = offline), OPC UA server, collectors;
   - the commissioning steps in `docs/ROBOT_CONTROL.md`;
   - the IP conflict: FANUC .100 and UR5e .102 are fixed, but Hemaly's PC gets DHCP .100–.103 on Smart_Lab.
6. **Lab PCs and Hemaly's PC:**
   - pc_agent versions (PC-13 still on 0.9);
   - relay through Hemaly's engineer PC (S2PC136 = PC-01/PC-04 case);
   - screen wall, screen share, message all, maintenance, exam mode, shutdown countdown;
   - sticker mapping: PC-02 owner seat, PC-05/07/12 out, PC-03 removed, PC-16 TA desk; GIULAB20-PC14 was renamed PC-11 from the hostname pattern (unconfirmed);
   - old "TEST - …" cards hidden, not deleted.
7. **AI assistant and knowledge (Obsidian):**
   - answer speed (47 s at the lab with the cameras on; Claude is fixing it now), grounding and citations, hallucinations;
   - instant-answer routes, vault coverage, stale notes, broken links;
   - the graph, the voice path.
8. **n8n:** all 23 workflows vs backend endpoints. Check:
   - credentials needed (names only);
   - workflows that can never fire;
   - duplicated alerts, missing error branches;
   - which ones are documented in the thesis.
9. **AR (phone):**
   - recognition (UR5e 52 %, FANUC 89 %, door controller 93 %, bin 80 % in the 17 Nov test), marker → live data;
   - what is unfinished, HTTPS "Not Secure" warning on the phone.
10. **Videos and media:**
    - Videos taken: `D:\SmartLabData\lab_2026-11-17\ar_test\`, the camera recordings, and `OneDrive\Desktop\Bsc\*.mp4`.
    - Videos made:
      - `D:\SmartLabData\lab_2026-11-18\video\` (v1, v2 narrated tour);
      - `reports\final-smart-lab-closure-2026-11-18\SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4` (Claude, in progress);
      - ONECORE / FACILITY promo cuts.
    - Report: what is missing for the defense (e.g. a real robot + twin shot, door entry shot, node close-ups) and privacy problems (faces, names, phone numbers, emails).
11. **Thesis and evidence:**
    - claims that have no measurement behind them. Known gaps: end-to-end door latency, cold start, power-cut recovery, load-cell accuracy, cost list, power draw per node;
    - figures and screenshots that are out of date;
    - code snippets in `THESIS_CODE_SNIPPETS_AND_EVIDENCE_INDEX.md`.
12. **Operations:**
    - `launch.bat`, startup order, RAM headroom (16 GB), backups (DB dump schedule, n8n backup), rollback runbook;
    - Docker on the D: spinning disk;
    - the stopped `backup` container; TLS certificates.
13. **Repo hygiene:**
    - untracked folders, `.bak` files (`docker-compose.yml.bak-backupenc`), secrets accidentally tracked (`git ls-files` + pattern search; report paths only);
    - large files, `.gitignore` gaps;
    - branches not merged (`git branch --no-merged`), stale worktrees;
    - docs that contradict each other.

## 4. Evidence rules
- Label every claim: **VERIFIED (file:line or command output)**, **TESTED OFFLINE**, **LIVE-VERIFIED**, **UNVERIFIED**, **NEEDS HARDWARE**.
- Hardware results only from real measurements. Never write "works" for something nobody ran.
- Do not repeat findings Claude already closed. Check `git log` and the newest reports first, and say "already fixed in <sha>" where true.

## 5. Allowed to run
- `git log/diff/show/status/branch/worktree` (no checkout in the main checkout).
- Reading any file.
- `py -m pytest -q tools/security_vision` / `tools/robot_monitor` / `tools/knowledge`.
- `npx tsc --noEmit -p frontend`.
- Read-only psql `SELECT`s.
- `curl` GETs to `/api/health` and `/version.json`.
- Do NOT run the backend fast suite (`tools\ops\test_backend_fast.ps1`) while Claude is deploying; ask the owner first.

## 6. Deliverables
Write only into a new folder `C:\Projects\smart-lab-argon\reports\gemini-full-inspection-2026-11-19\` (your worktree, not the main checkout):
1. `INSPECTION_SUMMARY.md`: one page, readiness per area (GREEN / AMBER / RED) and the 10 most important things left.
2. `REMAINING_DEVELOPMENT_BACKLOG.csv`. Columns:
   - `id, area, item, type(bug|missing-feature|untested|docs|privacy|ops|thesis-evidence), severity(P0-P3), evidence(file:line / command), effort(S/M/L), needs(owner|hardware|code|docs), suggested_fix`.
3. `AREA_FINDINGS.md`: one section per area in §3, with evidence.
4. `THESIS_CLAIMS_VS_EVIDENCE.md`: each claim → measurement/file, or "NO EVIDENCE".
5. `MEDIA_AND_VIDEO_GAPS.md`: what footage exists, what is missing, privacy issues (describe them, never paste them).
6. `HARDWARE_TEST_PLAN_FOR_OWNER.md`: ESP32 nodes, robots, door, cameras. One step at a time, with the expected result for each step.
7. `QUESTIONS_FOR_OWNER.md`: only what cannot be decided from the files.

Finish with a short reply listing the P0/P1 items and the folder path.
Do not mark anything done that you did not verify.
