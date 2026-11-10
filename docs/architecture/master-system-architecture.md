# Master system architecture

The platform is one backend (FastAPI + PostgreSQL) that every device, service and user interface reports to over the local network. ESP32 nodes, camera services, the robot collector and the PC agents send HTTP requests to the API; the portal, phones and n8n read and act through the same API. The AI assistants and the knowledge agent run on local models. Every arrow below was checked against the code on 9 November 2026.

Diagram sources: [master-system-architecture.mmd](master-system-architecture.mmd), [network-architecture.mmd](network-architecture.mmd), [data-flow.mmd](data-flow.mmd), [ai-automation-architecture.mmd](ai-automation-architecture.mmd), [digital-twin-ar-architecture.mmd](digital-twin-ar-architecture.mmd).

## 1. Components and protocols

```mermaid
flowchart LR
  subgraph PHY["Physical layer (Smart_Lab Wi-Fi, 192.168.1.0/24)"]
    MASTER["Master Node (ESP32)<br/>PN532 NFC · AS608 fingerprint · ST7735 TFT<br/>relay → 12 V lock · door reed · LEDs"]
    ENV["Environment Node (ESP32)<br/>DHT22 · MQ-2 · 2× PIR · flame board"]
    CONS["Consumables Node (ESP32)<br/>HX711 load cell · 16×2 LCD"]
    REUSE["Reusables Node (ESP32)<br/>PN532 NFC · servo lid · LCD"]
    ECAM["ESP32-CAM<br/>door face camera"]
    SCAM["IP security cameras (RTSP)"]
    ROBOT["UR5e / FANUC (read-only)"]
    PCS["Lab PCs (PC agent)"]
    PHONE["Phone browser (HTTPS, camera)"]
  end
  subgraph EDGE["Engineer PC: local services"]
    FACE["Face server"]
    VISION["Security vision<br/>YOLO26s · tracking · identity"]
    COLLECT["Robot collector<br/>ur_rtde receive only"]
    KB["Knowledge agent :5199"]
    OLLAMA["Ollama · qwen2.5"]
    VAULT[("Obsidian vault")]
  end
  subgraph STACK["Docker Compose stack"]
    NGINX["frontend (nginx + React) :443/:80"]
    API["backend (FastAPI) :8000"]
    DB[("PostgreSQL 16")]
    N8N["n8n 2.40.7 :5678 (localhost)"]
    BK["backup"]
  end
  MASTER -- "HTTP /api/access/*" --> API
  ENV -- "HTTP readings/events" --> API
  CONS -- "HTTP /api/inventory/measurements" --> API
  REUSE -- "HTTP /api/reusable/*" --> API
  MASTER -- "HTTP /identify" --> FACE
  FACE -- "HTTP capture" --> ECAM
  API -- "HTTP /enroll" --> FACE
  SCAM -- "RTSP" --> VISION
  VISION -- "HTTP /api/security/*" --> API
  ROBOT -- "RTDE (read)" --> COLLECT
  COLLECT -- "HTTP /api/robots/telemetry" --> API
  PCS -- "HTTP agent reports" --> API
  PHONE -- "HTTPS" --> NGINX
  NGINX -- "/api proxy" --> API
  API --- DB
  BK -- "pg_dump" --> DB
  N8N -- "HTTP /api/automation/*" --> API
  API -- "webhooks" --> N8N
  API -- "Ollama API" --> OLLAMA
  API -- "project questions" --> KB
  KB -- "index + read" --> VAULT
  KB --> OLLAMA
```

Protocol facts: there is **no MQTT broker, PLC or Raspberry Pi** in the running system (searched: no MQTT client in backend or firmware). Devices use plain HTTP to the API with per-device keys; cameras use RTSP to the vision service only; robots are read with `ur_rtde` receive interfaces and never commanded.

## 2. Access to presence (the core integration)

```mermaid
sequenceDiagram
  participant P as Person
  participant M as Master Node
  participant F as Face server
  participant A as API + DB
  participant V as Security vision
  participant U as Portal
  P->>M: NFC card / QR (factor 1)
  M->>A: POST /api/access/validate-qr or card check
  P->>M: Fingerprint or face (factor 2)
  M->>F: /identify (face path)
  M->>A: POST /api/access/grant (or /deny)
  A-->>M: session opened
  M->>M: TFT "ACCESS GRANTED", relay releases the lock
  V->>A: person tracks, faces, looks (per frame batch)
  A->>A: match tracks to open door sessions
  A-->>U: occupants, "Person with no door entry", "More people seen than entered"
  Note over A,U: an exit is recorded only when one is observed (door or camera)
```

Detection, identity and presence are separate steps; see [tracking-and-presence.md](../computer-vision/tracking-and-presence.md).

## 3. Layers

| Layer | What it contains | Code |
|---|---|---|
| Hardware nodes | Master, Environment, Consumables, Reusables, ESP32-CAM | `firmware/` |
| Vision | YOLO26s person detection, tracking, identity evidence, equipment zones | `tools/security_vision/` |
| Robots | UR5e RTDE and FANUC read-only collectors, twin | `tools/robot_monitor/`, `tools/ur5e_collector/`, `frontend/src/components/robot/` |
| PCs | PC agent, screen wall, screen sharing, exam mode | `tools/pc_agent/`, `frontend/src/components/ScreenShare.tsx` |
| Backend | 329 API operations, rules, alerts, sessions, reports | `backend/app/` |
| Data | PostgreSQL 16, 42 tables, nightly backups | `backend/app/models/`, `backend/alembic/` |
| Portal | React 18 + Vite 6 + Tailwind 3.4 | `frontend/src/` |
| AI | Lab assistant (Ollama, optional Claude API), knowledge agent | `backend/app/services/ai.py`, `agent.py`, `tools/knowledge/` |
| Knowledge | Obsidian vault built from the repository | `tools/knowledge/kb.py`, `docs/knowledge/obsidian/vault/` |
| Automation | 23 n8n workflows; the backend decides, n8n schedules and notifies | `automation/n8n/` |
| AR | Phone "Scan the lab": QR markers decoded on the phone, live records pinned | `frontend/src/pages/Scan.tsx`, `routes/scan.py` |

More detail: [network](../deployment/local-network-and-offline.md), [hardware](../hardware/), [software](../software/), [AI](../ai/), [automation](../automation/n8n-overview.md).
