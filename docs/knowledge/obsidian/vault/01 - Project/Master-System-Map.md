---
type: system-map
updated: "2026-10-14"
sources: ["docker-compose.yml", "launch.bat", "devices table (portal, 2026-10-13)", "memory/project-system-overview.md"]
---
# Master system map

> Solid lines: verified in code/config or the portal's device list (2026-10-13). Dashed: reported, not re-verified.
> Addresses from the portal's registered devices; the robots' own addresses are **not configured** yet.

```mermaid
flowchart LR
  subgraph LAN["Smart_Lab router (local, no internet)"]
    CAM["ESP32-CAM entry camera<br/>192.168.1.150"]
    MASTER["Master ESP32 door controller<br/>192.168.1.151<br/>only door authority"]
    ENV["Environment node ESP32<br/>192.168.1.152"]
    BIN["Consumables bin ESP32<br/>192.168.1.153"]
    REUSE["Reusables bin ESP32<br/>192.168.1.154"]
    MC210["Security camera MC210<br/>192.168.1.155 (memory note; blank in the portal)"]
    UR["UR5e (read-only)<br/>IP not configured"]
    FAN["FANUC ER-4iA (read-only)<br/>IP not configured"]
  end
  subgraph LAPTOP["Laptop 192.168.1.200"]
    subgraph DOCKER["Docker Compose"]
      BE["backend (FastAPI) :8000"]
      DB[("PostgreSQL")]
      FE["frontend (nginx) :80/:443, IoT :8080"]
      N8N["n8n :5678 (localhost)"]
    end
    FACE["face server :5000"]
    SV["security_vision :5100<br/>YOLO26s + re-ID (GTX 1650)"]
    OLL["Ollama :11434 (localhost)"]
    KB["knowledge tool (kb.py)"]
  end
  MASTER --> BE
  CAM --> FACE
  ENV --> BE
  BIN --> BE
  REUSE --> BE
  MC210 --> SV --> BE
  BE --> DB
  FE --> BE
  N8N -->|"/api/automation (23 workflows)"| BE
  BE -.-> OLL
  KB --> OLL
  UR -. "RTDE read-only (pending IP)" .-> BE
  FAN -. "interface unknown" .-> BE
```

Related: [[Door and access]] · [[SecurityCam (vision)]] · [[Robots (read-only)]] · [[Consumables bin]] · [[Reusables bin]] ·
[[Environment monitoring]] · [[n8n automation]] · [[Backend and data]] · [[Database-Data-Dictionary]]
