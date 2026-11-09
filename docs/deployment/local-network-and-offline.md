# Local network and offline operation

The platform is built to run its core operations on one local network with no internet connection. Diagram: [network-architecture.mmd](../architecture/network-architecture.mmd). Network setup and addresses: [SMART_LAB_NETWORK_CONFIGURATION.md](../SMART_LAB_NETWORK_CONFIGURATION.md).

## Topology

| Part | Where | Exposure |
|---|---|---|
| Smart_Lab router | 192.168.1.0/24 | Local Wi-Fi; the core does not need an internet uplink |
| Engineer PC | 192.168.1.200 (cable) | nginx 443/80 and API 8000 on the LAN; PostgreSQL (5433), n8n (5678), Ollama (11434), knowledge (5199) and camera services (5100/5101) on 127.0.0.1 only |
| ESP32 nodes, ESP32-CAM | Wi-Fi, DHCP reservations (for example Environment 192.168.1.152) | HTTP to the API with device keys |
| IP cameras | Wi-Fi/LAN, fixed address | RTSP to the camera service only |
| Phones | Wi-Fi | HTTPS to nginx (local CA) |
| GIU lab PCs (other network) | Through `tools/relay` on the engineer PC | Only the portal ports |

Firewall rules are limited to 192.168.1.0/24 and the exact ports (scripts/tighten_firewall.ps1, firmware/face_server/allow_firewall.bat). Nothing is published to the internet; there is no tunnel or public reverse proxy.

## What needs the internet

| Capability | Local operation | Internet required | External dependency | Current verified status |
|---|---|---|---|---|
| Door access (NFC, QR, fingerprint, face) | Yes | No | None | Bench-verified; face path needs the face server running |
| Environment, consumables, reusables nodes | Yes | No | None | See [hardware-validation.md](../hardware/hardware-validation.md) |
| Camera detection, tracking, presence cross-check | Yes | No | None | Verified in the lab (Oct 2026) |
| Portal, database, reports, exports | Yes | No | None (CSP allows only the portal itself, no CDN fonts) | Verified on the LAN |
| Robot twin (UR5e) | Yes | No | None | Verified with the robot (Oct 2026); FANUC not yet |
| Phone Scan (AR) | Yes | No | Local CA trusted on the phone | Headless test only |
| AI assistants | Yes (Ollama) | No (`AI_LOCAL_ONLY=true`) | None by default | Verified locally |
| Knowledge agent | Yes | No | None | Verified locally |
| Voice | Yes (faster-whisper with local files, Piper) | No | None | Verified locally |
| n8n workflows | Yes | No for the exported workflows | E-mail delivery would need SMTP | Exports verified; live runs recorded earlier |
| First-time setup | - | **Yes** | Docker images, npm/pip packages, Ollama models, camera app activation | One-time |
| Optional cloud AI | - | Yes | Claude API, only with `AI_LOCAL_ONLY=false` | Off by default |

**Status of the formal offline test:** the checker `tools/offline/offline_check.py` (13 checks every minute for 30 minutes with the internet disconnected) is ready, and its dry run passed 12/13 with the internet up. The run with the internet disconnected has **not** been done yet ([OFFLINE_TEST_2026-10-27.md](../OFFLINE_TEST_2026-10-27.md)). Until then, offline operation is a design property verified by reading the code, not by measurement.

Local Wi-Fi is not the same as offline: on a network with internet the system still sends nothing out by default, but updates, model downloads and camera app setup need a connection.
