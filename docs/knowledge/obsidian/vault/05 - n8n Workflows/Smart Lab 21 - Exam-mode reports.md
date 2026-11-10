---
type: "n8n-workflow"
workflow_id: "0E6cwF6DEB3kGrz9"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/21-exam-violations.json"
source_hash: "dd7ac5865c3b0f1a2286a5fcf1373b977feecd6a99da78cd40d72f98bf64c3e1"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 21 - Exam-mode reports

> Generated from `automation/n8n/json/21-exam-violations.json` (sha256 dd7ac5865c3b). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Exam-mode reports
Programs the PC agent saw running in exam mode. Staff decide what a report means; nothing is automatic.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 5}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 5 Minutes<br/><small>scheduleTrigger</small>"]
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
- `GET <host>/api/automation/robotics/exam-violations` - Check In Backend
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
