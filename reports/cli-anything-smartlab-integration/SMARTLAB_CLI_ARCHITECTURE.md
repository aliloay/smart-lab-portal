# smartlab CLI: architecture

The full SOP is in `tools/smartlab_cli/agent-harness/SMARTLAB.md`. This report summarises it.

## Layout
```text
tools/smartlab_cli/
├── skills/cli-anything-smartlab/SKILL.md      canonical agent skill
└── agent-harness/
    ├── SMARTLAB.md                            software-specific SOP (architecture, command map, deviations)
    ├── setup.py                               cli-anything-smartlab 0.1.0, PEP 420, entry points smartlab + cli-anything-smartlab
    └── cli_anything/                          namespace package (no __init__.py)
        └── smartlab/
            ├── __init__.py, __main__.py, README.md, smartlab_cli.py   Click groups, handle_error, REPL
            ├── core/   devices.py  services.py  ai.py  repo.py  doctor.py
            ├── utils/  api_client.py (allow-list)  config.py  output.py  redaction.py  freshness.py  errors.py  repl_skin.py (upstream copy)
            ├── skills/SKILL.md                packaged copy
            └── tests/  TEST.md  test_core.py  test_safety.py  test_full_e2e.py
```

## Data flow
```text
smartlab <group> <command> [--json]
   │
   ├─ core/devices.py ──► api_client.portal(GET allow-listed) ──► FastAPI /api/devices, /robots, /system/health, ...
   │                         (Bearer token from `smartlab auth login`, 8 h, ~/.smartlab/token.json)
   ├─ core/ai.py ───────► api_client.ollama(GET /api/tags|ps|version)
   │                    ► api_client.kb(GET /status|/gpu-gate) and kb_search(POST /ask route=lookup)
   ├─ core/services.py ─► api_client.probe(configured /health URLs), camera(/health|/metrics)
   │                    ► subprocess [docker ps] [ipconfig] [ping -n 1 HOST] [nvidia-smi]   (argument lists, no shell)
   ├─ core/repo.py ─────► repo files: firmware/*, automation/n8n/json/*, docs/reports, logs/ (+ serial log)
   │                    ► subprocess [git -C repo ...] (status, log, for-each-ref, worktree list, diff --name-only)
   └─ utils/output.py ──► one envelope {success, command, timestamp, source, freshness, data, warnings, errors}
                          → redact() → JSON or human table
```

## Design decisions
| Decision | Why |
|---|---|
| **Read the portal API, not the database** | Same rules and liveness the portal shows. It needs a sign-in, so the CLI has no more rights than the account used |
| **Use the portal's own `state` and `seconds_since_seen`** | No second liveness algorithm that could disagree. The CLI only adds STALE (> 300 s) and maps NO_DATA → UNKNOWN |
| **Allow-list in one module** | One place to review. The tests parametrise known side-effect GETs (command polls, nonce/token minting, AI generation, exports, photos, door QR) and assert they are refused before any socket opens |
| **n8n from the repo copies** | The live n8n is never called; the output is labelled `freshness: repo copy` |
| **Knowledge search = `route=lookup`** | Instant, cited sources; no GPU or CPU load from the model |
| **No `project` / `session` / `export`** | Nothing is edited or rendered (see the deviations in SMARTLAB.md) |
| **Token file only** | The only persistent state; written with `O_CREAT\|O_TRUNC`, mode 0600 (best effort on Windows); bound to the API base and expiry |
| **No new dependencies** | stdlib `urllib`, `subprocess`, `ctypes`; Click; prompt-toolkit for the REPL only |
| **REPL falls back to `input()` without a console** | Agents and scripts can pipe commands (tested) |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | error / not found |
| 2 | usage / invalid input |
| 3 | AUTH_REQUIRED |
| 4 | UNAVAILABLE (service down, timeout) |
| 5 | FORBIDDEN_BY_CLI_POLICY |
