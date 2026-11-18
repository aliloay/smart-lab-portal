# Final executive summary: Smart Lab integration release candidate (2026-11-18)

**One local release candidate now exists, and it is deployed to the local portal.** The Claude and Argon optimization
branches were merged on top of the owner's branch, reviewed line by line and tested as one system. The integration
review found eight further defects, all fixed and verified.
- Branch: `release/smart-lab-final-optimization-2026-11-17`
- Worktree: `C:\Projects\smart-lab-release`
- Nothing was pushed.

## What is running locally now
- **backend** `7e3ed3b46b8e` (stamp 279c625-20261118101511)
- **frontend** `86c0df1dc030` (df3407f)
- Both healthy. The db, n8n and backup containers were untouched, and no migration was made.
- DB dump taken before the deploy: backups/predeploy_rc_20261118_0939.dump.
- Rollback tags: `pre-rc-20261118` (both images) and `pre-assist-20261118` (backend). The rollback images were verified to boot.

## Integration
- **Verified graph:** Claude's branch sits on 4e58b52; Argon's on c68adb0. The two branches share 0 files, and both merges were conflict-free with original SHAs preserved.
- **Argon's identity changes** only make matching stricter (confirmed-identity veto, no lab-number merge across different names).

## Defects found and fixed during integration
| # | Fix | Proof |
|---|---|---|
| 1 | Pose parts were claimed OBSERVED without a keypoint model; now PREDICTED (box geometry) | +1 test |
| 2 | Camera lab-number register lock failed under two processes (Windows delete-pending) | 13/15 -> 25/25 |
| 3 | /api/health reported a 28 Oct build; deploy.py could not build. Stamp now from build args; web /version.json added | live: both report the running build |
| 4 | Incidents list (polled every 20 s): SQL-side filters, summary rows, keyset cursor, "Load older" | 134.4 -> 81.4 kB raw, 11.7 -> 7.0 kB on the wire, p50 23.4 -> 20.0 ms (same run) |
| 5 | Assistant answered stock questions with "no access" via the LLM (25.8 s) | instant from records, 33 ms live |
| 6 | Assistant answered "is the door open?" with fingerprint refusals | instant door-contact state with its age; old data said to be old; 30 ms live |
| 7 | LLM benchmark: "The bin measured the capacitance." | node capabilities now a fixed instant answer (9.5 ms) |
| 8 | Face-server tests depended on the working directory (service code was fine) | 14/14 + 1 skip from any folder |

## Verification
- **Unit tests:**
  - Backend: **828 passed / 3 skipped / 0 failed**
  - Cameras: 363 passed / 22 skipped
  - Other tool suites: 228 passed
  - Frontend: tsc 0 errors, build ok, unit 7/7
  - MCP end-to-end against the live backend: 8/8 (no physical tool reachable)
- **Isolated copy of the release images:**
  - Role navigation (student / staff / admin): 98 checks, 0 problems
  - Workflows: 30/30
  - Realtime push to painted card: 26 ms median single viewer; 261 ms median under 10-client load (113 req/s, 0 errors, 0 missed or duplicate pushes)
- **Database:** key query plans 1.3-4 ms; one 84 ms full scan every 10 min (P3).
- **Local LLM** (qwen2.5:1.5b, GTX 1650): first token 0.19 s, 76 tok/s, quality 0.68 on 11 cases. Argon's timeout was not reproducible with more than 2 GB free RAM (probable cause: paging during a cold load).
- **Firmware:** 7/7 ESP32 projects compile (placeholder secrets). Nothing was flashed.
- **n8n:** 26 workflows, read-only audit. The 373 errors since 10 Nov are explained (knowledge service off; deploy windows).
- **Obsidian:** a real, project-generated vault; health shows 27 broken links (P3, mirrored README images).

