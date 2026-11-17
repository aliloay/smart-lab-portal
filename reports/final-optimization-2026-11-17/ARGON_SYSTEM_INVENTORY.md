# ARGON_SYSTEM_INVENTORY.md

- **Agent**: Argon Max (Antigravity) — Independent Systems, Vision, Devices, AI Runtime & Infrastructure Auditor/Implementer
- **Date**: 2026-11-17 (Night Audit & Final Optimization Pass, post-GIU Lab Session)
- **Main Repository**: `C:\Projects\smart-lab-portal` (branch `fix/pre-lab-hardening`, commit `c68adb0`) — **UNTOUCHED** (Claude Code actively running there)
- **Argon Isolated Worktree**: `C:\Projects\smart-lab-argon` (branch `opt/argon-systems-vision-2026-11-17`, branched from `c68adb0`)

---

## 1. Host Hardware & OS Inventory (`LIVE MEASURED`)

| Attribute | Measured Value | Evidence Class |
|---|---|---|
| Host Computer Name | `DESKTOP-61G2S1I` | `LIVE MEASURED` |
| Operating System | Microsoft Windows 11 Pro (`10.0.26200`) | `LIVE MEASURED` |
| CPU | Intel Core i7-9750H @ 2.60 GHz (6 physical cores / 12 logical threads) | `LIVE MEASURED` |
| Physical RAM | 16,213 MB total (`~15.83 GB`); Free RAM: `884–1,258 MB`; Commit: `23.6 / 37.6 GB` (`62%`) | `LIVE MEASURED` |
| Discrete GPU | NVIDIA GeForce GTX 1650 (4,096 MiB VRAM, Driver `581.83`); Used: `385 MiB`, Temp: `41 °C`, Power: `7.64 W` | `LIVE MEASURED` |
| Integrated GPU | Intel UHD Graphics 630 (DirectML secondary; slower than GTX 1650 at 165 ms vs 30 ms) | `OBSERVED` |
| Storage Drive `C:` (SSD) | 222.9 GB total, 200.9 GB used, **22.0 GB free** (`10%` free) | `LIVE MEASURED` |
| Storage Drive `D:` (HDD) | 931.5 GB total, 134.9 GB used, **796.6 GB free** (`85.5%` free; hosts `D:\SmartLabData`) | `LIVE MEASURED` |
| Network Interfaces (Current) | `Wi-Fi` = `192.168.1.8/24` (Home LAN); `Ethernet` = `192.168.1.200/24` (`Disconnected`); `WSL` = `172.24.64.1` | `LIVE MEASURED` |
| Serial / USB COM Ports | `NONE` attached at time of audit (`Get-CimInstance Win32_SerialPort` empty) | `LIVE MEASURED` |

---

## 2. Docker & Container Stack (`LIVE MEASURED`)

| Container Name | Image | Status / Health | Port Mapping | CPU / Memory (`docker stats`) | Evidence Class |
|---|---|---|---|---|---|
| `smart-lab-portal-backend-1` | `smart-lab-portal-backend:latest` (built `2026-11-17 14:04`) | `Up (healthy)` | `0.0.0.0:8000->8000/tcp` | `0.21%` CPU / `262.9 MiB / 1 GiB` (`25.67%`) | `LIVE MEASURED` |
| `smart-lab-portal-frontend-1` | `smart-lab-portal-frontend:latest` (built `2026-11-17 17:04`) | `Up (healthy)` | `0.0.0.0:80->80/tcp`, `0.0.0.0:443->443/tcp` | `0.00%` CPU / `36.32 MiB / 256 MiB` (`14.19%`) | `LIVE MEASURED` |
| `smart-lab-portal-db-1` | `postgres:16-alpine` | `Up (healthy)` | `127.0.0.1:5433->5432/tcp` | `0.00%` CPU / `217.5 MiB / 1 GiB` (`21.24%`) | `LIVE MEASURED` |
| `smart-lab-portal-backup-1` | `postgres:16-alpine` | `Up (healthy)` | Internal (`db:5432`) | `0.00%` CPU / `2.70 MiB / 256 MiB` (`1.06%`) | `LIVE MEASURED` |
| `smart-lab-portal-n8n-1` | `n8nio/n8n:latest` | `Up (healthy)` | `127.0.0.1:5678->5678/tcp` | `0.06%` CPU / `342.4 MiB / 1 GiB` (`33.44%`) | `LIVE MEASURED` |

---

## 3. Host Helper Services & AI Runtime Inventory (`LIVE MEASURED` + `STATICALLY INSPECTED`)

