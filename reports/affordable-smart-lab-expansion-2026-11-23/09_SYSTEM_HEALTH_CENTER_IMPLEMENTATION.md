# Health Center (`/admin/health`, staff)
Limitation before: states, causes, coverage and events were on different pages.
Source: `frontend/src/pages/HealthCenter.tsx`; data from the existing `/api/system/health` and the new `/api/metrics/*`.

- **Now:** problems first, search, "Needs attention" / "Everything", what to check. Unknown is not called healthy; a failed refresh says so.
- **Why?** drawer per device: what happened, possible causes with confidence and evidence, missing evidence, checks, earlier alerts.
- **Data coverage:** hours with a stored reading. Labelled as coverage, not uptime.
- **Timeline:** alerts, robot, maintenance, PC, door and automation events; no people.

It has no restart, reset or switch button. Limits: a cause is correlation; packet loss and voltage are not recorded; signal only after the firmware.
Tests: `test_metrics.py`, `e2e/expansion.mjs`. Picture: `graphics/health_center.png`, `graphics/health_diagnosis.png` (test copy).
Rollback: remove the route and menu entry; no data changes. Deployment: none.
