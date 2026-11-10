---
type: "n8n-workflow"
workflow_id: "smartlab-23"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/23-emergency.json"
source_hash: "eaa7c7fddab6e2c5636fa2ad6e5fca6692fc30d27477455f58e676ea5f394afb"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 23 - Emergency: warn people inside, check the door

> Generated from `automation/n8n/json/23-emergency.json` (sha256 eaa7c7fddab6). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Emergency
Set by an admin in the Emergency tab. 1) Everyone INSIDE that lab gets a notice telling them what to do (leave / lockdown / the admin's message). 2) After 30 s: if the door controller has not confirmed the new state, the admins are told to act at the door.

This workflow NEVER opens or locks anything - the door applies the state itself.

## Triggers
- webhook: `"smartlab-emergency-set"`

## Flow
```mermaid
flowchart LR
  n0["Emergency Set<br/><small>webhook</small>"]
  n1["Get Emergency State<br/><small>httpRequest</small>"]
  n2["One Item Per Person Inside<br/><small>splitOut</small>"]
  n3["Warn Person Inside<br/><small>httpRequest</small>"]
  n4["Give The Door 30 s<br/><small>wait</small>"]
  n5["Check Door Applied It<br/><small>httpRequest</small>"]
  n6["Door Has Not Applied It?<br/><small>if</small>"]
  n7["Alert Admins<br/><small>httpRequest</small>"]
  n8["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n1 --> n4
  n2 --> n3
  n4 --> n5
  n5 --> n6
  n5 --> n8
  n6 --> n7
```

## Endpoints called (host redacted)
- `GET =<host>/api/automation/emergency/{{ $json.body.lab_id }}` - Get Emergency State
- `POST <host>/api/automation/notify` - Warn Person Inside
- `GET =<host>/api/automation/emergency/{{ $json.lab_id }}` - Check Door Applied It
- `POST <host>/api/automation/notify` - Alert Admins
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
