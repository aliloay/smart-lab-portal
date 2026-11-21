---
name: "cli-anything-smartlab"
description: "Read-only inspection of the Smart Research Lab through the `smartlab` CLI: devices and ESP32 boards (online/offline/stale), security camera services, robots and lab PCs, local AI models and which model each assistant uses, the knowledge vault search, n8n workflow definitions, firmware versions, logs, reports and git state. Use it for any 'is X online / what model / which workflow / what version / where is it implemented / what is not pushed' question about the Smart Lab instead of opening dashboards or reading source. It cannot change anything."
---

# cli-anything-smartlab

`smartlab` is an agent-native, **read-only** CLI for the Smart Research Lab (BSc thesis, GIU). It follows the
CLI-Anything methodology (Click command groups, `--json` envelopes, REPL, installed-command tests), adapted to a
distributed web + hardware system: it reads the portal's real FastAPI endpoints and the local services, never a copy.

## Hard limits (by design)
- It **cannot**:
  - unlock or open the door, or drive the relay;
  - move or stop a robot, or write OPC UA;
  - run, activate or edit an n8n workflow;
  - flash firmware;
  - shut down or message PCs;
  - change users, the database, the router or the models.
- Those commands do not exist. The network layer refuses any request outside a read-only allow-list.
- **Never** try to get around this (curl, docker exec, SQL writes, n8n API). For any action, tell the owner what you would
  do and stop.

## Install / prerequisites
- **Installed on the lab laptop:** `smartlab` and `cli-anything-smartlab` are on PATH via `C:\Projects\external-tools\bin`.
- **To reinstall from the repo:**
  `C:\Projects\external-tools\venvs\clihub\Scripts\python -m pip install tools\smartlab_cli\agent-harness`.
- **Config (no secrets):** `~/.smartlab/config.json` has `{"repo": "...", "serial_log": "..."}`. The same values can come
  from the env vars `SMARTLAB_REPO`, `SMARTLAB_API` (default `http://localhost:8000/api`), `SMARTLAB_SERIAL_LOG`,
  `SMARTLAB_TIMEOUT` and `SMARTLAB_STALE_AFTER_S` (default 300).
- **Portal sign-in:** the device, ESP32, robot, PC and `system health` commands need staff/admin.
  - The owner runs `smartlab auth login` once; the token is kept for 8 h in `~/.smartlab/token.json`.
  - Without it those commands return `AUTH_REQUIRED` (exit 3). Ask the owner to sign in; never ask for the password in chat.

## Always use `--json`
Every command prints one envelope:
```json
{"success": true, "command": "devices list", "timestamp": "2026-11-21T15:38:00+00:00",
 "source": "smartlab-api /api/devices", "freshness": "live", "data": {...}, "warnings": [], "errors": []}
```
- **`source`:** where the data came from. Quote it when you answer.
- **`freshness`:** `live`, `file contents`, or `repo copy (may differ from the live n8n)`. Never present a repo copy or a
  file as live state.
- **Status labels:** `ONLINE`, `OFFLINE`, `STALE` (online flag but the last report is older than 300 s), `DEGRADED`
  (reporter runs, device missing), `UNKNOWN` (never reported), `NOT_ACCESSIBLE` (no permission or key), `NOT_CONFIGURED`.
  Treat UNKNOWN and STALE as **not online**.
- **Exit codes:**

  | Code | Meaning | What to do |
  |---|---|---|
  | 0 | ok | |
  | 1 | error / not found | |
  | 2 | bad usage | |
  | 3 | sign-in needed | ask the owner for `smartlab auth login` |
  | 4 | service unavailable | the service or the laptop is down; report it, do not retry in a loop |
  | 5 | refused by the read-only policy | |

## Commands
| Group | Commands | Source |
|---|---|---|
| (top) | `status`, `doctor`, `health` | portal + local probes |
| `auth` | `login`, `status`, `logout` | portal sign-in (local token only) |
| `system` | `services`, `containers`, `resources`, `health`, `version` | health URLs, `docker ps`, OS, `/api/system/health` |
| `devices` | `list [--type T] [--status S] [--include-retired]`, `inspect UID`, `offline`, `summary` | `/api/devices` |
| `esp32` | `list`, `inspect UID`, `firmware`, `ping` | `/api/devices` + repo `firmware/` + ICMP |
| `cameras` | `status` (picture arriving? fps, engine), `list` | camera services `/metrics`, `/api/devices` |
| `robots` | `list`, `status` | `/api/devices`, `/api/robots` (telemetry only) |
| `pcs` | `list [--status S]`, `inspect UID` | `/api/devices` |
| `ai` | `models`, `status`, `config` | Ollama tags/ps, knowledge service, `/api/ai/status`, GPU gate |
| `knowledge` | `status`, `search QUERY... [--limit N]` | knowledge service (search only, no AI generation) |
| `automation` | `list`, `inspect NAME_OR_ID` | repo copies `automation/n8n/json` (live n8n is never called) |
| `network` | `interfaces`, `ping HOST` | `ipconfig`, ICMP |
| `firmware` | `inventory` | version strings in `firmware/*` sources |
| `logs` | `list`, `recent LOG [-n N] [--errors]` | `logs/`, the master serial log (redacted) |
| `reports` | `list`, `latest`, `read PATH` | `docs/reports`, `reports/`, `docs/benchmarks` (.md only) |
| `github` | `status`, `branches`, `compare [--base REF]` | local git refs (no fetch, no push) |

Run `smartlab` with no arguments for the REPL. `smartlab <group> --help` shows every option.

## Recipes
| Question | Command(s) |
|---|---|
| "Is the lab OK?" | `smartlab --json doctor` (`overall` + one row per check) |
| "Is the consumables bin online?" | `smartlab --json devices inspect BIN_NODE_1`, then read `status` and `age` |
| "Which ESP32 handles the environment?" | `smartlab --json esp32 list`, then the `ENV_LAB01` row (type, ip, firmware) |
| "Are the cameras seeing anything?" | `smartlab --json cameras status` (`picture` ONLINE/OFFLINE, `capture_fps`) |
| "What model does the assistant use?" | `smartlab --json ai status` (knowledge assistant, portal assistant, GPU gate) |
| "Where is X implemented / documented?" | `smartlab --json knowledge search X`, then cite `rows[].source` |
| "Which workflow sends the daily report?" | `smartlab --json automation list`, then inspect it |
| "Are the boards on the repo's firmware?" | `smartlab --json esp32 firmware` (`matches_source`) |
| "What is not on GitHub yet?" | `smartlab --json github status` and `github compare` |
| "Why is the RFID offline?" | `smartlab --json logs recent master_serial_20261120.log -n 30 --errors` |

## Answering rules
- Say where each fact came from (`source`) and how fresh it is.
- If a command fails, report the error code and hint; do not guess the state.
- Do not print IPs, logs or reports outside the lab context unless asked. The output is already redacted for keys and tokens.
