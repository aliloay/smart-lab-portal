# Complete code and system audit: Smart Research Laboratory (GIU)

| | |
|---|---|
| Auditor | Claude, independent session |
| Date | 2026-11-21, 19:06–19:45 local (UTC+2) |
| Local HEAD | `f32d7b3` on `fix/pre-lab-hardening` |
| GitHub | `35d2a10` on `main` and `fix/pre-lab-hardening` |
| Live images | backend `a0814c7-20261121185827`, frontend `8fcef6f-20261121155020` (both equal HEAD source) |
| Rules followed | read-only; no restarts, DB writes, flashing, n8n runs, robot or door actions, installs or pushes |
| Independence | Gemini/other-model reports not opened |

**Detail reports:**

- BACKEND_AND_API_AUDIT.md
- FRONTEND_AND_PORTAL_PERFORMANCE.md
- CAMERA_PIPELINE_AND_TRACKING_AUDIT.md
- TWO_CAMERA_ARCHITECTURE_AND_BENCHMARK_PLAN.md
- AR_RECOGNITION_AND_UX_REVIEW.md
- AI_LATENCY_AND_MODEL_CONFIGURATION_AUDIT.md
- OBSIDIAN_AND_KNOWLEDGE_GRAPH_REVIEW.md
- FAQ_FAST_ANSWER_PROPOSAL.md
- ESP32_AND_WIFI_CONNECTIVITY_AUDIT.md
- ROBOTS_AND_DIGITAL_TWINS_AUDIT.md
- PC_FLEET_AND_HEMALY_RELAY_AUDIT.md
- N8N_WORKFLOW_AUDIT.md
- TERMINAL_PROCESS_AND_RESOURCE_INVENTORY.md
- GITHUB_LOCAL_REMOTE_REVIEW.md
- DATABASE_BACKUP_AND_ALERT_AUDIT.md
- **Findings:** PRIORITIZED_FINDINGS.csv (26 rows)

## 1. Live environment reconstruction

### Docker (`docker compose ps`)

| Service | Image | State |
|---|---|---|
| db | postgres:16-alpine | 127.0.0.1:5433, up 7 h, healthy |
| backend | – | 8000, up 9 min, healthy (redeployed by the owner at about 18:58) |
| frontend | – | 80/443/8080/8443, up 3 h |
| n8n | 2.40.7 | 127.0.0.1:5678, healthy |
| backup | – | up 7 h, healthy |

### Helper services

- All were started by `launch.bat` at 15:50 except knowledge:
  - face 5000 ✔
  - camera 1 (5100) ✔ service, ✘ stream
  - camera 2 (5101) ✔ service, ✘ stream
  - voice 5320 ✔
  - OPC UA ✔
  - UR5e and FANUC collectors ✔ (no robots reachable)
  - PC agent ✔
  - LAN presence ✔
  - mDNS ✔
  - status watch ✔
- **Knowledge (5199):** served by an instance started at 17:23 through a `backend/.venv` shim chain. The launcher's own knowledge process died (F-12).

### The 15:22 / 15:51 discrepancy

- Current processes all start at 15:50:10–15:50:25, consistent with a launcher restart at about 15:50.
- I found no logs proving the 15:22 stop. Its cause is UNVERIFIED.

### Ollama

- 3 models resident, all on the CPU (F-05).
- GPU 918 MiB used, 0 % utilisation.
- RAM 6.1 GB free of 31.8 GB during the backend tests; page file usage 104 MB.

## 2. Backend

- **Tests:** 887 passed and 3 skipped.
- **Auth sweep:**
  - All non-public routes are guarded.
  - **F-01:** a recording-link JWT doubles as an admin Bearer token (P1).
  - Device keys, PC key scoping, door scope, OPC UA key and the PC enrolment gate are sound.
