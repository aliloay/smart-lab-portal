# Smart Research Lab: project state, 21 Nov 2026 (~15:40)

**Setting:** at home, with all 5 ESP32 boards connected; the robots and lab PCs are at GIU.

**Labels used:**
- **live**: read from the running system at the time of this report;
- **measured**: real-hardware numbers from [MEASUREMENTS_2026-11-21.md](MEASUREMENTS_2026-11-21.md);
- **tested**: automated tests;
- **last seen**: from the last time it ran.

## 1. Summary
| Area | State |
|---|---|
| Portal (web app + database) | **Running and healthy** (live). Today's code is deployed. 875 backend tests pass |
| ESP32 boards (5) | **All 5 online** (live): master door, environment, consumables bin, reusable bin, ESP32-CAM |
| Door | Works with card, QR, fingerprint and face. One known hardware fault: the RFID reader freezes at the relock (fix: 1N4007 diode, being bought) |
| Security cameras (2) | Stopped at 15:22 today together with the other laptop helper services. Start `launch.bat` |
| Face server | Stopped with the helper services. Face entry worked today until then |
| AI assistant | Ollama running, model qwen2.5:1.5b installed. The knowledge service is stopped with the helper services |
| n8n | **Running**, 26 of 26 workflows active (live) |
| Obsidian vault | 806 notes, 0 broken links (last checked 18 Nov) |
| Robots (UR5e, FANUC) | At GIU, last seen 18 Nov. Read-only, so nothing in the system can move them |
| Lab PCs (14) | At GIU, last seen 18 Nov |
| Code | Branch `fix/pre-lab-hardening`, latest commit 3758fa9, **79 commits not pushed to GitHub** |

## 2. Laptop and services
- **Laptop:** Dell G3 3590, now 32 GB RAM, GTX 1650. WSL limited to 10 GB / 6 cores; Windows power plan "Best performance" on AC.
- **Docker (live, all healthy):**

| Container | What it does | State |
|---|---|---|
| `db` | Postgres 16: all portal data | healthy, up 4 h |
| `backend` | FastAPI portal API (ports 8000 / 443 / 8443) | healthy, rebuilt today |
| `frontend` | React web app (ports 80 / 443) | healthy, rebuilt today |
| `n8n` | Automations, n8n 2.40.7 (127.0.0.1:5678) | healthy |
| `backup` | Scheduled database backups | healthy |

- **Helper services started by `launch.bat` (stopped at the time of this report):**
  - face server (port 5000);
  - security camera 1 and 2 (5100 / 5101);
  - voice (5320);
  - knowledge service (5199);
  - robot / OPC UA monitors.
  - Start `launch.bat` by double-clicking it in Explorer. Started from the VS Code terminal, it inherits the wrong Python
    environment, which breaks mDNS and starts the knowledge service twice.
- **Ollama (live):** running on 127.0.0.1:11434 with `qwen2.5:1.5b` (the assistant) and `nomic-embed-text` (search).
- **Session loggers still running:** the master serial logger and the node timeline recorder. Stop them when the testing is finished.

## 3. ESP32 boards (live, all on the Smart_Lab router)
| Board | Address | Firmware | State | Notes |
|---|---|---|---|---|
| Master door controller `MASTER_LAB01` | 192.168.1.151 | portal-1.2 | online | RFID + QR + fingerprint + face; TFT and tablet grant screen with the person's photo; events stored while offline and delivered later |
| ESP32-CAM `CAM_LAB01` | 192.168.1.150 | core 3.2.1 build with idle throttle | online | Door camera for QR and face; the throttle brought ping loss on the other nodes to 0 % |
| Environment `ENV_LAB01` | 192.168.1.152 | env-0.1.1 | online | Temperature, humidity, gas, flame. At home the flame sensor sees sunlight and reports flame (owner checked: fine) |
| Consumables bin `BIN_NODE_1` | 192.168.1.153 | bin-0.6 | online | Load cell + LCD; guided calibration; several items per scale; 3D-printed holder fitted |
| Reusable bin `REUSE_BIN_1` | 192.168.1.154 | reuse-mod-0.5 | online | Floor dock for borrowed items |

