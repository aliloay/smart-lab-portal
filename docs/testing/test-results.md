# Test results

| Suite | Command | Result | Date |
|---|---|---|---|
| Backend | `docker compose run --rm --no-deps -T -v "${PWD}\backend:/app" backend python -m pytest -q -p no:cacheprovider` | 753 passed, 2 skipped (after fixing a midnight-boundary test; first run 752 passed, 1 failed) | 9 Nov 2026 |
| Security vision | `py -m pytest -q tools/security_vision` | 297 passed | 9 Nov 2026 |
| Knowledge | `py -m pytest -q tools/knowledge` | 49 passed | 9 Nov 2026 |
| Robot monitor | `py -m pytest -q tools/robot_monitor` | 43 passed | 9 Nov 2026 |
| PC agent | `py -m pytest -q tools/pc_agent` | 40 passed | 9 Nov 2026 |
| Relay | `py -m pytest -q tools/relay` | 5 passed | 9 Nov 2026 |
| Frontend types | `npx tsc --noEmit -p frontend` | pass | 9 Nov 2026 |
| Frontend build | `npx vite build` (in `frontend/`) | pass (chunk-size warning only) | 9 Nov 2026 |
| Fresh clone | Clone, `.env` from the example, `docker compose config`, frontend `npm ci` + build | pass | 9 Nov 2026 |
| Launch script | `launch.ps1` parser check; full clean-clone launch on alternate ports | parser 0 errors; full launch: see GITHUB_FINAL_RELEASE_REPORT.md | 10 Nov 2026 |
| Live deployment | Backend + frontend rebuilt, migration `f1a7c3d9e250` applied, health 200 | pass | 9 Nov 2026 |

## Not testable here

Physical behaviour needs the hardware and the lab: door and lock, sensors, load cell, servo, cameras with people, robots, lab PCs. Their recorded results are in [hardware-validation.md](../hardware/hardware-validation.md). The formal offline run (internet disconnected) and a real-phone AR measurement are open ([KNOWN_ISSUES.md](../../KNOWN_ISSUES.md)).
