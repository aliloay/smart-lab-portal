---
type: "n8n-workflow"
workflow_id: "zXZvJP5vAQbPtAG6"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/05-maintenance-automation.json"
source_hash: "60fa0806d80e1e88d3135fb87286a937b293869403a3f9883cc9f87efc25a047"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 05 - Maintenance automation

> Generated from `automation/n8n/json/05-maintenance-automation.json` (sha256 60fa0806d80e). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Maintenance automation
Event path: a HIGH/CRITICAL issue in a lab with bookings in the next 24 h is flagged to staff at once.
Daily path: overdue (per published SLA), urgent unassigned, and equipment due for maintenance within 7 days.

## Triggers
- webhook: `"smartlab-issue-created"`
- scheduleTrigger: `{"interval": [{"triggerAtHour": 8}]}`

## Flow
```mermaid
flowchart LR
  n0["Issue Created Event<br/><small>webhook</small>"]
  n1["Get Issue Context<br/><small>httpRequest</small>"]
  n2["Urgent And Lab In Use?<br/><small>if</small>"]
  n3["Notify Staff Of Impact<br/><small>httpRequest</small>"]
  n4["Record Run<br/><small>httpRequest</small>"]
  n5["Daily 08:00<br/><small>scheduleTrigger</small>"]
  n6["Get Maintenance Digest<br/><small>httpRequest</small>"]
  n7["Anything Needs Attention?<br/><small>if</small>"]
  n8["Send Maintenance Digest<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n5 --> n6
  n6 --> n7
  n7 --> n8
  n8 --> n4
```

## Endpoints called (host redacted)
- `GET =<host>/api/automation/issues/{{ $json.body.object.id }}` - Get Issue Context
- `POST <host>/api/automation/notify` - Notify Staff Of Impact
- `POST <host>/api/automation/runs` - Record Run
- `GET <host>/api/automation/maintenance` - Get Maintenance Digest
- `POST <host>/api/automation/notify` - Send Maintenance Digest

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key
- httpHeaderAuth:Smart Lab webhook token

## External services
- none found: all calls go to the local backend

## Related
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
