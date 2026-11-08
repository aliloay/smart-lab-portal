---
type: "n8n-workflow"
workflow_id: "kQ26kzclkT47uNaB"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/11-data-quality.json"
source_hash: "92b4c416da2b4b24a254b1760d1ec7f75cb9782a67fe77bf071319b125d19764"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 11 - Daily data quality check

> Generated from `automation/n8n/json/11-data-quality.json` (sha256 92b4c416da2b). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Data quality
Read-only consistency checks (stale sessions, entries on cancelled bookings, unattributed events, devices never reporting, implausible sensor values...). Nothing is modified - a human decides.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "days", "triggerAtHour": 6}]}`

## Flow
```mermaid
flowchart LR
  n0["Daily 06:00<br/><small>scheduleTrigger</small>"]
  n1["Run Checks In Backend<br/><small>httpRequest</small>"]
  n2["Any Check Failing?<br/><small>if</small>"]
  n3["Notify Administrators<br/><small>httpRequest</small>"]
  n4["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/data-quality` - Run Checks In Backend
- `POST <host>/api/automation/notify` - Notify Administrators
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
