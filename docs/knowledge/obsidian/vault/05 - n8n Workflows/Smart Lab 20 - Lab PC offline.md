---
type: "n8n-workflow"
workflow_id: "kkBmwinhDIURUNqn"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/20-pc-offline.json"
source_hash: "0189a7485b138524b79634cc90583d5d49ee43207525d5c246ff3bca04fd623d"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 20 - Lab PC offline

> Generated from `automation/n8n/json/20-pc-offline.json` (sha256 0189a7485b13). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Lab PC offline
A lab PC agent stopped reporting.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 15}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 15 Minutes<br/><small>scheduleTrigger</small>"]
  n1["Check In Backend<br/><small>httpRequest</small>"]
  n2["One Item Per Finding<br/><small>splitOut</small>"]
  n3["Notify Staff<br/><small>httpRequest</small>"]
  n4["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/robotics/pcs-offline` - Check In Backend
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