| Service Name | Entrypoint | Bind Address & Port | Baseline State | Role & Scope Owner |
|---|---|---|---|---|
| `ollama` | `ollama serve` (Windows tray app) | `127.0.0.1:11434` | `UP` (`v0.20.7`) | Local LLM (`qwen2.5:1.5b`, `986 MB`) & embeddings (`nomic-embed-text:latest`, `274 MB`) — **Argon** |
| `face_server` | `firmware/face_server/face_server.py` | `0.0.0.0:5000` | `DOWN` (not started) | Door ESP32-CAM face recognition (`SFace` + `YuNet`, OpenCV DNN) — **Argon** |
| `security_camera` | `tools/security_vision/security_vision.py` (`camera.env`) | `127.0.0.1:5100` | `DOWN` (not started) | Security Camera 1 (`SECCAM_LAB01`, `192.168.1.106` RTSP) — **Argon** |
| `security_camera2` | `tools/security_vision/security_vision.py` (`camera2.env`) | `127.0.0.1:5101` | `DOWN` (not started) | Security Camera 2 (`SECCAM_LAB02`, `192.168.1.119` RTSP) — **Argon** |
| `ur5e_monitor` | `tools/robot_monitor/robot_collector.py` (`--type UR5E`) | Outbound TCP `:30003` -> POST `:8000` | `DOWN` (not started) | Read-only UR5e 125 Hz realtime socket decoder (`192.168.1.102`) — **Argon** |
| `fanuc_monitor` | `tools/robot_monitor/robot_collector.py` (`--type FANUC`) | Outbound HTTP `:80` -> POST `:8000` | `DOWN` (not started) | Read-only FANUC LR Mate 200iD web server scraper (`192.168.1.101`) — **Argon** |
| `knowledge` | `tools/knowledge/serve.py` | `127.0.0.1:5199` | `DOWN` (not started) | Local RAG index, `/ask` NDJSON stream, `/gpu-gate` arbiter — **Argon** |
| `voice` | `tools/voice/voice_service.py` | `127.0.0.1:5320` | `DOWN` (not started) | Faster-Whisper (`base.en` int8) STT + Piper (`en_US-lessac-medium`) TTS — **Argon** |
| `opcua` | `tools/opcua/opcua_server.py` | `127.0.0.1:4840` | `DOWN` (not started) | Read-only OPC UA mirror of `/api/opcua/snapshot` — **Argon** |
| `pc_agent` | `tools/pc_agent/pc_agent.py` | Outbound HTTP -> `:8000` | `DOWN` (not started) | Local workstation heartbeat, lock/exam policy, screen preview — **Argon** |
| `lan_presence` | `tools/lan_presence/lan_presence.py` | Outbound ping -> POST `:8000` | `DOWN` (not started) | Read-only ICMP ping of `PC_DEVICES` when agent is silent — **Argon** |
| `mdns` | `tools/mdns/announce.py` | UDP `224.0.0.251:5353` | `DOWN` (not started) | Announces `smartlab.local` on the `192.168.1.x` lab router interface — **Argon** |

---

## 4. Registered Devices in PostgreSQL (`smartlab` DB — `LIVE MEASURED`)

| `device_uid` | `device_type` | `ip_address` | `firmware_version` | `is_online` (DB) | `last_seen_at` (UTC) | Notes |
|---|---|---|---|---|---|---|
| `MASTER_LAB01` | `MASTER_CONTROLLER` | `192.168.1.109` | `5.0.0-offline-door` | `true` | `2026-11-17 17:04:01` | Door lock controller, keypad, PN532 NFC, fingerprint |
| `ENV_LAB01` | `SENSOR_NODE` | `192.168.1.105` | `3.1.1-env-core0net` | `true` | `2026-11-17 17:03:59` | DHT22, MQ-2, Flame, LDR, Sound (Core 0 netTask) |
| `BIN_NODE_1` | `SENSOR_NODE` | `192.168.1.190` | `2.4.1-hx711-cal` | `true` | `2026-11-17 17:04:00` | Consumables Bin (`HX711` load cell) |
| `REUSE_BIN_1` | `REUSABLE_BIN` | `192.168.1.116` | `3.4-portal` | `true` | `2026-11-17 17:04:01` | Reusable Bin (`PN532` + `HX711` + LCD) |
| `SECCAM_LAB01` | `CAMERA_NODE` | `127.0.0.1` (RTSP `.106`) | `1.0.0-Tapo_C200` | `true` | `2026-11-17 17:10:03` | Tapo C200 #1 (Entrance / Desks / UR5e view) |
| `SECCAM_LAB02` | `CAMERA_NODE` | `127.0.0.1` (RTSP `.119`) | `1.0.0-Tapo_C200` | `true` | `2026-11-17 17:10:04` | Tapo C200 #2 (Back corner / FANUC / UR5e view) |
| `UR5E_01` | `ROBOT_ARM` | `192.168.1.102` | `URSoftware-5.x-rt30003` | `true` | `2026-11-17 17:05:31` | Universal Robots UR5e (read-only TCP 30003) |
| `FANUC_01` | `ROBOT_ARM` | `192.168.1.101` | `R-30iB-Mate-Plus-http80` | `true` | `2026-11-17 17:05:32` | FANUC LR Mate 200iD/7L (read-only HTTP 80) |
| `PC_ADMIN_LAPTOP` | `WORKSTATION_AGENT` | `192.168.1.200` | `1.3.0-pc-agent` | `true` | `2026-11-17 17:09:57` | Portal host laptop (`DESKTOP-61G2S1I`) |
| `PC_ENG` | `WORKSTATION_AGENT` | `192.168.1.210` | `1.3.0-pc-agent` | `true` | `2026-11-17 17:03:54` | Engineer PC (`S2PC136`, dual-NIC bridge `10.30.11.136` + `.210`) |
| `CAM_DOOR_01` | `CAMERA_NODE` | `192.168.1.150` | `ESP32-CAM-OV2640` | `false` | `2026-10-11 19:21:08` | Door ESP32-CAM (posts via `face_server` / `MASTER_LAB01`) |
| `PC_01` .. `PC_16` | `WORKSTATION_AGENT` | `10.40.20.x` / `192.168.1.x` | `1.1.0`–`1.3.0` | `false` | `2026-10-08` to `2026-11-03` | 16 Student Lab PCs (awaiting GIU IT firewall rule on `S2PC136`) |
