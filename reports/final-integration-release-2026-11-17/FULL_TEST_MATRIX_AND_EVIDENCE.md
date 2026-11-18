# Full test matrix and evidence

Machine-readable: `test_results.csv`. Every result names where it ran and its evidence class. Logs are kept in the
session scratch folder (not committed: they include local paths and timing noise).

## Automated suites on the integrated release tree
| Suite | Result | Class |
|---|---|---|
| Backend, full (tools/ops/test_backend_fast.ps1) | 823 at c49fa07 (merge) -> 826 at b685a43 -> **828 passed / 3 skipped / 0 failed at 279c625** | UNIT TEST |
| Backend, assistant + AI + camera-activity files at 279c625 | 33 / 33 | UNIT TEST |
| tools/security_vision | 363 passed / 22 skipped / 0 failed | UNIT TEST |
| tools/knowledge | 49 | UNIT TEST |
| tools/robot_monitor (Python 3.12) | 42 / 1 skipped | UNIT TEST |
| tools/ur5e_control (Python 3.12) | 20 | UNIT TEST |
| tools/opcua (Python 3.12) | 3 | UNIT TEST |
| tools/relay, pc_agent, lan_presence, ops, voice | 6, 40, 6, 28, 6 | UNIT TEST |
| firmware/face_server | 14 / 1 skipped (from the repo root and from its folder) | UNIT TEST |
| door test entry, benchmarks | 4, 6 | UNIT TEST |
| MCP end-to-end vs the live backend | 8 / 8 | LIVE LOCAL SOFTWARE |
| Frontend tsc / vite build / unit | 0 errors / ok / 7 of 7 | STATIC / UNIT TEST |
| Firmware compile, 7 projects | 7 / 7 | STATIC INSPECTION |

## Failures found during integration, and what happened to them
| Failure | Root cause | Outcome |
|---|---|---|
| labmap two-writer test (intermittent, 13/15) | Windows delete-pending PermissionError escaped the lock | fixed; 25/25 |
| face_server 6 failed when run from the repo root | ENGINE fell back to LBPH (relative model paths; models git-ignored) | test fixture fixed; the service was correct |
| opcua and mcp_server collection errors | wrong interpreter (asyncua is on Python 3.12; mcp has its own venv) | ran with the documented interpreter: 3 / 3, 8 / 8 |
| incidents cursor test (422) | an ISO "+" in the cursor became a space when unencoded | cursor changed to digits only |
| node-capabilities test (KeyError) | the test called the staff-only /ai/ask as a student | test uses /ai/student/ask; code correct |
| live_bin e2e timeout | a fresh seeded DB has no REUSE_BIN_1 | registered with one synthetic heartbeat on the throw-away DB |

## Live / isolated runs (release images)
- navigation.mjs: 98 checks, 0 problems (student / staff / admin; direct links, reloads, expired session).
- workflows.mjs: 30 / 30.
- live_bin.mjs, 30 trials: single viewer median 26 ms, p95 35 ms; under 10-client load median 261 ms, p95 359 ms. 0 problems in both runs.
- Deploy check: /api/health and /version.json show the expected stamp. Rollback images boot (backend imports, nginx -t).
- API bench before / after and DB EXPLAIN: see PORTAL_BACKEND_DATABASE_REALTIME_AUDIT.md.
- Ollama bench: see AI_RAG_VOICE_ASSISTANT_LATENCY_AUDIT.md.

## Not run (with class)
Live two-camera tracking, door / tablet / TFT hardware, UR5e / FANUC live telemetry, device-to-portal latency, student
PCs through the relay: BLOCKED (on campus / GIU IT). Firmware flashing: NOT RUN (owner on site). Real-account
click-through: BLOCKED (credentials not available to agents).
