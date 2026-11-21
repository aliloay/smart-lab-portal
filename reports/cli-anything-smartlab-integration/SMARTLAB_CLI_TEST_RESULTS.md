# smartlab CLI: test results

The full plan and the raw output are in `tools/smartlab_cli/agent-harness/cli_anything/smartlab/tests/TEST.md`.

## Final run (21 Nov 2026)
```text
CLI_ANYTHING_FORCE_INSTALLED=1 SMARTLAB_LIVE=1 python -m pytest -v cli_anything/smartlab/tests
107 passed in 23.2 s
```
- **Command tested:** the one `shutil.which` found on the **user PATH**:
  `C:\Projects\external-tools\bin\cli-anything-smartlab.cmd` → the venv exe. With `CLI_ANYTHING_FORCE_INSTALLED=1` there
  was no `python -m` fallback.
- **Working directory:** subprocess tests set no `cwd`. A manual check from `C:\` also worked (repo found through
  `~/.smartlab/config.json`).

| Suite | Tests | What it proves | Result |
|---|---|---|---|
| `test_core.py` | 49 | config/env/repo discovery; secret readers; redaction (7 leak patterns + look-alike keys kept); freshness labels incl. naive timestamps; portal state mapping (UNKNOWN never ONLINE); filters/summary; n8n trigger parsing; firmware regexes (build/ ignored, prefix-normalised compare); log tail + filter + redaction; report path traversal guard; git ref validation; token expiry and API binding; AUTH_REQUIRED without a token; UNAVAILABLE on a dead port; allow-list refusals; envelope schema | PASS |
| `test_safety.py` | 36 | no dangerous command words in the tree; only read verbs; 19 side-effect portal paths refused **before any socket**; only POSTs are login + knowledge lookup; Ollama pull/delete/generate/chat/create/copy refused; knowledge only status paths; cameras only /health and /metrics; no shell/eval/exec, `subprocess.run` with argument lists; unauthenticated device command sends nothing; fake secrets never in output | PASS |
| `test_full_e2e.py`, `TestCLISubprocess` | 14 | installed command vs a fake portal over real HTTP: help, version, health JSON, AUTH_REQUIRED (exit 3), labels ONLINE/OFFLINE/UNKNOWN, offline + esp32 filters, inspect known/unknown (NOT_FOUND), bad token (exit 3), slow API → timeout (exit 4), API down (exit 4), unknown/dangerous command (exit 2), token never printed, only GETs reached the portal, REPL driven through a pipe | PASS |
| `test_full_e2e.py`, `TestLiveReadOnly` | 8 | **real services**: portal/ollama/knowledge ONLINE; real Ollama model list; knowledge search finds the relock guard in the master firmware without running the model; real firmware versions; ≥ 20 real workflow definitions; real git status; doctor rows valid; camera rows valid | PASS |

## Live command checks (manual, real data, 21 Nov)
| Command | Real result |
|---|---|
| `smartlab system services` | 8/8 ONLINE (portal 243 ms first call, others 70–215 ms) |
| `smartlab doctor` | overall WARN: 13 PASS, 2 WARN (cameras have no picture because the IP cameras are at GIU; 1 commit not on origin/main), 2 SKIP (no sign-in), 0 FAIL |
| `smartlab cameras status` | both services ONLINE, picture OFFLINE, 174 open failures, DirectML detector 47 / 38 ms |
| `smartlab knowledge search relock guard PN532` | 3 cited sources in 60 ms; #1 `firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino` |
| `smartlab firmware inventory` | portal-1.2, bin-0.6, 0.1.1 (env), reuse-0.3, reuse-mod-0.5; no constant found for ESP32CAM_Vision_FAST, face_server, Robot_Stop |
| `smartlab github status` | fix/pre-lab-hardening, 1 ahead / 0 behind origin/main, which confirms the owner's push landed |
| `smartlab logs recent master_serial_20261120.log --errors` | the PN532 "frozen - only a power cycle clears it" lines (redacted) |

## Signed-in live check (21 Nov, 19:00, owner signed in as admin)
| Command | Real result |
|---|---|
| `smartlab esp32 list` | 5/5 ONLINE: BIN_NODE_1, MASTER_LAB01, CAM_LAB01, ENV_LAB01, REUSE_BIN_1 (ages 0–21 s) |
| `smartlab esp32 firmware` | all 4 reporting boards match their repo source (bin-0.6, portal-1.2, env-0.1.1, reuse-mod-0.5); the ESP32-CAM reports no version |
| `smartlab esp32 ping` | 5/5 reachable, 2–24 ms |
| `smartlab devices summary` | 23 devices, 7 online; offline = the robots and 10 PCs (at GIU); security cameras DEGRADED (service up, no picture) |
| `smartlab doctor` | **15 PASS, 2 WARN, 0 FAIL, 0 SKIP** (WARN = camera pictures away from the lab; 3 commits not on GitHub) |

## Not covered (honest gaps)
- **Official `/cli-anything:test`:** the plugin's commands load only after a Claude Code restart. Run it once then.
