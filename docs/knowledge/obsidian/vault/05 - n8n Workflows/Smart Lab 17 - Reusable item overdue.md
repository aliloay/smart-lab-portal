---
type: "n8n-workflow"
workflow_id: "x9pBFvrZc2KKfnB2"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/17-asset-overdue.json"
source_hash: "f6c3261d0cfdebd2ce019d4726c8cd853999b99d3199f0ee7b6682422e3556c0"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 17 - Reusable item overdue

> Generated from `automation/n8n/json/17-asset-overdue.json` (sha256 f6c3261d0cfd). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Reusable item overdue
A smart-bin item checked out for more than 24 h.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "hours", "hoursInterval": 1}]}`

## Flow
```mermaid
flowchart LR
  n0["Every Hour<br/><small>scheduleTrigger</small>"]
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
- `GET <host>/api/automation/robotics/assets-overdue` - Check In Backend
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Reusables bin]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
