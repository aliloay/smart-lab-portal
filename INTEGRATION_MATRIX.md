# Integration matrix

Who talks to whom, how, and what was verified (10 Nov 2026). Details: [docs/architecture/master-system-architecture.md](docs/architecture/master-system-architecture.md).

| From | To | Protocol / path | Auth | Verified |
|---|---|---|---|---|
| Master Node | API | HTTP `/api/access/*` (validate-qr, grant, deny, events, heartbeat, telemetry, commands) | `X-Device-Key` | Bench + lab |
| Master Node | Face server | HTTP `/identify` | Local network | Lab runs |
| Face server | ESP32-CAM | HTTP capture | Local network | Lab runs |
| API | Face server | HTTP `/enroll` | Server URL in settings | Lab runs |
| Environment Node | API | HTTP readings and events | `X-Device-Key` | Bench |
| Consumables Node | API | HTTP `/api/inventory/measurements` | `X-Device-Key` | Lab use |
| Reusables Node | API | HTTP `/api/reusable/scan`, `/complete` | `X-Device-Key` | Partial bench |
| IP cameras | Security vision | RTSP | Camera account in `camera*.env` (git-ignored) | Lab |
| Security vision | API | HTTP `/api/security/*` | `X-Device-Key` | Lab + tests |
| UR5e | Robot collector | RTDE receive (read-only) | - | Lab |
| Robot collector | API | HTTP `/api/robots/telemetry`, `/events` | `X-Device-Key` | Lab + tests |
| PC agents | API | HTTP agent reports | Per-PC keys | Lab day 4 Nov |
| Portal / phones | nginx → API | HTTPS, `/api/*`, WebSocket `/ws/activity` | JWT | Verified |
| n8n | API | HTTP `/api/automation/*` | `X-Automation-Key` | Exports + earlier live runs |
| API | n8n | Webhooks (`AUTOMATION_WEBHOOK_BASE`) | Webhook token | Earlier live runs |
| API | Ollama | Ollama HTTP API (127.0.0.1) | Local | Verified |
| API | Knowledge service | HTTP `/ask` (host.docker.internal:5199) | `X-KB-Key` | Verified |
| Knowledge service | Obsidian vault | File read/write (generated folders only) | Local | Verified |
| Backup service | PostgreSQL | `pg_dump` | DB credentials from `.env` | Verified |
