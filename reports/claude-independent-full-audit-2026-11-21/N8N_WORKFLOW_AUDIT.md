# n8n workflow audit

## Live service (read-only)

- **Container:** `n8nio/n8n:2.40.7`, healthy, `127.0.0.1:5678`. `GET /healthz` returns `{"status":"ok"}` (200).
- **Workflow state:** the n8n-lab MCP (read-only) **failed to connect (ECONNREFUSED)**, so live workflow activation states and the execution list could not be read. **"26/26 active" is UNVERIFIED** in this audit.
- **Indirect live evidence:** the backend records every run that posts to `/api/automation/runs` as `audit_logs.action='AUTOMATION_RUN'`. Last 7 days:

| Workflow | Runs (7 days) | Last run (UTC) | Failures |
|---|---|---|---|
| 01-booking-confirmation | 2 | 11-21 11:14 | 0 |
| 03-access-denial-intelligence | 5 | 11-20 19:45 | 0 |
| 04-device-offline-escalation | 570 | 11-21 17:21 | 0 |
| 05-maintenance-automation | 1 | **11-18** 06:00 | 0 |
| 08-sensor-thresholds | 1 | 11-17 13:00 | 0 |
| 10-post-session | 3 | 11-21 12:30 | 0 |
| 11-data-quality | 1 | **11-18** 04:00 | 0 |
| 12-anomaly-detection | 37 | 11-21 17:00 | 0 |
| 13-environment-hazard-escalation | 52 | 11-21 14:27 | 0 |
| 14-node-offline | 111 | 11-21 11:45 | 0 |
| 16-unattended-stock-change | 13 | 11-21 17:00 | 0 |
| 18-robot-offline-fault | 511 | 11-21 17:18 | 0 |
| 19-robot-without-booking | 23 | 11-17 13:30 | 0 |
| 20-pc-offline | 173 | 11-21 17:15 | 0 |
| 22-robotics-daily | 1 | **11-18** 05:00 | 0 |

- **Not seen in 7 days:** 02, 06, 07, 09, 15, 17, 21, 23 and the 3 knowledge workflows.
- Some of these may post runs only when they have findings, or may not log runs at all (the knowledge jobs post to :5199, not to `/runs`). So "not seen" is not proof of failure.
- **Daily jobs at 04:00–06:00 last ran on 18 Nov.** This is consistent with the laptop sleeping at those hours. n8n does not catch up missed schedule triggers.
- **Delivery side (`integration_events`):**
  - `device.offline` 248 DELIVERED, 4 FAILED (18 Nov 21:19).
  - `access.denied` 37 DELIVERED.
  - `booking.confirmed` 3 DELIVERED.
  - Most other event types are SKIPPED (no subscriber, by design).

## Static review of the repo copies (`automation/n8n/json/*.json` + `json/knowledge/*.json`, 26 files)

Script: `scratchpad/n8n_audit.py`.

| Check | Result |
|---|---|
| JSON parses, connections reference existing nodes | 26/26 OK; no dangling or unconnected nodes |
| Triggers | 3 webhook-only (01, 03, 23), 2 webhook + schedule (04, 05), 18 schedule, 3 schedule + manual (knowledge) |
| Credentials (by name) | "Smart Lab automation key", "Smart Lab webhook token", "KB service token (local)"; no inline secrets |
| `errorWorkflow` setting | **none in any workflow** |
| HTTP node timeout set | knowledge 3/3 yes; **01–23: 0** (n8n default applies) |
| `retryOnFail` on HTTP nodes | most schedule flows retry 1 of 3 (the data read); **01, 03, 23 (emergency) and the knowledge flows: 0** |
| `onError` continue branches | present in 18 flows (1 node each) |
| Repo copy `active` flag | 01–23 exported as `false`; knowledge `true`. Exports do not reflect the live state |
| Backend dependencies | all point to `http://backend:8000/api/automation/*` or `host.docker.internal:5199/jobs/*` |
| Backup | `D:\SmartLabData\n8n_backup_20261118` has `draft/` (26) and `published/` (26) JSON files; all 52 parse. Import into n8n was not tested |

## Knowledge 1–3

- **Workflows:** source sync (`/jobs/build`), vault health (`/jobs/drift` + `/jobs/health`), weekly summary (`/jobs/digest`).
- **Error visibility:** the knowledge service answers **HTTP 500** when a job step fails (`serve.py:138`), so n8n marks the execution failed. Without an error workflow, nobody is alerted.
- **Content accuracy:** the jobs rebuild and report. They do not validate facts. The drift job compares the live export against the docs. The recursive mirror problem (OBSIDIAN review, F-07) is not detected by them.

## Duplicate alerts

- 04 runs every 5 min and reports "Offline devices: 17" at home. Backend notifications are deduplicated (`uq_notification_dedupe`). Still, 541 notifications were created today, mainly by the bin calibration.

## Recommendations (repo copies only; importing them live is an owner action)

1. One "Error handler" workflow (Error Trigger → POST `/api/automation/runs` with status=error → notify admin), set as `errorWorkflow` on all 26.
2. Explicit HTTP timeouts (10–30 s) on 01–23.
3. Retry 2× on the HTTP nodes of webhook flows 01, 03 and 23.
4. Move daily schedules to hours when the laptop is on, or add a "missed run" check in the backend daily summary.
5. Re-export after any live change. Verify the backup with `n8n import:workflow --input` into a throwaway container (not done here).
