---
type: "n8n-workflow"
workflow_id: "VzICtIpS27WGPhJF"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/15-low-stock.json"
source_hash: "c34c2c5d8a5f7c71362fcd75abae92ecc4a9335ad578af0ad8205495eb204542"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 15 - Consumable below reorder level

> Generated from `automation/n8n/json/15-low-stock.json` (sha256 c34c2c5d8a5f). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Consumable below reorder level
Estimated quantity at or below the bin's reorder level. Only calibrated bins are estimated.

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
- `GET <host>/api/automation/robotics/low-stock` - Check In Backend
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Consumables bin]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
