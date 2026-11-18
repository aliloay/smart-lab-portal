# SYSTEM_INVENTORY_LIVE.md

- **Audit Timestamp**: `2026-11-18 16:41–17:16 +02:00` (On-site at German International University — GIU Robotics Lab `LAB_01`)
- **Main Checkout**: `C:\Projects\smart-lab-portal` (branch `fix/pre-lab-hardening`, `HEAD = 610279e`)
- **Gemini/Argon Isolated Worktree**: `C:\Projects\smart-lab-argon` (branch `opt/gemini-live-lab-finalization-2026-11-18`, branched from `610279e`)
- **Claude App Worktree**: `C:\Projects\smart-lab-portal-opt` (branch `opt/claude-app-performance-2026-11-17`, `HEAD = 3937ed1`)
- **Release Worktree**: `C:\Projects\smart-lab-release` (branch `release/smart-lab-final-optimization-2026-11-17`, `HEAD = 86375b9`)

---

## 1. Host & Network Topology at GIU (`LIVE_PHYSICAL` + `LIVE_SERVICE`)

| Parameter | Measured On-Site Value | Evidence Class |
|---|---|---|
| Host Laptop | `DESKTOP-61G2S1I` (`ali`), Intel Core i7-9750H (6C/12T), `16,213 MB` RAM, NVIDIA GTX 1650 (`4,096 MiB` VRAM) | `LIVE_PHYSICAL` |
| Lab Ethernet Interface | `Ethernet` = `192.168.1.200/24` (connected to Smart Lab Router `192.168.1.1`, `1–2 ms` RTT) | `LIVE_PHYSICAL` |
| Upstream Wi-Fi Interface | `Wi-Fi` = `172.20.10.2/28` (phone hotspot internet) | `LIVE_PHYSICAL` |
| Host Load During Full Live Stack | CPU `35–88%`, Free RAM `1,404 MB / 16,213 MB`, Paging `317–811 pages/s`, Disk `C:`/`D:` `0 ms`, GPU `868 / 4,096 MiB` (`30–36%` util, `70 °C`) | `LIVE_SERVICE` |
| Attached USB/Serial COM Ports | `0` (`Win32_SerialPort` empty — ESP32 nodes left at home per 18 Nov uni checklist) | `LIVE_PHYSICAL` |

---

## 2. Live Physical Devices & Workstations Inventory (`LIVE_PHYSICAL` / `LIVE_SERVICE` / `NOT_PRESENT`)

