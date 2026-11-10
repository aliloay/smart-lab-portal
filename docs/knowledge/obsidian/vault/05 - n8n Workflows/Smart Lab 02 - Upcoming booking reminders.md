---
type: "n8n-workflow"
workflow_id: "wb24O1Xymccm2Lw4"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/02-booking-reminders.json"
source_hash: "1f940607da49a1ccc4ecc6f81e51e04d0f1f90d06e4359dfa920513af3589984"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 02 - Upcoming booking reminders

> Generated from `automation/n8n/json/02-booking-reminders.json` (sha256 1f940607da49). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Upcoming booking reminders
Idempotent: the backend raises at most one reminder per booking - shared with the portal's own lazy reminder, so a retry or both paths firing never sends two.

## Triggers
- scheduleTrigger: `{"interval": [{"field": "minutes", "minutesInterval": 5}]}`

## Flow
```mermaid
flowchart LR
  n0["Every 5 Minutes<br/><small>scheduleTrigger</small>"]
  n1["Get Bookings Starting Soon<br/><small>httpRequest</small>"]
  n2["One Item Per Booking<br/><small>splitOut</small>"]
  n3["Not Reminded Yet<br/><small>filter</small>"]
  n4["Raise Reminder<br/><small>httpRequest</small>"]
  n5["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## Endpoints called (host redacted)
- `GET <host>/api/automation/bookings/upcoming?within_minutes=20` - Get Bookings Starting Soon
- `POST =<host>/api/automation/bookings/{{ $json.booking_id }}/remind` - Raise Reminder
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
