# Tool integrations

Read-only tools available to the staff assistant (from `ai.py` / `tool_gateway.py`): `list_labs`, `get_operations_overview`, `get_environment`, `get_lab_readiness`, `get_trends`, `get_anomalies`, `list_open_issues`, `get_maintenance_priorities`, `get_report`.

| Integration | Direction | Notes |
|---|---|---|
| Database | Read | Every tool is a typed read with validated arguments |
| Bookings | Proposal → user confirms → normal endpoint | The only change an assistant can lead to |
| MCP clients | Read | `/api/tools` and `tools/mcp_server/server.py` expose the same read-only tools |
| n8n | Separate | n8n calls backend automation endpoints; the assistant does not trigger workflows |
| Knowledge service | Read | Staff project questions only |
| Voice service | In/out | Local faster-whisper (speech to text) and Piper (text to speech), hourly limit per user |
| Doors, relays, robots | **None** | Out of reach by design |
