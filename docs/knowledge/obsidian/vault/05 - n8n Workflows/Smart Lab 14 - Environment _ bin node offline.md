---
type: "n8n-workflow"
workflow_id: "f4ftl41QzO36QMMW"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/14-node-offline.json"
source_hash: "bd915fbdd064e46b6fe9e1ab4a79f5b3ff5269a02021261fb45ad8f8d1f3b538"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 14 - Environment / bin node offline

> Generated from `automation/n8n/json/14-node-offline.json` (sha256 bd915fbdd064). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Environment / bin node offline
A sensor or bin node stopped sending heartbeats - its readings are stale, never shown as current.

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
- `GET <host>/api/automation/robotics/env-offline` - Check In Backend
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Environment monitoring]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
