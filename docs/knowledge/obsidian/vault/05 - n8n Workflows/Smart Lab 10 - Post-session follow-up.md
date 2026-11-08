---
type: "n8n-workflow"
workflow_id: "9lJpTc93G2Hl4YKH"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/10-post-session.json"
source_hash: "066192ada8a1a8a5bda0462f96b25cbb83b398dd1f53e385063eb4c6d3b79abe"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 10 - Post-session follow-up

> Generated from `automation/n8n/json/10-post-session.json` (sha256 066192ada8a1). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Post-session
Attended: summary, and says 'exit not recorded' honestly when no exit was observed. Missed: a gentle no-show note. Text is composed by the backend.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 30}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 30 Minutes<br/><small>scheduleTrigger</small>"]
  n1["Get Bookings That Just Ended<br/><small>httpRequest</small>"]
  n2["One Item Per Booking<br/><small>splitOut</small>"]
  n3["Send Follow-up<br/><small>httpRequest</small>"]
  n4["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/bookings/ended?minutes=60` - Get Bookings That Just Ended
- `POST <host>/api/automation/notify` - Send Follow-up
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
