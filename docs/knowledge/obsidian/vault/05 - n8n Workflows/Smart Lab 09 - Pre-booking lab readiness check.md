---
type: "n8n-workflow"
workflow_id: "BEoxaJKi19VheL3G"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/09-pre-booking-check.json"
source_hash: "62ec98a78f542d5d2e2e891835d5c08d137e3295520a5f53c2d4d55bdad8a82c"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 09 - Pre-booking lab readiness check

> Generated from `automation/n8n/json/09-pre-booking-check.json` (sha256 62ec98a78f54). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Pre-booking check
Warns the student and staff when a lab is not ready (controller offline, critical issue). It never cancels or changes a booking.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 15}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 15 Minutes<br/><small>scheduleTrigger</small>"]
  n1["Get Bookings In Next Hour<br/><small>httpRequest</small>"]
  n2["One Item Per Booking<br/><small>splitOut</small>"]
  n3["Lab Not Ready<br/><small>filter</small>"]
  n4["Warn Student<br/><small>httpRequest</small>"]
  n5["Warn Staff<br/><small>httpRequest</small>"]
  n6["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
  n5 --> n6
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/bookings/upcoming?within_minutes=60` - Get Bookings In Next Hour
- `POST <host>/api/automation/notify` - Warn Student
- `POST <host>/api/automation/notify` - Warn Staff
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key

## External services
- none found: all calls go to the local backend

## Related
- [[Bookings and labs]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
