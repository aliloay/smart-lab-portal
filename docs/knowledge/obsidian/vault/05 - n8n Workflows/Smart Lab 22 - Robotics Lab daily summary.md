---
type: "n8n-workflow"
workflow_id: "l3xYkfCjlNRy9c1d"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/22-robotics-daily.json"
source_hash: "1d8d8b24af3d73eb7839b538984f39c65b40140346a6c17eb1f9f610fc975b92"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 22 - Robotics Lab daily summary

> Generated from `automation/n8n/json/22-robotics-daily.json` (sha256 1d8d8b24af3d). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Robotics Lab daily summary
Robot run time, consumable withdrawals, items out, environment alerts - from recorded data only.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "days", "triggerAtHour": 7}]}`

## Flow
```mermaid
flowchart LR
  n0["Daily 07:00<br/><small>scheduleTrigger</small>"]
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
- `GET <host>/api/automation/robotics/daily` - Check In Backend
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Robots (read-only)]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