| `device_uid` | Type | Actual IP / Subnet | Firmware / Agent Version | Verified State | Last Seen Age | Evidence Class & Verification Notes |
|---|---|---|---|---|---|---|
| `SECCAM_LAB01` | `SECURITY_CAMERA` | `192.168.1.155` (`:554` RTSP -> `:5100`) | Tapo C200 / `security_vision` | **`LIVE`** | `0.2 s` | `LIVE_PHYSICAL` — `8 ms` ICMP ping; `13.85 fps` capture, `5.4–6.0 fps` analysis on DirectML GPU1 |
| `SECCAM_LAB02` | `SECURITY_CAMERA` | `192.168.1.156` (`:554` RTSP -> `:5101`) | Tapo C200 / `security_vision` | **`LIVE`** | `0.2 s` | `LIVE_PHYSICAL` — `5–22 ms` ICMP ping; `14.85 fps` capture, `5.3–6.0 fps` analysis on DirectML GPU1 |
| `PC_ADMIN_LAPTOP` | `PC` | `192.168.1.200` / `172.20.10.2` | `pc-agent-1.0` | **`LIVE`** | `4.2 s` | `LIVE_PHYSICAL` — Host laptop (`dell`), PID `38448` (`24.2 MB` WS), `clock_offset_s: 0.05` |
| `PC_ENG` | `PC` | `192.168.1.100` (Lab NIC) + `10.30.11.136` (GIU NIC) | `pc-agent-1.0` + `relay.py` | **`LIVE`** | `1.5 s` | `LIVE_PHYSICAL` — Engineer PC `S2PC136` (`ahmed.el-hemaly`), `2–3 ms` ping on `.100`, dual-monitor (`1920x1080` + `1920x1200`), actively relaying 6 student PCs |
| `PC_GIULAB20-PC4` | `PC` (`PC-02`) | `10.40.20.4` (via `S2PC136` relay) | `pc-agent-1.0` | **`LIVE`** | `8.0 s` | `LIVE_PHYSICAL` — Student Lab PC (`ali.abozeid`, `msedge.exe`), reporting through `10.30.11.136:8000` relay |
| `PC_GIULAB20-PC13` | `PC` (`PC-13`) | `10.40.20.13` (via `S2PC136` relay) | `pc-agent-0.9` | **`LIVE`** | `4.0 s` | `LIVE_PHYSICAL` — Student Lab PC (`ali.abozeid`, `powershell.exe`), reporting through relay (needs upgrade to `1.0`) |
| `PC_GIULAB20-PC14` | `PC` (`PC-14`) | `10.40.20.14` (via `S2PC136` relay) | `pc-agent-1.0` | **`LIVE`** | `13.0 s` | `LIVE_PHYSICAL` — Student Lab PC (`pansih.abudif`, `explorer.exe`), reporting through relay |
| `PC_GIULAB20-PC17` | `PC` (`PC-17`) | `10.40.20.17` (via `S2PC136` relay) | `pc-agent-1.0` | **`LIVE`** | `12.2 s` | `LIVE_PHYSICAL` — Student Lab PC (`ali.elalawi`, `msedge.exe`), reporting through relay |
| `PC_GIULAB20-PC18` | `PC` (`PC-18`) | `10.40.20.18` (via `S2PC136` relay) | `pc-agent-1.0` | **`LIVE`** | `11.8 s` | `LIVE_PHYSICAL` — Student Lab PC (`ali.abozeid`, `AtmelStudio.exe`), reporting through relay |
| `PC_GIULAB20-PC19` | `PC` (`PC-19`) | `10.40.20.19` (via `S2PC136` relay) | `pc-agent-1.0` | **`LIVE`** | `11.9 s` | `LIVE_PHYSICAL` — Student Lab PC (`ali.abozeid`, `vlc.exe`), reporting through relay |
| `PC_GIULAB20-PC8/11/12` | `PC` | `10.40.20.8 / .11 / .12` | `pc-agent-0.9` | **`DOWN`** | `13 d` | `LIVE_SERVICE` — Powered off or no logged-in user session during audit window |
| `UR5E_01` | `ROBOT` | `192.168.1.102:30003` | `robot-collector-0.2 (ur)` | **`STALE / OFF`** | `1.1 s` (collector) | `LIVE_SERVICE` — Controller powered off (`WinError 10060` timeout in `ur5e_monitor.log`); collector falsely kept DB `is_online=t` (fixed by Gemini in `robot_collector.py`) |
| `FANUC_01` | `ROBOT` | `192.168.1.100:80` (conflict w/ `PC_ENG`) | `robot-collector-0.2 (fanuc)` | **`STALE / OFF`** | `2.5 s` (collector) | `LIVE_SERVICE` — `.100` is currently `PC_ENG` USB-Ethernet NIC (`00-e0-4c-18-65-60`); `/MD/CURPOS.DG` times out; collector false-online fixed |
| `MASTER_LAB01` | `MASTER_CONTROLLER` | `192.168.1.151` | `portal-1.0` (`portal-1.1` compiled) | **`NOT_PRESENT`** | `21.5 h` | `STATIC_INSPECTION` — Left at home per `LAB_DAY_UNI_CHECKLIST_2026-11-18.md` |
| `ENV_LAB01` | `SENSOR_NODE` | `192.168.1.152` | `env-0.1.1` | **`NOT_PRESENT`** | `21.6 h` | `STATIC_INSPECTION` — Left at home per 18 Nov checklist |
| `BIN_NODE_1` | `SENSOR_NODE` | `192.168.1.153` | `bin-0.5` | **`NOT_PRESENT`** | `21.5 h` | `STATIC_INSPECTION` — Left at home per 18 Nov checklist; 5 s HTTP retry backoff compiled |
| `REUSE_BIN_1` | `SENSOR_NODE` | `192.168.1.154` | `reuse-mod-0.5` | **`NOT_PRESENT`** | `21.6 h` | `STATIC_INSPECTION` — Left at home per 18 Nov checklist; reconnect `WiFi.setSleep(false)` compiled |
| `CAM_LAB01` | `CAMERA` | `192.168.1.150` | `ESP32CAM_Vision_FAST` | **`NOT_PRESENT`** | — | `STATIC_INSPECTION` — Left at home per 18 Nov checklist; compiled with `esp32:esp32@3.2.1` |

