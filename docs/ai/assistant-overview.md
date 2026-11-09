# AI assistants: overview

| Assistant | Who | Where | What it answers |
|---|---|---|---|
| **Ask the lab** (staff) | Staff, admins | AI bubble / Operations pages · `POST /api/ai/ask` | Operational state from the database: occupancy, environment, devices, issues, bookings, trends, anomalies, reports, maintenance priorities |
| **Student assistant** | Students | `POST /api/ai/student/ask` | How to book, QR codes, face registration, their own bookings; no lab-wide data |
| **Ask the project** (knowledge agent) | Staff | `POST /api/knowledge/ask` → `tools/knowledge` | How the system is built, from the Obsidian vault and repository, with sources |
| **Scan the lab** | Staff | Phone camera page | Questions about the equipment in view (target-aware) |
| **Talk** (voice) | Signed-in users | `/api/voice/transcribe`, `/api/voice/speak` | Speech in and out through the local voice service (faster-whisper + Piper); the text goes through the normal assistant |

Typical questions: "Who is in the lab?", "What is running low?", "Show the recent activity", "Compare this week with last week", "Give me today's summary", "How to make the UR5e better?" (answered from that device's records), "What is the current operational status of the lab?" (knowledge agent).

Many common questions are answered **instantly from the records without a language model** (`agent.py` instant routes: empty labs, low stock, recent activity, comparisons, daily report, device advice); the model is used for open questions and tool-calling.

See: [agent-architecture.md](agent-architecture.md) · [model-configuration.md](model-configuration.md) · [knowledge-and-context.md](knowledge-and-context.md) · [tool-integrations.md](tool-integrations.md) · [security-and-limitations.md](security-and-limitations.md) · design notes: [AI_ASSISTANT.md](../AI_ASSISTANT.md).
