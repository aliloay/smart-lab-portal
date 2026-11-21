# Test results and evidence index

All runs were made by this audit on 2026-11-21, serially, while the owner's services kept running. Logs are in `evidence/`.

## Test suites

| Suite | Command | Result | Duration | Log |
|---|---|---|---|---|
| Backend (throwaway test DB) | `powershell -ExecutionPolicy Bypass -File tools\ops\test_backend_fast.ps1` | **887 passed, 3 skipped**, 26 warnings, exit 0 | 601 s | `evidence/backend_tests.log` (UTF-16) |
| Security vision | `py -3.14 -m pytest -q -p no:cacheprovider tools/security_vision` | **396 passed** | 91 s | `evidence/security_vision_tests.log` |
| Robot monitor | `py -3.12 -m pytest -q -p no:cacheprovider tools/robot_monitor` | **44 passed** | 1.1 s | `evidence/robot_monitor_tests.log` |
| Knowledge | `py -3.12 -m pytest -q -p no:cacheprovider tools/knowledge` | **64 passed** | 15.6 s | `evidence/knowledge_tests.log` |
| Face server | `cd firmware/face_server; py -3.14 -m pytest -q -p no:cacheprovider .` | **22 passed** | 1.9 s | `evidence/face_server_tests.log` |
| PC agent | `cd tools/pc_agent; py -3.14 -m pytest -q -p no:cacheprovider .` | **40 passed** | 5.9 s | `evidence/pc_agent_tests.log` |
| Relay | `cd tools/relay; py -3.14 -m pytest -q -p no:cacheprovider .` | **6 passed** | 1.1 s | `evidence/relay_tests.log` |
| Frontend types | `npx tsc --noEmit -p .` (in `frontend/`) | **exit 0** | – | `evidence/tsc.log` |

### Compared with the historical table in the brief

- Backend: 875 → **887**. Face 22, cameras 396, robots 44, knowledge 64 and PC agent 40 are unchanged.

### Skipped or not run

- **3 backend skips:** `test_ai_router.py:14` (eval set not mounted), `test_automation_kinds.py:17` (workflow copies not mounted), plus one other conditional skip.
- **`vite build`:** not run. The live image is already a production build (measured), and a build writes `frontend/dist`.
- **Frontend unit test (`npm run test:unit`):** not run.
- **Playwright e2e** (`navigation.mjs`, `workflows.mjs`, `click_everything.mjs`, `responsive_audit.mjs`): not run, because the isolated test copy (:5176/:8100) was down and the brief forbids interacting with live controls.
- **`tools/smartlab_cli` tests** (107 per the checkpoint): not run.
- **Hardware, live-camera and robot tests:** impossible (equipment at GIU) or forbidden (door, flashing).

## Live evidence gathered (read-only)

| Evidence | How | Label |
|---|---|---|
| Git local/remote SHAs at 19:06 and 19:24 | `git rev-parse`, `git ls-remote`, `gh repo view` | LIVE-VERIFIED |
| Process tree, ports, start times | `Win32_Process`, `Get-NetTCPConnection` | LIVE-VERIFIED |
| Service health (8000, 5000, 5100, 5101, 5199, 5320, 5678, 11434) | `curl` GET | LIVE-VERIFIED |
| GPU, RAM, CPU, disk, page file, power scheme, `.wslconfig` | `nvidia-smi`, CIM, `Get-Counter`, `powercfg` | LIVE-VERIFIED |
| Network interfaces, routes, ARP (two MACs at .1) | `Get-NetIPConfiguration`, `route print`, `arp -a` | LIVE-VERIFIED |
| ESP32 ping, 5 × 20 packets, 0 % loss | `ping -n 20` | LIVE-VERIFIED |
| COM ports COM6/7/8 | `Get-PnpDevice` (ports not opened) | LIVE-VERIFIED (identity unverified) |
| ESP32-CAM `/status` fields | one GET (token value redacted) | LIVE-VERIFIED |
| DB counts, devices, alerts, users, bookings, bins, indexes, sizes | SELECT only | LIVE-VERIFIED |
| Backup status, dump header, TOC, uploads tar listing | read files; `pg_restore --list` in the backup container | LIVE-VERIFIED |
| n8n health, run history (`audit_logs`), backup parse (52/52) | GET `/healthz`; SELECT; Python json | LIVE-VERIFIED (live workflow states: UNVERIFIED) |
| Knowledge latency, 7 questions | `scratchpad/audit_aibench.py` + `curl` → `evidence/knowledge_latency.json` | TESTED – measured |
| Ollama models and residency, server log | `/api/tags`, `/api/ps`, `server.log` | LIVE-VERIFIED |
| Frontend asset sizes and gzip transfer, headers | `docker compose exec frontend ls`; `curl` | LIVE-VERIFIED |
| Route authorization sweep | `scratchpad/audit_routes.py` (AST) | VERIFIED FROM CODE |
| Vault links, frontmatter, orphans, mirrors | `scratchpad/vault_audit.py` | VERIFIED (read-only scan) |
| n8n JSON structure | `scratchpad/n8n_audit.py` | VERIFIED FROM CODE |

The scratchpad scripts are at `C:\Users\dell\AppData\Local\Temp\claude\718303409c203bf0\f3a7f05b-5e4a-46c1-a4ed-e8af73cd7e29\scratchpad\` (`audit_routes.py`, `vault_audit.py`, `n8n_audit.py`, `audit_aibench.py`).

## Historical (not re-verified; cited only as history)

- UR5e RTDE 48 Hz, FANUC read-only twin, 19 Oct camera GPU contention test.
- 21 Nov door measurements (relock 7/8, QR 161 ms).
- AR detector v8 evaluation numbers.
- 21 Nov model benchmark.
- 25-concurrent-login test.
- e2e 98/30.
