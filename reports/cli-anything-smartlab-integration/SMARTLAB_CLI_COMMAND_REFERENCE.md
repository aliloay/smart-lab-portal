# smartlab command reference (generated from the installed CLI, v0.1.0)

Every command accepts the global `--json` flag: `smartlab --json <group> <command>`.

**Exit codes:** 0 ok · 1 error / not found · 2 usage · 3 sign-in needed · 4 service unavailable · 5 refused by the read-only policy.

## Top-level commands
- **`smartlab doctor`**: Run every health check (PASS / WARN / FAIL / SKIP with evidence).
- **`smartlab health`**: Portal health and build stamp (no sign-in needed).
- **`smartlab status`**: One-screen overview: portal, services, ESP32 boards, AI.

## `smartlab ai`
Local AI: Ollama models, which model each assistant uses, the camera-first GPU gate.

- **`smartlab ai config`**: Knowledge assistant settings (keys and passwords removed).
- **`smartlab ai models`**: Installed Ollama models, size, which are loaded and on CPU or GPU.
- **`smartlab ai status`**: Knowledge assistant model, portal assistant model/health, GPU gate decision.

## `smartlab auth`
Portal sign-in for the commands that need staff/admin (token kept locally, 8 h).

- **`smartlab auth login`**: Sign in (password is asked for, or read from SMARTLAB_PASSWORD). Writes a LOGIN audit entry in the portal.  
  options: `--username/-u`: Username or email.
- **`smartlab auth logout`**: Forget the local token (nothing is changed in the portal).
- **`smartlab auth status`**: Who the CLI is signed in as.

## `smartlab automation`
n8n workflow DEFINITIONS from the repo copies. Nothing is run, activated or edited.

- **`smartlab automation inspect`**: One workflow definition: node list and portal endpoints it calls (redacted).  
  options: `NAME_OR_ID`
- **`smartlab automation list`**: Every n8n workflow definition: triggers (webhook / schedule), nodes, HTTP calls.

## `smartlab cameras`
Security camera services: is a picture arriving, analysis speed, engines.

- **`smartlab cameras list`**: Camera devices as the portal sees them.
- **`smartlab cameras status`**: Per camera: service up? picture arriving? capture/analysis fps, detector engine.

## `smartlab devices`
Every registered device (portal API, staff sign-in).

- **`smartlab devices inspect`**: One device in detail (components, note, freshness).  
  options: `UID`
- **`smartlab devices list`**: All devices with a status label (ONLINE/OFFLINE/STALE/DEGRADED/UNKNOWN), age, IP, firmware.  
  options: `--type`: Filter by device type, e.g. SENSOR_NODE, PC, ROBOT.; `--status`; `--include-retired`
- **`smartlab devices offline`**: Everything that is not ONLINE right now.
- **`smartlab devices summary`**: Counts per device type and status.

## `smartlab esp32`
The ESP32 boards: master door, environment, bins, ESP32-CAM.

- **`smartlab esp32 firmware`**: Reported firmware vs the version declared in the repo's firmware sources.
- **`smartlab esp32 inspect`**: One ESP32 board in detail (components, note, freshness).  
  options: `UID`
- **`smartlab esp32 list`**: The ESP32 boards with status, age, IP and reported firmware.
- **`smartlab esp32 ping`**: One ping to each ESP32 address the portal knows (Wi-Fi reachability from this laptop).

## `smartlab firmware`
Firmware versions declared in the repo sources (read-only; nothing is flashed).

- **`smartlab firmware inventory`**: Firmware version declared in each firmware/ folder.

## `smartlab github`
Local git state vs GitHub (no fetch, no push).

- **`smartlab github branches`**: Local branches by last commit, and the git worktrees.
- **`smartlab github compare`**: Commits and files on HEAD that are not on BASE (default origin/main).  
  options: `--base`
- **`smartlab github status`**: Branch, HEAD, modified/untracked files, commits ahead/behind origin/main (last fetch).

## `smartlab knowledge`
The project knowledge vault and search (no AI generation).

- **`smartlab knowledge search`**: Find the documents/code that answer QUERY (cited sources, no model run).  
  options: `QUERY` (one or more words); `--limit`
- **`smartlab knowledge status`**: Knowledge service: index build time, embeddings, assistant model.

## `smartlab logs`
Service logs (redacted).

- **`smartlab logs list`**: Known log files (logs/, master serial log) with size and modified time.
- **`smartlab logs recent`**: Last lines of LOG_NAME (a name from `smartlab logs list`).  
  options: `LOG_NAME`; `--lines/-n`; `--errors`: Only error/warning/offline lines.

## `smartlab network`
Laptop network adapters and reachability.

- **`smartlab network interfaces`**: IPv4 address and gateway per network adapter.
- **`smartlab network ping`**: One ping to HOST (IP or hostname).  
  options: `HOST`

## `smartlab pcs`
Lab PCs (agents report to the portal).

- **`smartlab pcs inspect`**: One lab PC in detail.  
  options: `UID`
- **`smartlab pcs list`**: Lab PCs with status label and last report.  
  options: `--status`

## `smartlab reports`
Project reports and benchmarks in the repo.

- **`smartlab reports latest`**: Read the most recently changed report (redacted, first 6000 characters).
- **`smartlab reports list`**: Most recent reports and benchmarks (.md) in the repo.  
  options: `--limit`
- **`smartlab reports read`**: Read a .md report inside the repo (first 6000 characters, redacted).  
  options: `PATH`

## `smartlab robots`
UR5e / FANUC digital twins - read-only telemetry. No motion command exists here.

- **`smartlab robots list`**: Robot devices as the portal sees them (status, age, note).
- **`smartlab robots status`**: Twin state from the portal (mode, connection, simulated or real).

## `smartlab system`
Laptop, services, containers and versions.

- **`smartlab system containers`**: Docker containers and their health (docker ps, read-only).
- **`smartlab system health`**: The portal's own aggregate health view (staff).
- **`smartlab system resources`**: RAM, disks and GPU memory.
- **`smartlab system services`**: Probe every local service (portal, n8n, face, cameras, knowledge, voice, Ollama).
- **`smartlab system version`**: CLI version, portal build stamp and repo HEAD.

`smartlab` with no command starts the REPL; it also works with piped input.