- **Approval flow:** works and is audited; edge cases in F-17.
- **Status and staleness guards:** correct (90 s stale; DEGRADED for a camera without a picture or a robot without joint data).
- **Robot UNKNOWN/STALE guard and presenter timeout (90 s):** present and correct.
- **Alert lifecycle:** the validator is correct; 3 legacy inconsistent rows remain (F-13).
- **Indexes:** adequate. The DB is 117 MB. No N+1 or unbounded memory problems of consequence.

## 3. Frontend

- tsc is clean.
- 38 lazy routes, GET deduplication and a cache, visibility-aware polling, `LazyMotion`.
- First load is about 227 KB gzip with immutable caching.
- **Opportunities:** the charts, robotModels and CSS sizes, and the `Scan.tsx` timers.
- Authenticated navigation timing and accessibility were not measured.

## 4. Cameras

- Services up; streams OFFLINE since 15:50 (IP cameras at GIU).
- Pipeline traced: RTSP → YOLO26s DirectML → IoU+appearance tracker → re-ID (`person_reid_youtu_2021nov.onnx`) → evidence-only Labeler → crosscam/labmap → activity/seat/equipment → backend.
- Naming thresholds are conservative ("never inherit a wrong name").
- **No pose model:** body parts are box-geometry PREDICTED (F-16).
- Recovery times and live metrics are **not measured**. A plan is provided.

## 5. AR

- **Active model:** v8 ft_y11s, 12 classes, server-side, every 3–6 s.
- Robots and nodes map 1:1 to devices. **Lab PCs have no identity** without a QR marker.
- The bin detector is inactive while the lab detector is loaded.
- Proposal: measure first, then add client-side box tracking, adaptive cadence, PC wording and 2-hit confirmation for low-threshold classes.

## 6. AI and knowledge

### Models

- Live: knowledge `qwen3:1.7b`, portal `qwen2.5:1.5b`, embeddings `nomic-embed-text`. All installed. The "3b" mismatch is gone from the live configuration.
- All models are resident on the CPU although the gate says GPU (F-05).

### Measured latency

| Path | Time |
|---|---|
| Lookup | 99 ms |
| Guard | 20 ms |
| Cache | 0 ms |
| Synthesis | 11.7 / 15.7 / 18.4 s |

- Prompt evaluation is 66 % of the time.

### Quality and vault

- One synthesis answer contained an invented statement.
- **Vault:** 810 notes, of which 322 are recursive mirrors of the repo vault snapshot; 182 unique broken wikilinks; 335 notes with no inbound link. The index is fresh (18:01).
- **Fast path:** 58 draft WH questions with sources, live/static split and auth level (FAQ_FAST_ANSWER_PROPOSAL.md).

## 7. ESP32 and network

- **All five reachable:** 0 % loss over 20 pings, average 8–20 ms. Heartbeats under 30 s old. Firmware versions match the source.
- **USB:** COM6 CP210x (held by the serial logger), COM7 and COM8 CH340. Identity not opened.
- **No RSSI telemetry.**
- **Network conflicts:**
  - Two routers at 192.168.1.1 on the same /24 (F-02).
  - .100 used by both FANUC and Hemaly's PC (F-03).
- **Consumables:** the logic handles sensor-invalid, uncalibrated and offline states. Today's data reads about 60 screws versus the owner's "empty" (F-10).
- **ESP32-CAM:** `/status` leaks the last booking QR (F-08). There is no compile guard for core 3.2.1 (F-20).
- **Door:** the diode is pending (F-24).

## 8. Robots

- Both collectors run, but no controller is reachable at home. Last data 18 Nov; UI shows OFFLINE/stale correctly.
- `ROBOT_CONTROL=off`: every adapter reports UNAVAILABLE. OPC UA is read-only.

## 9. PCs

- **14 rows:** 9 GIU lab PCs, Hemaly's PC, the admin laptop and 3 TEST cards.
- PC-10 still runs agent 0.9. PC-11 = `GIULAB20-PC14` (sticker unverified).
- Last GIU heartbeat: 18 Nov 17:28 UTC.
- Relay and agent tests pass; nothing live today.

