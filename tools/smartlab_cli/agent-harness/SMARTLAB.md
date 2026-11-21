# SMARTLAB.md: architecture analysis and SOP for cli-anything-smartlab

This file is the CLI-Anything per-software SOP (`<SOFTWARE>.md`). The method is the plugin's `HARNESS.md`, which is not
duplicated here.

## 1. What the "software" is
The Smart Research Lab is not a desktop GUI application. It is a distributed system:
- **Portal:**
  - FastAPI backend, 52 route modules under `backend/app/api/routes`, mounted at `/api`;
  - React frontend;
  - Postgres;
  - n8n;
  - backups (Docker Compose).
- **Local services started by `launch.bat`:**
  - face server (:5000);
  - security cameras 1 and 2 (:5100 / :5101, DirectML YOLO + re-ID);
  - knowledge service (:5199; vault search, assistant, GPU gate);
  - voice (:5320);
  - Ollama (:11434);
  - robot collectors / OPC UA.
- **Five ESP32 boards:**
  - master door (RFID, QR, fingerprint, face, relay);
  - environment;
  - consumables bin;
  - reusable bin;
  - ESP32-CAM.
  - They report to the portal over Wi-Fi.
- **UR5e / FANUC digital twins:** read-only telemetry; every control adapter stays UNAVAILABLE until commissioning.

## 2. Backend engine mapping ("GUI action → API")
| What a person does in the portal | Real backend used by the CLI |
|---|---|
| IoT / Devices page: online, offline, last seen | `GET /api/devices` (staff). The portal recomputes liveness on read: `state`, `seconds_since_seen`, `state_note` |
| System Health page | `GET /api/system/health` (staff); `GET /api/health` (public, build stamp) |
| Robots page | `GET /api/robots` (user): twin state, telemetry only |
| AI Assistant status | `GET /api/ai/status` (staff) + knowledge service `/status` + `/gpu-gate` (X-KB-Key) |
| Knowledge search panel | knowledge service `POST /ask` with `route=lookup`: retrieval and citations, **no generation** |
| Security cameras page | camera services `/health` and `/metrics` (X-Device-Key): capture fps, analysis fps, engine |
| n8n editor | the repo copies `automation/n8n/json/*.json`, read as definitions. The live n8n API is **not** used, because its harness can run, activate and edit workflows, and the project forbids that |
| Firmware / Arduino IDE | the version constants in the `firmware/*` sources |
| Watching the laptop | health URLs (same list as `tools/ops/watchdog.py` + face + Ollama), `docker ps`, `ipconfig`, `nvidia-smi`, OS memory |

## 3. Why the template is adapted (deviations from the generic GUI harness)
| HARNESS.md expectation | Smart Lab decision | Reason |
|---|---|---|
| `core/project.py` (create/open/save project files) | Not present | There is no document or project file. The "project" is the running lab, read through its API |
| `core/session.py` with undo/redo | Not present | The CLI is read-only by owner requirement; undo/redo of reads is meaningless. Persistent state is only the sign-in token (`~/.smartlab/token.json`), written atomically |
| `core/export.py` render pipeline + `EXPORT_PRESETS` | Not present | Nothing is rendered. The "real software" invoked is the portal API, the local services, Ollama, git, docker and the OS |
| `--project` flag | Replaced by `SMARTLAB_REPO` / `~/.smartlab/config.json` | The repo path locates the definitions (firmware, n8n copies, reports, git) |
| E2E tests produce real output files | E2E tests verify real API / service responses | The installed command is run as a subprocess against a fake portal (real HTTP) and against the live laptop services (real backends); a down service fails the test |
| Mutation commands | None, by design | Physical safety: door, relay, robots, OPC UA, n8n, firmware, PCs, the database |

**Kept from the method:**
- Click command groups;
- `--json` on every command, with one envelope;
- the `handle_error` decorator with stable exit codes;
- a REPL as the default, using the upstream `repl_skin.py`;
- PEP 420 `cli_anything.smartlab` packaging;
- TEST.md plan → tests → results;
- the `_resolve_cli` subprocess pattern with `CLI_ANYTHING_FORCE_INSTALLED`;
- SKILL.md in its canonical place plus a packaged copy.

## 4. Command map
See `cli_anything/smartlab/skills/SKILL.md`. The groups are:
- `status`, `doctor`, `health`
- `auth`, `system`
- `devices`, `esp32`, `cameras`, `robots`, `pcs`
- `ai`, `knowledge`, `automation`
- `network`, `firmware`, `logs`, `reports`, `github`

**Groups from the owner's proposal that were omitted, and why:**
- **`vision pipeline/benchmark/pose`:** no read-only API exposes them; a benchmark would load the GPU the cameras own.
- **`portal routes`:** OpenAPI is disabled in production (`EXPOSE_API_DOCS=False`).
- **`esp32 serial/heartbeat`:** the serial port is held by the session logger, and opening it can reset a board.
- **Robot `telemetry/history`:** covered by `robots status`; history endpoints rebuild data and were not verified as
  side-effect free.

## 5. Rendering-gap assessment
There is no rendering. The equivalent risk is **reporting stale data as live**. Three mitigations:
- the portal's own liveness computation is used;
- a STALE label is added after 300 s;
- every envelope carries `source` and `freshness`; repo copies and files are labelled as such.

## 6. Security model
- **Allow-list in `utils/api_client.py`:**
  - portal: GET on 20 path patterns, plus the sign-in POST;
  - knowledge: 3 GET paths, plus a search POST forced to `route=lookup`;
  - Ollama: 3 GET paths;
  - cameras: `/health` and `/metrics` only;
  - local health URLs: only the configured ones.
- **Side-effect GET endpoints are excluded:** command polls, nonce/token minting, AI generation, exports, photos, door QR.
  `tests/test_safety.py` parametrises them.
- **Secrets** are read from where the system keeps them, never logged; output is redacted by key name and by pattern.
- **Shell:** none. `subprocess.run` gets argument lists only (git, docker ps, ipconfig, ping, nvidia-smi), with
  validated inputs.
- **Portal sign-in:** a normal user sign-in, recorded in the audit log. The CLI never has more rights than the account
  used. There is no service token and no read-only role yet; creating one is an owner decision.
