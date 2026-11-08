---
type: "n8n-workflow"
workflow_id: "kGJmLTC5T0fuQvQN"
status_in_file: "inactive"
live_status: "active"
live_checked: "2026-11-04T00:02:25+02:00"
live_matches_file: true
source_path: "automation/n8n/json/01-booking-confirmation.json"
source_hash: "4fcebe0333634c38b55cbb3ba1dadd6ce6d9a28da4d9d762418c19ee03863774"
generated: true
updated: "2026-11-04T00:02:39+02:00"
tags: ["n8n"]
---

# Smart Lab 01 - Booking confirmation briefing

> Generated from `automation/n8n/json/01-booking-confirmation.json` (sha256 4fcebe033363). Configured behaviour, not observed runs.

## Live state
**active** in the running n8n (export of 2026-11-04T00:02:25+02:00). Nodes and connections match this file.

## Purpose
## Booking confirmation briefing
The portal already confirms the booking. This adds a heads-up only when the lab is not in a normal state (controller offline, critical issue, equipment in maintenance). Readiness is decided by the backend. Never cancels.

## Triggers
- webhook: `"smartlab-booking-confirmed"`

## Flow
```mermaid
flowchart LR
  n0["Booking Confirmed Event<br/><small>webhook</small>"]
  n1["Get Booking Readiness<br/><small>httpRequest</small>"]
  n2["Lab Needs Heads-up?<br/><small>if</small>"]
  n3["Send Briefing To Student<br/><small>httpRequest</small>"]
  n4["Record Run<br/><small>httpRequest</small>"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
```

## Endpoints called (host redacted)
- `GET =<host>/api/automation/bookings/{{ $json.body.object.id }}` - Get Booking Readiness
- `POST <host>/api/automation/notify` - Send Briefing To Student
- `POST <host>/api/automation/runs` - Record Run

## Changes data
Yes - uses POST/PUT/PATCH/DELETE

## Credentials (references only, never values)
- httpHeaderAuth:Smart Lab automation key
- httpHeaderAuth:Smart Lab webhook token

## External services
- none found: all calls go to the local backend

## Related
- [[Bookings and labs]] (system)
- [[backend_app_api_routes_automation.py]] (code it calls)
- [[n8n automation]] (system)

Back to [[Home]] · [[Workflow catalogue]]
