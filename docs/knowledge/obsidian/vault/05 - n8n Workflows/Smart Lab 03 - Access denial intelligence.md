---
type: "n8n-workflow"
workflow_id: "ZhcCkMf7KgQDfmSh"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/03-access-denial-intelligence.json"
source_hash: "757cd1a3977126ab8457550746640fc08308545954f3346333b6dfecd1104b15"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 03 - Access denial intelligence

> Generated from `automation/n8n/json/03-access-denial-intelligence.json` (sha256 757cd1a39771). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Access denial intelligence
1 refusal = normal (early, wrong code). 3 within 10 min = warning (thresholds in backend config). One alert per burst via dedupe key.

This workflow NEVER locks or unlocks anything - the door decides on its own.

## Triggers
- webhook: `"smartlab-access-denied"`

## Flow
```mermaid
flowchart LR
  n0["Access Denied Event<br/><small>webhook</small>"]
  n1["Evaluate Denial Burst<br/><small>httpRequest</small>"]
  n2["Is It A Burst?<br/><small>if</small>"]
  n3["Raise Security Alert<br/><small>httpRequest</small>"]
  n4["Notify Staff<br/><small>httpRequest</small>"]
  n5["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## Endpoints called (host redacted)
- `GET =<host>/api/automation/access/denials{{ $json.body.lab_id ? "?lab_id=" + $json.body.lab_id : "" }}` - Evaluate Denial Burst
- `POST <host>/api/automation/alerts` - Raise Security Alert
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key
- httpHeaderAuth:Smart Lab webhook token

## External services
- none found: all calls go to the local backend

## Related
- [[Door and access]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
