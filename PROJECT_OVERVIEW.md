# Project overview

**Locally Operated AIoT Facility Intelligence Platform:** design and development of a lightweight, locally operated AIoT platform for integrated smart facility management and vision-based presence verification.

**In one paragraph.** Four ESP32 nodes (door access, environment, consumables, reusables), IP cameras with a YOLO26s person tracker, read-only robot collectors and PC agents all report over the local network to one FastAPI + PostgreSQL backend. The backend joins those records: a door entry becomes a presence record the cameras can confirm or contradict; stock that moves while nobody is inside becomes a record to check; a smoke reading becomes an alert and a workflow. Staff see everything in one portal, ask local AI assistants about it, look up how the system works through an agent that reads the project's Obsidian knowledge base, let n8n schedule the routine checks and reports, watch a read-only digital twin of the UR5e, and point a phone at equipment to see its live record. The core needs no internet.

| Layer | Summary | More |
|---|---|---|
| Hardware | Master, Environment, Consumables, Reusables nodes in printed enclosures | [docs/hardware/](docs/hardware/master-node.md) |
| Vision | YOLO26s detection, tracking, identity evidence, access cross-check | [docs/computer-vision/](docs/computer-vision/vision-system.md) |
| Backend and data | 329 API operations, 42 tables | [docs/software/](docs/software/backend.md) |
| Portal | React 18 portal for every role | [docs/PORTAL_GUIDE.md](docs/PORTAL_GUIDE.md) |
| AI | Local assistants, knowledge agent, voice | [docs/ai/](docs/ai/assistant-overview.md) |
| Knowledge | Obsidian vault generated from the repository | [docs/knowledge/](docs/knowledge/obsidian-overview.md) |
| Automation | 23 n8n workflows | [docs/automation/](docs/automation/n8n-overview.md) |
| Digital twin | UR5e read-only twin | [docs/digital-twin/](docs/digital-twin/overview.md) |
| AR | Phone "Scan the lab" | [docs/augmented-reality/](docs/augmented-reality/overview.md) |
| Network | Local-first, dependency table | [docs/deployment/](docs/deployment/local-network-and-offline.md) |

Academic origin: GIU Bachelor's thesis "Design and Development of an Intelligent IoT-Based Smart Research Laboratory".
