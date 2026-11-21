# Terminal, process and resource inventory

- **Captured:** 19:06–19:15 local, read-only, with `Get-CimInstance Win32_Process`, `Get-NetTCPConnection`, `nvidia-smi`, `docker compose ps`/`stats`, `Get-Counter` and `powercfg`.
- Secrets in command lines are redacted; none appeared.

## Launcher tree

Started 15:50:10 by `launch.bat` (`cmd` pid 30508).

| Child window | Process | Port | Interpreter | Started | State |
|---|---|---|---|---|---|
| face server | `python.exe` 2892 | 0.0.0.0:5000 | Python 3.14 | 15:50:13 | `/health` ok, sface, threshold 0.363 |
| camera 1 | `python.exe` 30172 | 127.0.0.1:5100 | Python 3.14 | 15:50:25 | running; **stream OFFLINE** (317 fails) |
| camera 2 | `python.exe` 19844 | 127.0.0.1:5101 | Python 3.14 | 15:50:25 | running; **stream OFFLINE** (317 fails) |
| UR5e collector | `python.exe` 24256 | – | 3.12 | 15:50:11 | retrying 192.168.1.102 (unreachable at home) |
| FANUC collector | `python.exe` 30480 | – | 3.12 | 15:50:11 | retrying 192.168.1.100 (unreachable) |
| voice | `python.exe` 29816 | 127.0.0.1:5320 | 3.12 | 15:50:11 | `/health` ok (tiny.en STT, Piper TTS), 142 MB |
| OPC UA server | `python.exe` 13508 | (OPC UA port) | 3.12 | 15:50:12 | running |
| PC agent (admin laptop) | `python.exe` 27964 | – | 3.14 | 15:50:12 | heartbeating (`PC_ADMIN_LAPTOP` last seen 20 s) |
| LAN presence | `python.exe` 10356 | – | 3.12 | 15:50:12 | running |
| mDNS announce | `python.exe` 30556 | – | 3.14 | 15:50:11 | running |
| status watch | `powershell` 30380 | – | – | – | `scripts/status.ps1 -Watch` |
| **knowledge** | `cmd` 15916 | – | – | 15:50:10 | **no python child: exited; the window stays open (`/k`)** |

## Knowledge service: outside the launcher (finding F-12)

The listener on 127.0.0.1:5199 is `python.exe` 7516, started 17:23:54 through this chain:

`cmd /k py serve.py` (24904, parent 14952, gone) → `py` → `WindowsApps\python3.exe` → `backend\.venv\Scripts\python.exe` (shim) → `Python312\python.exe`

- This matches the checkpoint's warning that a launch from a VS Code terminal inherits `backend/.venv`.
- The service works (`/health` ok; `/status`: index built 18:01).
- However, it is not the launcher's instance, and the interpreter is chosen through the shim.
- There is exactly **one** listener, so no duplicate knowledge service is serving. The launcher's attempt died.

## Other processes

- **Ollama:** `ollama.exe serve` (25740, since 11:57), loopback only.
  - It receives `/api/tags` every ~10 s from a poller, probably the status watcher or the backend. This is cheap (30–60 ms).
- **Docker/WSL:** `vmmemWSL` working set 2.99 GB. The `.wslconfig` cap is 10 GB, 6 processors, 4 GB swap, `autoMemoryReclaim=dropcache`.
- **Serial logger:** `py -3.14 ...\scratchpad\master_monitor.py` (26768) holds **COM6** (master) open and logs to `D:\SmartLabData\firmware_backup\master_serial_20261120.log`.
  - It is an owner/agent tool, left untouched. COM6 therefore cannot be opened by anyone else.
- **MCP helpers:** chrome-devtools-mcp, context7-mcp and chroma-mcp (claude-mem), about 45–85 MB each.
- **VS Code:** Pylance 836 MB plus 2 tsservers. 3 VS Code PowerShell terminals are idle.
- **Docker containers:**

| Container | CPU | Memory | Up |
|---|---|---|---|
| backend | 12 % | 312 MB | 9 min (owner redeploy at ~18:58) |
| db | 10 % | 200 MB | – |
| n8n | 0.06 % | 574 MB | – |
| frontend | 0 % | 10 MB | – |
| backup | 0 % | 36 MB | – |

- During my backend test run, two temporary containers (test backend and test DB) used about 71 % CPU each. They were removed by the script.

## Resources

| Metric | Value | Conditions |
|---|---|---|
| RAM | 31.8 GB total, **6.1 GB free** | during the backend test run |
| Page file | 104 MB used (peak 117 MB) of 25 GB | no paging pressure |
| CPU | 42–46 % | during the backend test run |
| GPU | GTX 1650, **0 % util, 918 MiB / 4096 MiB** | cameras have no stream; 2 camera services and the face server hold the context |
| Ollama VRAM | 0 (all 3 models on the CPU) | see F-05 |
| Disk C: | 89 GB free of 370 | `./backups` = 6.2 GB |
| Disk D: | 791 GB free of 932 | Docker data and SmartLabData |
| Power scheme | **Balanced** (`381b4222…`) | the brief says "Best Performance"; the power-mode slider may differ (UNVERIFIED) |

## Issues found

1. **Knowledge service:** wrong-chain instance plus a dead launcher window (F-12).
2. **COM6 occupied** by a long-running logger. That is fine, but document it before any flashing session.
3. **Robot collectors poll unreachable controllers all day at home.** This is harmless: there is a 2–3 s backoff and no false online state.
4. **No duplicate camera services and no port conflicts** (each port has exactly one owner).
5. **About 60 docker rollback image tags.** Layers are shared, so disk use is lower than the 1.4 GB nominal each; prune after the defense.
6. **The biggest real CPU consumer is LLM inference on the CPU** (F-05). The biggest GPU consumer would be the cameras, which are idle today.

I did not stop, restart or kill anything.
