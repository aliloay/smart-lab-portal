# Final integration release candidate - status and handoff (2026-11-18, ~01:00)

> **SUPERSEDED (2026-11-18 ~10:30): every NOT-DONE item below was completed or classified. Read FINAL_EXECUTIVE_SUMMARY.md.**

Session stopped at the usage limit. Everything below is verified; anything not listed is NOT done.

## Where it is
- Worktree `C:\Projects\smart-lab-release`, branch `release/smart-lab-final-optimization-2026-11-17` (local only, NOT pushed).
- Base: owner's `fix/pre-lab-hardening` @ 4e58b52. Safety branch `backup/before-final-integration-2026-11-18` = 4e58b52.
- Main checkout, Claude worktree, Argon worktree: untouched (no edits, no branch switches).

## Commit map (original SHAs preserved by --no-ff merges, no cherry-picks)
| Integrated | Contents |
|---|---|
| e70db0e merge | Claude d085b73 (lazy framer-motion) + 5314195 (incident cap after filters) |
| c49fa07 merge | Argon fe126b7 (cross-cam UR5e veto, partial pose, GPU gate STREAMING, knowledge /health + qwen2.5:1.5b, relay bind fallback, USB kit EOL, watchdog, camera-2 guard, firmware source fixes, Argon reports) |
| 35f8cb4 | pose parts PREDICTED not OBSERVED (no keypoint model); labmap lock retries Windows delete-pending PermissionError; face-server test fixture cwd-independent |
| bdc41aa | build stamp from docker build args (stale 1be41ab root cause); deploy.py uses real `docker build`; tools/deploy/build_images.ps1; frontend /version.json |
| b685a43 | incidents: SQL-side state/lab filters, view=summary, keyset cursor (limit/before/next_cursor); portal "Load older"; camera activity contract test |
Branches had zero file overlap; merges were conflict-free. Argon identity code reviewed line by line (veto only stricter; labmap pass merge behaviour-equivalent).

## Tests (evidence class UNIT TEST unless noted)
- Backend full suite on merged tree (before b685a43): 823 passed, 3 skipped, 0 failed (404.8 s). Targeted after b685a43: 30/30.
  FULL RERUN AFTER b685a43 NOT YET DONE.
- security_vision 363 passed / 22 skipped (two-writer labmap test 13/15 before fix, 25/25 after).
- knowledge 49, robot_monitor 42 (py3.12), ur5e_control 20 (py3.12), opcua 3 (py3.12), relay 6, pc_agent 40,
  lan_presence 6, ops 28, voice 6, face_server 14+1 skip, door entry 4, benchmarks 6.
- MCP e2e vs live backend (LIVE LOCAL SOFTWARE, read-only, 10-min token): 8/8 incl. unlock_door refused.
- Frontend: tsc 0 errors; vite build ok (motion chunk 26.32 kB gzip); unit 7/7.

## Measurements (LIVE LOCAL SOFTWARE, 20 req, backend container, while a test DB ran)
incidents?state=ACTIVE p50 32.4 / p95 42.4 ms, 134,813 B, 195 rows; incidents (all) p50 56.3 ms, 268,670 B;
alerts?limit=50 p50 15.5 ms 63,878 B; devices 22.8 ms; bookings 19.9 ms; others 4.6-8.8 ms.
DB EXPLAIN ANALYZE: incidents scan 1.4 ms (cost is Python serialization); ACTIVE uses ix_alerts_is_resolved;
newest-reading-per-metric 2-4 ms (composite index used for silent metrics); automation.sensor_evaluation
full scan of 166,862 sensor_readings = 84 ms, called every 10 min by n8n 08 -> P3, not changed.
AFTER-numbers for incidents need the new images deployed (not done).

## Findings not changed (documented decisions)
- Backend activity allowlist kept: partial/pose_visibility not stored (portal does not need them).
- Ollama: only qwen2.5:1.5b + nomic-embed-text installed; every default now 1.5b. Argon's "timed out" bench
  NOT re-measured yet (no model loaded, GPU idle at check time).

## NOT DONE (next session, in order)
1. Full backend suite rerun on HEAD b685a43 (`$env:COMPOSE_ENV_FILES='C:\Projects\smart-lab-portal\.env'` then tools\ops\test_backend_fast.ps1 from this worktree).
2. Local deploy: DB dump first; `tools\deploy\build_images.ps1` (tags rollback point) -> `docker compose up -d --no-deps backend frontend`
   -> check /api/health version.id and /version.json -> re-run scratch bench for after-numbers. Rollback tags exist
   (smart-lab-portal-backend:pre-incidents-20261117, frontend:pre-lazymotion-20261117).
3. Firmware compile: arduino-cli is the Arduino IDE bundled one; ESP32-CAM MUST use core 3.2.1 (isolated data dir),
   others core 3.3.12. Flashing = owner approval, NOT RUN.
4. Bounded Ollama benchmark (first token / full / tokens/s, warm vs cold) + factual checks.
5. Role click-through USER/LAB_STAFF/ADMIN (needs E2E creds or test copy :5176/:8100) and realtime event-to-UI latency.
6. The 19 required reports; markdown inventory (Haiku agent output in session scratch, may be partial).
7. Physical/GIU blockers unchanged: firmware not flashed, student-PC firewall (GIU IT), UR5e floor point (x=1.4, y=3.2), live two-camera tests.
