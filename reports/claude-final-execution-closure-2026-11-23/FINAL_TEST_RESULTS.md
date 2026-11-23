# Final test results - 23 Nov 2026

**Code tested:** `d023e98` plus the closure changes (worktree `C:\Projects\smart-lab-claude-closure`; the camera suite was run from the main checkout, which holds the same code plus the model files).

| Suite | Command | 22 Nov report | 23 Nov result | Note |
|---|---|---|---|---|
| Backend | `tools\ops\test_backend_fast.ps1` (throw-away in-memory PostgreSQL, never the live DB) | 902 passed, 3 skipped | **903 passed, 3 skipped, 0 failed** (22 min 43 s, CPU shared with the video render) | +1: C-01 test |
| Backend focus | same, `tests/test_closure_2026_11_23.py tests/test_face_submissions.py` | - | 1 failed **before** the C-01 fix; 20 passed after | proves the test catches the bug |
| Cameras | `py -m pytest -q tools/security_vision` (main checkout, models present) | 412 passed, 1 skipped | **413 passed, 2 skipped** | +2 tests (V-F10, V-F12). Both fail with the fix removed. In the worktree without model files: 393 passed, 22 skipped |
| Knowledge | `py -m pytest -q tools/knowledge` | 80 | **82 passed** | +2: C-03, C-06 |
| Robot monitor | `py -m pytest -q tools/robot_monitor` | 43 + 1 skipped | 43 passed, 1 skipped | unchanged |
| PC agent | `py -m pytest -q tools/pc_agent` | 40 | 40 passed | unchanged |
| Relay | `py -m pytest -q tools/relay` | 6 | 6 passed | unchanged |
| Face server | `py -m pytest -q firmware/face_server` | 21 + 1 skipped | 21 passed, 1 skipped | unchanged |
| Frontend types | `npx tsc --noEmit -p frontend` | 0 errors | **0 errors** | - |
| Frontend unit | `npm run test:unit` | 16 | **16/16 pass** | - |
| Frontend build | `npx vite build` | OK | **OK** (32 s) | chunk sizes in `PORTAL_AND_SYSTEM_OPTIMIZATION_RESULTS.md` |
| Static check | pyflakes over `backend/app` and `tools/` | - | no undefined names or real errors | 1 harmless escape warning in an offline helper |
| AI benchmark | `tools/perf/kb_latency_bench.py` | - | see `AI_PERFORMANCE_BEFORE_AFTER.md` | live service |
| Pose benchmark | `tools/perf/vf9_pose_bench.py` | not measured | see `V_F9_CPU_POSE_BENCHMARK.md` | offline, under load |
| Deployment health | `/api/health`, `/version.json`, login page | `unstamped` | ok, stamped `d023e98-dirty-20261123063157`, 200 | live-verified |

## Not tested (and why)
- **Camera behaviour on live streams:** the streams are unreachable from this network. NEEDS GIU HARDWARE.
- **ESP32 contracts end to end:** all five boards are offline (the Smart_Lab Ethernet link is down). The firmware and contract tests inside the backend suite pass, but no live heartbeat was seen. OWNER ACTION REQUIRED (reconnect).
- **Door relock:** hardware; OWNER ACTION REQUIRED (1N4007, then the 20-relock test).
