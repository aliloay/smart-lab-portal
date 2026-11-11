# Smart Lab - final test results (11 November 2026)

All runs on the owner's laptop, from `C:\Projects\smart-lab-portal`, branch `qa/browser-and-camera-docs` with the
uncommitted closure changes. Counts are per suite; they are not added together.

| Suite | Command | Result |
|---|---|---|
| Backend, full | `tools\ops\test_backend_fast.ps1` (in-memory test DB) | **775 passed, 2 skipped, 0 failed** - 12 min |
| Backend, full (earlier, live server's test DB, before the last 3 changes) | old docker compose command | 757 passed, 2 skipped, 1 failed: `test_robots::...disagreement_after_hold`; passed in the targeted re-run (121 passed) - intermittent timing |
| Security vision (cameras) | `py -m pytest -q tools/security_vision` | **328 passed** |
| Camera scenario bench (simulated, 14 scenarios) | `py tools/security_vision/scenario_bench.py` | **0 false names, 0 name switches, 0 ID switches** |
| Knowledge | `py -m pytest -q tools/knowledge` | 49 passed |
| PC agent | `py -m pytest -q tools/pc_agent` | 40 passed |
| Robot monitor | `py -m pytest -q tools/robot_monitor` | 43 passed |
| UR5e control (dry run) | `py -m pytest -q tools/ur5e_control` | 20 passed |
| Voice | `py -m pytest -q tools/voice` | 6 passed |
| LAN presence | `py -m pytest -q tools/lan_presence` | 6 passed |
| Relay | `py -m pytest -q tools/relay` | 5 passed |
| OPC UA | Python 3.12: `-m pytest -q tools/opcua` | 3 passed |
| Watchdog | `py -m pytest -q tools/ops` | 3 passed |
| MCP end-to-end | - | **not run**: pytest is not installed in tools/mcp_server/.venv (needs the owner's OK to install) |
| Frontend type check | `npx tsc --noEmit -p frontend` | 0 errors |
| Frontend build | `npx vite build` | built (chunk-size warning only) |
| Frontend node tests | `node --test e2e/*.test.mjs` (3 files) | **15 / 15** - one test updated to the 3 Nov PC-status rule (a live agent wins over the LAN scan) |
| Compose file | `docker compose config -q` | valid |

## Live checks after deployment (11 Nov)

| Check | Result |
|---|---|
| `/api/health` | ok, database true |
| New endpoints exist (`/auth/ws-ticket`, `/ai/ask/stream`, `/ai/student/ask/stream`) | 401 without sign-in (present, protected) |
| Door report without a key (`/access/grant`) | 401 |
| Served frontend contains the new code | ticket socket, streamed answers, live camera bar, "guess by look", create_issue |
| Watchdog snapshot | 11 / 11 services up |
| Docker disk move | same 5 volumes; row counts identical (users 8, access events 2,005, audit logs 16,756, devices 26) |
| Project move | 94,096 files, 11,741,328,078 bytes identical in old, new and D: backup |

## Not tested (needs the lab)

Real two-person walks with both cameras, camera analysis rate with both live, AR on a phone, assistant
time-to-first-word with the cameras running, load test with 50-100 users. See
SMART_LAB_FINAL_PHYSICAL_ACCEPTANCE_CHECKLIST.md.