## Second round, 18 Nov (owner: install the core, fix n8n / Obsidian, get ready for uni)
- **Main checkout:** fast-forwarded to the release branch, so launch.bat at the lab runs the integrated code. The untracked Argon report copies (identical) were backed up to D:\SmartLabData\main_untracked_backup_20261118 first.
- **n8n:**
  - Backup in D:\SmartLabData\n8n_backup_20261118.
  - 18 scheduled read nodes and 4 knowledge job nodes retry 5x / 5 s.
  - Notify / alert POSTs and the webhook workflows (incl. emergency) untouched.
  - 26/26 active after publish + restart.
  - Knowledge service started and reachable from n8n; its jobs return 200.
- **Obsidian:** 27 -> 0 broken links. Root cause: kb.py's fnmatch took the generated vault copies in as sources.
- **Legacy reusable sketch:** guarded with `#error` (same REUSE_BIN_1 id, LAB_ID BENCH).
- **esp32 core 3.2.1:** installed in an isolated data dir (D:\SmartLabData\arduino_core321) for the ESP32-CAM image. See ESP_FIRMWARE_AUDIT_EACH_NODE.md for the build result.
- **Uni checklist:** LAB_DAY_UNI_CHECKLIST_2026-11-18.md. The 4 ESP nodes stay home; the door is offline today, by plan.
- **Passwords:** kept by owner decision until the lab verification is finished.

## Owner actions (in BLOCKERS_AND_NEXT_PHYSICAL_LAB_ACTIONS.md)
1. **P0, after the lab verification (owner decision): change the published default passwords** of admin@giu-uni.de and ramy@giu-uni.de (`set_password.py`).
2. **GIU IT:** open the relay ports on S2PC136 for the lab subnet.
3. **Next lab visit:**
   - Flash BIN_NODE_1, REUSE_BIN_1 and the ESP32-CAM (the CAM needs core 3.2.1 — approve the install or use the known-good image).
   - Camera 1 floor point (x=1.4, y=3.2).
   - A labelled live two-camera run.
   - Door / tablet / TFT and UR5e / FANUC live checks.
4. **n8n:** add retryOnFail on the HTTP nodes.
5. **Push** when satisfied.

## Honest limits
- No live camera, door, robot or student-PC result in this release. All of those are BLOCKED off-site and are labelled so.
- Camera continuity figures are historical replay and simulation only.
- No "perfect tracking" claim is made.

## Report index
REPOSITORY_WORKTREE_AND_COMMIT_MAP · COMPLETE_PROJECT_AND_MARKDOWN_INVENTORY (+ markdown_inventory.csv,
source_inventory.csv) · SYSTEM_ARCHITECTURE_AND_DATA_FLOWS (+ service_inventory.csv) · ESP_FIRMWARE_AUDIT_EACH_NODE
(+ firmware_compile_results.jsonl) · PORTAL_BACKEND_DATABASE_REALTIME_AUDIT · SECURITY_RBAC_AND_PRIVACY_AUDIT ·
CAMERA_TRACKING_FLOOR_MAP_AND_DESK_MAP_AUDIT · DIGITAL_TWINS_PC_AGENTS_RELAY_AND_LAB_NETWORK_AUDIT ·
AI_RAG_VOICE_ASSISTANT_LATENCY_AUDIT (+ ai_benchmark_results.json) · N8N_AND_OBSIDIAN_INTEGRATION_AUDIT ·
TABLET_DOOR_TFT_AND_ENCLOSURE_AUDIT · INTEGRATION_FIXES_IMPLEMENTED · FULL_TEST_MATRIX_AND_EVIDENCE (+ test_results.csv) ·
BEFORE_AFTER_PERFORMANCE_BENCHMARKS (+ performance_metrics.json) · BLOCKERS_AND_NEXT_PHYSICAL_LAB_ACTIONS (+ blockers.csv) ·
CHANGED_FILES_COMMITS_AND_ROLLBACK (+ branch_commit_integration.json) · STARTUP_SHUTDOWN_AND_LIVE_DEMO_RUNBOOK ·
THESIS_READINESS_AND_CLAIMABLE_RESULTS
