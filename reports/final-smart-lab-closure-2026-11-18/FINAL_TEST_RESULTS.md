# Final test results (19 Nov 2026, home laptop)

**Code under test:** `fix/pre-lab-hardening` @ `ecbb167`. That is the 18 Nov lab work + the opt branch merged (`fc18c99`) + the AI fixes (`7619717`, `b2f89e8`) + the test contract fix (`ecbb167`).
**Deployed images:** backend `034e51c2a97b`, frontend `f24859878193`, stamp `ecbb167-20261118231702`.
**Rollback tags:** `smart-lab-portal-{backend,frontend}:pre-merge-20261119`.
**Pre-deploy DB dump:** `D:\SmartLabData\db_dumps\predeploy_2026-11-19.dump` (4.8 MB).

## Automated suites

| Suite | Command | Result | Label |
|---|---|---|---|
| Backend (FastAPI), full | `tools\ops\test_backend_fast.ps1` | **841 passed, 1 failed, 3 skipped** (9 min 37 s) → the failure was the old "pose_visibility dropped" contract test conflicting with 77b0702 after the merge; test updated to the validated-passthrough contract → `test_camera_activity.py` + `test_security_visibility.py` **8 passed** | TESTED — PASSED (after fix) |
| Security cameras | `py -3.14 -m pytest -q tools/security_vision` | **396 passed** | TESTED — PASSED |
| Robot collector | `py -3.12 -m pytest -q tools/robot_monitor` | **44 passed** | TESTED — PASSED |
| Knowledge / AI assistant | `py -3.14 -m pytest -q tools/knowledge` | **64 passed** (14 new) | TESTED — PASSED |
| PC agent | `py -3.14 -m pytest -q tools/pc_agent` | **40 passed** | TESTED — PASSED |
| Relay (engineer PC) | `py -3.12 -m pytest -q tools/relay` | **6 passed** | TESTED — PASSED |
| LAN presence | `py -3.12 -m pytest -q tools/lan_presence` | **6 passed** | TESTED — PASSED |
| Voice | `py -3.12 -m pytest -q tools/voice` | **6 passed** | TESTED — PASSED |
| OPC UA | `py -3.12 -m pytest -q tools/opcua` | **3 passed** | TESTED — PASSED |
| Frontend types | `npx tsc --noEmit -p frontend` | exit 0 | TESTED — PASSED |
| Frontend build | `npx vite build` | built in 21.9 s (chunk-size warning only) | TESTED — PASSED |

Note: a bare `py -m pytest` (default interpreter) fails at import for the camera and PC-agent suites, because that interpreter lacks `requests`/`psutil`. Use the interpreter each service runs on (3.14 for cameras and PC agent, 3.12 for robots).

## Live checks on the deployed portal (https://127.0.0.1, read-only)

| Check | Result | Label |
|---|---|---|
| `/api/health` | `status ok`, `database true`, version `ecbb167-20261118231702` (was "unstamped") | FIXED AND VERIFIED |
| `/version.json` (frontend) | `ecbb167-20261118231702` | FIXED AND VERIFIED |
| Sign-in + 7 main APIs (me, equipment, devices, cameras, robots, incidents, labs) | all 200, 14–179 ms | TESTED — PASSED |
| PC cards | ADMIN-LAPTOP, HEMALY - ENGINEER PC, PC-02, PC-06, PC-08, PC-09, PC-10, **PC-11**, PC-13, PC-14, PC-15; no TEST cards | FIXED AND VERIFIED |
| **25 simultaneous logins** | 25/25 OK, median 1.26 s, p95 1.88 s, max 2.03 s | TESTED — PASSED |
| **50 parallel dashboard loads** (4 API calls each) | 200/200 OK, median 4.18 s, max 4.30 s | TESTED — PASSED |
| Knowledge service `:5199/ask` | new question 5.3 s; repeat 0.0 s (cache); guarded questions 0.01–0.05 s | FIXED AND VERIFIED |

Both load tests ran **while the 1080p video render was using most of the CPU**, so they are pessimistic numbers.

## Not tested (and why)

| Item | Why | Label |
|---|---|---|
| ESP32 nodes (4) + ESP32-CAM on hardware | boards are at the owner's home, not connected | EXTERNAL BLOCKER |
| UR5e / FANUC live telemetry | controllers off; laptop not at the lab | OPERATOR ACTION REQUIRED |
| Cameras live + AI latency together | cameras are at GIU | NOT TESTED (next lab session) |
| n8n workflows | production workflows, deliberately not started | NOT REQUIRED for this closure |
| Door open/close | never triggered by software (rule) | NOT REQUIRED |