**Firmware backups** (full 4 MB, taken before today's flashes) are in `D:\SmartLabData\firmware_backup\`.

## 4. Door (measured)
| Step | Time |
|---|---|
| Card read → identity found | 5 ms |
| QR → booking confirmed by the portal | 161 ms |
| Fingerprint match → lock released | 8 ms |
| Face match → lock released | 5 ms |
| Lock released → grant screen | 230 ms |
| Cold start → accepting entries | 2.9 s (locked from 0.47 s) |
| Router power cut → all 5 boards back | 5.4 s after the router is ready |

- **Offline (laptop unreachable):**
  - card + fingerprint keep working;
  - QR and face are refused by design, because both need the laptop;
  - door events are kept on the master and delivered late at their real time (6 of 6 within 1 s).
- **Door photo:** the admin picks the photo shown on ACCESS GRANTED (Users → Enroll → Door photo), from:
  - face-training frames;
  - the door camera;
  - an upload.
  - Confirmed today for User 1, on both the TFT and the tablet (`http://192.168.1.151/`).
- **Personal door QR:** every user can create one (Profile → Door QR). It works anytime with no booking, follows the same rule
  as a card, and is the backup while the RFID is down. None has been created yet.
- **Known fault: the RFID reader freezes at the relock** (the lock has no flyback diode).
  - The software guard saved 8 of 10 relocks; only a power cycle clears a freeze.
  - Fix: a 1N4007 across the lock (EGP 1, Ekostra), then re-test 20 relocks.
  - A new buzzer is to be bought with it.

## 5. Cameras and vision
- **Security cameras `SECCAM_LAB01`, `SECCAM_LAB02`:** last seen 21 Nov 15:22, stopped with the helper services.
  - Features: people detection, tracking and naming across both cameras, seat and PC presence, equipment-moved alerts.
  - Recordings and live tiles in the portal. Suite: 396 tests (18 Nov).
- **Face server `FACESRV_01`:**
  - door face recognition;
  - accepts the master's own device key (by hash);
  - keeps door-photo candidates;
  - 22 tests pass.
- **Phone AR (Scan page):**
  - YOLO detector v7, live since 14 Nov;
  - recognises robots, PCs and nodes, with a live panel per item (UR5e joint bars, robot status).
- **Bin detector:** YOLO11n round 4 (14 of 15 unseen bins found, 0 false hits on 429 empty images).

## 6. AI assistant and knowledge
- **Assistant:** answers questions about the lab, labs' locations, devices, bookings and robots from the portal's data and the knowledge vault.
  - Model: qwen2.5:1.5b on the GPU, approved 19 Oct; revert to CPU if a camera suffers.
  - Today: "where is the X lab" answers in one line.
- **To check:** `tools/knowledge/config.json` names `qwen2.5:3b`, which is not installed. The running assistant uses 1.5b.
  Confirm which one the knowledge service actually loads.
- **Knowledge vault (Obsidian):**
  - `C:\Users\dell\SmartLabKnowledge\vault`, 806 notes;
  - sections: Home, Project, Systems, n8n Workflows, Database, Runbooks, Incidents and Lessons, Decisions, Generated Reports,
    Automation Inbox;
  - broken links fixed from 27 to 0 on 18 Nov.
  - Kept up to date by n8n workflows "Knowledge 1–3" (source sync, health check, weekly summary).
- **Voice:** offline Piper voice (`en_US-lessac-medium`) and offline speech-to-text (Whisper tiny.en) on the Scan page.

## 7. n8n automations (live: 26 of 26 active)
| # | Workflow | # | Workflow |
|---|---|---|---|
| 01 | Booking confirmation briefing | 14 | Environment / bin node offline |
| 02 | Upcoming booking reminders | 15 | Consumable below reorder level |
| 03 | Access denial intelligence | 16 | Stock change with nobody inside |
| 04 | Device offline alert with escalation | 17 | Reusable item overdue |
| 05 | Maintenance automation | 18 | Robot offline or fault |
| 06 | Daily lab report | 19 | Robot running without a booking |
| 07 | Weekly lab report | 20 | Lab PC offline |
| 08 | Sensor threshold alerts | 21 | Exam-mode reports |
| 09 | Pre-booking lab readiness check | 22 | Robotics Lab daily summary |
| 10 | Post-session follow-up | 23 | Emergency: warn people inside, check the door |
| 11 | Daily data quality check | K1 | Knowledge: local source sync |
| 12 | Rule-based anomaly detection | K2 | Knowledge: vault health check |
| 13 | Environment hazard escalation | K3 | Knowledge: weekly summary |

- Copies of the workflows are in the repo under `automation/n8n/`.
- Backup from 18 Nov: `D:\SmartLabData\n8n_backup_20261118`.

## 8. Robots and lab PCs (at GIU)
- **UR5e and FANUC:**
  - digital twins in the portal, fed by read-only collectors (UR RTDE, OPC UA);
  - last seen 18 Nov 18:39;
  - every control route stays UNAVAILABLE until the owner signs off commissioning.
  - Sim robots `UR5E_SIM` and `FANUC_SIM` are retired from alerts.
- **Lab PCs:**
  - 14 registered, last seen at GIU;
  - features: screen wall, screen share, message all, maintenance / shutdown countdown, exam mode.
- **Network note:** two routers use 192.168.1.1. Power the robots (.100 FANUC, .102 UR5e) before Hemaly's PC.

## 9. Portal data (live)
| Item | Count |
|---|---|
| Users | 10 (9 active, 1 waiting for approval, kept to show the approval feature) |
| Labs | 11 |
| Bookings | 26 |
| Door / access events | 2,384 (211 in the last 24 h) |
| Consumable bins / items | 1 bin, 2 items |
| Open alerts | 272 (816 in total) |

**Open alerts are mostly old lab-day noise, not current faults:**

| Alerts | Count | Last |
|---|---|---|
| Movement at equipment with nobody there | 43 | 18 Nov |
| PC agent restarted | 37 | |
| UR5e fault reported | 15 | 14 Oct |
| Forced entry, door tests | 7 | 8 Nov |
| Equipment moved / robot moved | rest | |

Bulk-resolving them before the defense would make the dashboard honest. This is an owner decision: resolving keeps the rows.

## 10. Tests
| Suite | Result |
|---|---|
| Backend | **875 passed**, 3 skipped (today, includes all 20–21 Nov work) |
| Face server | 22 passed (today) |
| Security cameras | 396 passed (18 Nov) |
| Robot monitor | 44 passed (18 Nov) |
| Knowledge | 64 passed (18 Nov) |
| PC agent | 40 passed (18 Nov) |
| Frontend | TypeScript + production build OK (21 Nov) |

## 11. Code, backups, documents
- **Git:** branch `fix/pre-lab-hardening`, HEAD 3758fa9.
  - 79 commits ahead of `origin/main`, **not pushed** (owner pushes when ready).
  - Untracked on purpose: the showcase videos and old report folders.
- **Database dumps:** `D:\SmartLabData\db_dumps\` (latest before a schema change: `before_bin_items_20261120.dump`).
- **Key documents:**
  - `docs/PROGRESS_CHECKPOINT.md` (running log);
  - `docs/reports/MEASUREMENTS_2026-11-21.md` (measurements);
  - `docs/hardware/BILL_OF_MATERIALS.md` (prices still blank);
  - `reports/final-smart-lab-closure-2026-11-18/` (final reports, showcase video V2 5:49 + 720p, and the Gemini video review prompt).

## 12. Open items
| Who | Item |
|---|---|
| Owner, parts | Buy the 1N4007 (×5) + new buzzer → fit the diode → 20-relock test |
| Owner, home | Move all boards onto the second charger → I run the 30-ping check. Optional: a USB power meter for node power draw |
| Owner, home | Start `launch.bat` from Explorer when cameras / face / assistant are needed |
| Owner, decision | Bulk-resolve the 272 old alerts before the defense? |
| Owner, Gemini | Run `GEMINI_SHOWCASE_VIDEO_REVIEW_PROMPT.md`, then I verify its findings |
| GIU | Robots before Hemaly's PC, then the twin check; PC-10 agent update 0.9 → 1.0; PC-11 sticker; assistant timing with both cameras running |
| Thesis | Paste the corrections, add the measurements, BOM prices, acknowledgements, Eng. Shehab's title, film decision |
| Later | Change passwords; push to GitHub when approved |
| Me (to check) | Knowledge config names qwen2.5:3b (not installed): confirm the model in use |
