# Occupancy history (design only, not enabled)
Purpose: room use per hour. Not a person list, not attendance, no inference about any person.

| Control | Rule |
|---|---|
| Input | PIR zone state and the existing anonymous camera count; never face, name or card |
| Stored | hour, zone, active minutes, count as 0 / 1-2 / 3-5 / 6+ |
| Small numbers | public views show only "in use / free" |
| Retention proposal | hourly 30 days, daily 12 months. This needs a deletion rule, and the owner rule is "never delete": **owner decision before any start** |
| Access | staff; students see only free/in use; no export with identity |
| Delay | history appears after the hour ends |
| Forbidden | joining with door events, gender/age/emotion, ranking people |
| Notice | sign in the lab and a line in the portal |
| Quality | PIR does not count; a camera gap is "unknown", not "empty" |

Prototype table (not created): `occupancy_hour(zone, hour, active_minutes, band, quality)`. Rollback: stop the job, drop the new table.
Motion is stored today as a 0/1 zone state without identity; the exhibition screen does not show it.
