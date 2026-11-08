---
type: "n8n-workflow"
workflow_id: "OzSJhnKihJQBDP5P"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/06-daily-report.json"
source_hash: "c7416e9793f9ad0c0e939b07665d02f783101f5d137bd0bf0d5a82146e73a8bd"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 06 - Daily lab report

> Generated from `automation/n8n/json/06-daily-report.json` (sha256 c7416e9793f9). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Daily lab report
The backend computes every figure from recorded rows (no estimates); n8n only schedules and delivers. Idempotent per day via dedupe key. Add an Email/Slack node in parallel to Send To Administrators for an external channel.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "days", "triggerAtHour": 20}]}`

## Flow
```mermaid
flowchart LR
  n0["Daily 20:00<br/><small>scheduleTrigger</small>"]
  n1["Build Report In Backend<br/><small>httpRequest</small>"]
  n2["Send To Administrators<br/><small>httpRequest</small>"]
  n3["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/reports/daily` - Build Report In Backend
- `POST <host>/api/automation/notify` - Send To Administrators
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
