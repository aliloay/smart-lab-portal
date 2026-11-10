---
type: "n8n-workflow"
workflow_id: "SmZcJv5WrtpyOZIr"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/08-sensor-thresholds.json"
source_hash: "9816c053dcb9d614674e5d016baa95c51fdad7e21fc9ec782c6339a9985d0f7e"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 08 - Sensor threshold alerts

> Generated from `automation/n8n/json/08-sensor-thresholds.json` (sha256 9816c053dcb9). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Sensor thresholds (configuration-driven)
Thresholds live in backend SENSOR_THRESHOLDS (metric=min:max). Stale readings are never treated as OK. With no sensor node installed the backend returns no_data and this workflow does nothing - no simulated values.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 10}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 10 Minutes<br/><small>scheduleTrigger</small>"]
  n1["Evaluate Sensors In Backend<br/><small>httpRequest</small>"]
  n2["One Item Per Breach<br/><small>splitOut</small>"]
  n3["Raise Threshold Alert<br/><small>httpRequest</small>"]
  n4["Notify Staff<br/><small>httpRequest</small>"]
  n5["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/sensors/evaluate?max_age_minutes=30` - Evaluate Sensors In Backend
- `POST <host>/api/automation/alerts` - Raise Threshold Alert
- `POST <host>/api/automation/notify` - Notify Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Environment monitoring]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