## 10. n8n

- 26 workflow files are structurally valid. The live states could not be read (MCP refused).
- 15 workflows logged runs in the last 7 days, with 0 failures. Daily jobs missed since 18 Nov.
- No error workflow; no timeouts on 01–23; no retries on webhook flows, including emergency.
- The backup has 52 JSON files, all parsing.

## 11. Data and backups

- **Counts:** 10 users (1 pending), 11 labs, 26 bookings (no overlaps), 2,437 access events, 4 open alerts (264 resolved via the API today by the owner).
- **Backups:** every 6 h, last 15:58 UTC, TOC valid.
- **Gaps:** no retention (6.2 GB), no encryption (the uploads tar is never encrypted), no restore test (F-09).

## 12. Resources

- **Biggest real bottleneck today:** LLM inference on the CPU (7.7 s prompt evaluation).
- No paging pressure; GPU idle (cameras offline).
- Docker VM capped at 10 GB (using 3 GB).
- The heavy combined camera + AI comparison was **not possible** (cameras offline). No heavy benchmark ran concurrently with other tests: AI questions were asked after the backend suite finished.

## 13. Answers to the 36 final questions

| # | Question | Answer | Label |
|---|---|---|---|
| 1 | Is local source fully pushed? | **No.** 5 commits ahead of origin (`5b458f4`..`f32d7b3`). | LIVE-VERIFIED |
| 2 | Does GitHub have the same revision? | **No.** GitHub `35d2a10` vs local `f32d7b3`. No remote-only commits; fast-forward. Unchanged between 19:06 and 19:24. | LIVE-VERIFIED |
| 3 | Uncommitted or untracked changes? | No tracked changes. 8 untracked paths (old reports, 3 MP4s, a Gemini folder). | LIVE-VERIFIED |
| 4 | Sensitive or oversized files tracked? | No secrets or `.env` files tracked. Oversized: 37 MB ONNX, CAD STEP ×4 copies, 422 MB loose objects (gc). Check `docs/screenshots/users-roles.png` for names. | LIVE-VERIFIED |
| 5 | All five ESP32 boards connected? | **Yes** (network and heartbeats). 3 of 5 on USB. | LIVE-VERIFIED |
| 6 | Wi-Fi and packet loss acceptable? | **Yes:** 0 % loss, average 8–20 ms, max 54 ms. RSSI unavailable. | LIVE-VERIFIED / RSSI UNVERIFIED |
| 7 | COM ports correctly mapped? | COM6 CP210x / COM7 CH340 / COM8 CH340 match the documented master / bin / CAM. Ports not opened. | LIVE-VERIFIED (identity UNVERIFIED) |
| 8 | Both networks routed correctly? | Functionally yes (Ethernet metric 10 for 192.168.1.x, Wi-Fi default route), but only because of the metrics. | LIVE-VERIFIED |
| 9 | Router, subnet or IP conflict? | **Yes:** the same /24 with two routers at .1; FANUC and Hemaly's PC both at .100. | LIVE-VERIFIED / DB |
| 10 | Empty-bin state handled accurately? | Logic yes (sensor-invalid ≠ zero; offline after 90 s). Today's data shows about 60 screws, not empty: physical check needed. | CODE + LIVE data |
| 11 | Both camera services running? | Processes yes; **no picture** on either (OFFLINE). | LIVE-VERIFIED |
| 12 | Fast detection and fresh frames? | Not measurable today. Design: 6 analyses/s, latest-frame semantics. | UNVERIFIED |
| 13 | Body-pose / keypoint tracking implemented? | **No.** Box-geometry PREDICTED parts only. | VERIFIED FROM CODE |
| 14 | Head and limb measurements trustworthy? | **No.** They are estimates, not measurements. | VERIFIED FROM CODE |
| 15 | Recovery from dead zones? | Not measured. Code: track kept 2 s moving / 6 s still; name handback window 60 s; re-acquisition needs distance ≤ 0.18 and margin 0.10. | CODE / SIMULATED |
| 16 | Batching, stitching or shared tracking? | Shared global identity already exists. Stitching not recommended. Batching is the only candidate to benchmark. | ANALYSIS |
| 17 | Best measured architecture? | None measured live yet. Keep the current one until the GIU benchmark. | UNVERIFIED |
| 18 | What remains in phone AR? | Box cadence 3–6 s, no client tracking, PC identity, phone latency measurement, low-threshold false positives. | CODE |
| 19 | Which model is loaded? | `qwen3:1.7b`, `qwen2.5:1.5b` and `nomic-embed-text`, all on the CPU. | LIVE-VERIFIED |
| 20 | Config/model mismatch fixed? | Yes in live config. Stale only in `.env.example` comments and CLAUDE.md. | LIVE-VERIFIED |
| 21 | Short and long latencies? | Lookup 0.1 s; guard 0.02 s; one-liner via synthesis 11.7 s; RAG 15.7 s; multi-document 18.4 s (CPU). | TESTED |
| 22 | Fast path for WH questions? | **Yes.** Intent + entity matching for FAQ and live lookups; draft of 58 questions. | ANALYSIS |
| 23 | Obsidian needs more material? | Little. Mainly remove mirrors, mirror the n8n JSON, fix links, add per-subsystem fact notes. | VERIFIED |
| 24 | Graph and embeddings current? | Index 18:01 today (13,292 chunks). Current. | LIVE-VERIFIED |
| 25 | Citations and grounding reliable? | Partly. Citations are validated and labelled, and the guard works, but 1 of 3 synthesis answers contained an invented statement. | TESTED |
| 26 | Navigation smooth and fast? | Load path fast (227 KB gzip, 21 ms HTML). Authenticated transitions not measured. | LIVE / UNVERIFIED |
| 27 | APIs and routes free of regressions? | Tests green. One security bug found in review (F-01). | TESTED / CODE |
| 28 | All n8n workflows valid? | Structurally yes (26/26). Robustness gaps. Live active state unverified. | CODE + DB |
| 29 | All 14 PCs and Hemaly's relay correct? | No. PC-10 on agent 0.9; 3 of the 14 rows are TEST cards; Hemaly .100 conflict; telemetry historical. | DB |
| 30 | Twins showing current telemetry? | **No.** Last data 18 Nov, correctly shown OFFLINE. | LIVE-VERIFIED |
| 31 | Admin notification and approval reliable? | Yes for the normal path (notify, audit, admin-only activation); P3 edge cases. | CODE + TESTS |
| 32 | Fully verified features? | See THESIS_EVIDENCE_GAPS.md: portal/auth, ESP32 reporting, robot lockout, backups, n8n runs, knowledge retrieval/guard, frontend load, offline logic of all subsystems. | – |
| 33 | Historical recordings only? | Live camera tracking, twins, PC fleet/relay/screen wall, AR accuracy, door timings, GPU AI latency. | – |
| 34 | Claims with no evidence? | Real dead-zone recovery, live ID-switch rate, pose, phone AR latency, RSSI, backup restore, batching benefit, "26/26 active" today. | – |
| 35 | Needs physical GIU attendance? | Cameras, robots + IP fix, Hemaly PC/relay, PC-10/PC-11, AR on robots/PCs, AI timing under camera load, face re-enrol. | – |
| 36 | 10 next actions? | See the list below and EXECUTIVE_SUMMARY.md. | – |

### Next actions

1. F-01 fix.
2. AI GPU reload plus FAQ/live fast path.
3. Re-tare the bin.
4. 1N4007 diode + 20 relock cycles.
5. GIU network fix (Hemaly IP), then robots.
6. GIU camera benchmark.
7. Push.
8. Backup retention, encryption and a restore test.
9. Vault clean-up and rebuild.
10. Thesis wording corrections.