---

## 3. Complete Host & Container Service Inventory (`LIVE_SERVICE`)

| Service | PID / Container | Bind / Port | Memory (`WS_MB`) | Health / Probe | Status |
|---|---|---|---:|---|---|
| `smart-lab-portal-frontend-1` | `33329051c213` | `0.0.0.0:80, 443` | `~36 MB` | `HTTP 200` (`10 ms`) | **`LIVE`** |
| `smart-lab-portal-backend-1` | `cd5610783269` | `0.0.0.0:8000` | `~263 MB` | `GET /api/health` `200` (`15–70 ms`) | **`LIVE`** |
| `smart-lab-portal-db-1` | `0ab1ef38c8f4` | `127.0.0.1:5433` | `~218 MB` | TCP `:5433` (`1 ms`), `EXPLAIN` `0.33 ms` | **`LIVE`** |
| `smart-lab-portal-backup-1` | `d82912acbc46` | Internal | `~3 MB` | Healthy | **`LIVE`** |
| `smart-lab-portal-n8n-1` | `5111453da449` | `127.0.0.1:5678` | `~342 MB` | `GET /healthz` `200` (`8 ms`), 26 workflows | **`LIVE`** |
| `security_camera` (`SECCAM_LAB01`) | PID `27156` | `127.0.0.1:5100` | `595.5 MB` | `GET /health` `200` (`5 ms`), `STREAMING` | **`LIVE`** |
| `security_camera2` (`SECCAM_LAB02`) | PID `19724` | `127.0.0.1:5101` | `592.6 MB` | `GET /health` `200` (`3 ms`), `STREAMING` | **`LIVE`** |
| `face_server` | PID `30468` | `0.0.0.0:5000` | `87.9 MB` | TCP `:5000` (`2 ms`) | **`LIVE`** |
| `knowledge` (`serve.py`) | PID `37300` (wrapper `40736`) | `127.0.0.1:5199` | `17.9 MB` | `GET /health` `200` (`6 ms`), `/gpu-gate` `cpu` | **`LIVE`** |
| `voice` (`voice_service.py`) | PID `37148` | `127.0.0.1:5320` | `99.5 MB` | `GET /health` `200` (`25 ms`), TTS `686 ms` | **`LIVE`** |
| `ollama` | PID `11812` | `127.0.0.1:11434` | `26.0 MB` (idle) | `GET /api/version` `200` (`2 ms`) | **`LIVE`** |
| `opcua` (`opcua_server.py`) | PID `36396` | `127.0.0.1:4840` | `25.9 MB` | TCP `:4840` (`1 ms`), mirroring `/api/opcua/snapshot` | **`LIVE`** |
| `pc_agent` (`PC_ADMIN_LAPTOP`) | PID `38448` | Outbound -> `:8000` | `24.2 MB` | Reporting every `10 s` | **`LIVE`** |
| `lan_presence` | PID `35924` | Outbound ARP/ICMP `192.168.1.200` | `16.4 MB` | Active | **`LIVE`** |
| `mdns` (`announce.py`) | PID `35936` | UDP `224.0.0.251:5353` | `18.3 MB` | Announcing `smartlab.local -> 192.168.1.200` | **`LIVE`** |
| `ur5e_monitor` | PID `34364` | Outbound -> `.102:30003` | `16.9 MB` | Retrying unreachable controller | **`STALE`** |
| `fanuc_monitor` | PID `35576` | Outbound -> `.100:80` | `17.9 MB` | Retrying unreachable controller | **`STALE`** |
