# smartlab CLI: safety validation

## Layer 1: no dangerous commands exist
- The command tree has these groups: `status doctor health auth system devices esp32 cameras robots pcs ai knowledge
  automation network firmware logs reports github repl`.
- Their sub-commands are only read verbs: list, inspect, status, summary, offline, firmware, ping, models, config, search,
  interfaces, inventory, recent, latest, read, branches, compare, services, containers, resources, health, version, plus
  login/logout for the local token.
- `test_safety.py::test_no_dangerous_command_exists` fails if any of 38 action words appears, for example unlock, lock,
  open, relay, door, move, jog, home, stop, write, run, execute, activate, flash, shutdown, restart, delete, create,
  update, set, grant, approve, pull, rm, alarm, emergency, message, maintenance, exam, share.
- `smartlab unlock door` exits 2 ("No such command"); this is tested on the installed command and in the REPL.

## Layer 2: the network allow-list (`utils/api_client.py`)
| Target | Allowed | Everything else |
|---|---|---|
| Portal API | GET on 20 read paths (health, auth/me, system status/services/health, devices, labs, alerts, summary, robots, equipment, security/cameras, ai/status, knowledge/status, voice/status, inventory bins/items); POST `/auth/login` | `Forbidden` raised **before** a socket is opened |
| Knowledge service | GET `/health`, `/status`, `/gpu-gate`; POST `/ask` with `route=lookup` hard-coded (no generation) | `Forbidden` |
| Ollama | GET `/api/version`, `/api/tags`, `/api/ps` | `Forbidden` (pull, delete, generate, chat, create, copy tested) |
| Camera services | GET `/health`, `/metrics` on 5100/5101 | `Forbidden` (`/record/start` and `/known`, which holds names, tested) |
| Local health probes | only the configured `/health` URLs | `Forbidden` (an n8n run URL tested) |

**Known side-effect GET endpoints are excluded and tested as refused:**
- command polls (`/access/commands/next`, `/equipment/pc/poll|wait`, `/robots/stop-relay/poll`);
- nonce/token minting (`/equipment/master/nonce`, `/equipment/share-requests/nonce`, `/equipment/pc/watch-token`);
- AI generation (`/ai/insights`, `/ai/report`);
- data export (`/access-events/export`);
- photos (`/security/cameras/{id}/frame.jpg`, `/users/{id}/door-photo`);
- door credential material (`/bookings/{id}/qr`, `/auth/me/door-qr`);
- robot control (`/robots/{id}/control`);
- config dump (`/system/config`);
- OPC UA (`/opcua/snapshot`).

## Layer 3: no shell, validated inputs
- No `shell=True`, `os.system`, `os.popen`, `eval` or `exec` (source scan in the tests).
- `subprocess.run` gets only argument lists: `git -C <repo> …`, `docker ps --format …`, `ipconfig`, `ping -n 1 -w 800 HOST`
  (HOST must match `[A-Za-z0-9.-]{1,253}`), `nvidia-smi --query-gpu=…`.
- `github compare --base` must match `[A-Za-z0-9._/-]{1,100}`.
- `reports read` only reads `.md` files inside the repo (a resolved path inside the repo root; `../` refused).
- `logs recent` only reads files listed by `logs list`; at most 2000 lines.

## Layer 4: secrets
- **The KB service key and the device key** are read from `tools/knowledge/config.json` and `.env` (or env vars) only to
  authenticate local calls. They are never placed in output.
- **The portal token** is stored in `~/.smartlab/token.json` (0600 best effort). It is bound to the API base URL and
  treated as expired 30 s early.
- **Redaction:**
  - Every envelope passes through `redact()`.
  - Keys named password, token, secret, api/service/device/kb/automation key, authorization, cookie, credentials or jwt
    are blanked.
  - Text patterns are masked: bearer tokens, JWTs, `key=value` secrets, `rtsp://` and `user:pass@` URLs, door QR tokens
    (`SLB:…`).
  - Look-alike keys (`PASS` counts, `prompt_tokens`, `has_own_key`) are kept. That is a regression test for a bug found
    while building.
- `test_secrets_never_in_output` and `test_token_never_printed` place fake secrets and check every byte of output.

## Layer 5: privileges
- The CLI never has more rights than the portal account used to sign in.
- It does not read the database directly, does not use `docker exec`, and does not call n8n.
- `devices list` uses `GET /api/devices`, which (like the portal's own page) recomputes liveness on read. That is the
  portal's normal read behaviour, not a CLI write.

## What was not done during this work (verified)
- No door, relay, robot, OPC UA, n8n, firmware or PC action.
- No production service restart **for the CLI work**. The backend container and the knowledge service were restarted
  earlier the same day, for the separately requested AI-model deployment.
- No database write. No GitHub push. No commit on `feat/smartlab-cli` (owner authorisation required).
