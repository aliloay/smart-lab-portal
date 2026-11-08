---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/reports/evidence_20261017_124648.md"
source_hash: "61c5d22165be048e7e63183592dbe966a44c6874a8813f9d3b2aaed38aba6a07"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/reports/evidence_20261017_124648.md` - edit the original in the repository, not this note.

Systems: none

# Smart Lab evidence run 2026-10-17T12:46:48+00:00

Environment: {"base": "http://192.168.1.200", "started": "2026-10-17T12:46:48.938976+00:00", "host": "ALI", "runs": 20}

Summary: {'PASS': 32, 'FAIL': 12, 'NOT_AVAILABLE': 9, 'SIMULATION': 2}

Evidence classes: REAL_HARDWARE (observed from a device now), LIVE_SYSTEM (running software), OFFLINE (historical rows), SIMULATION (never physical validation).

| Area | Check | Procedure | Expected | Observed | Result | Evidence |
|---|---|---|---|---|---|---|
| API | health | GET /api/health | HTTP 200 | HTTP 200 in 42 ms | PASS | LIVE_SYSTEM |
| Security | admin sign-in | POST /auth/login | token | token received | PASS | LIVE_SYSTEM |
| Security | anonymous refused | GET /incidents without a token | 401 | HTTP 401 | PASS | LIVE_SYSTEM |
| Performance | /summary | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 35 ms, p95 47 ms | PASS | LIVE_SYSTEM |
| Performance | /labs/overview | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 24 ms, p95 38 ms | PASS | LIVE_SYSTEM |
| Performance | /devices | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 24 ms, p95 44 ms | PASS | LIVE_SYSTEM |
| Performance | /system/status | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 27 ms, p95 45 ms | PASS | LIVE_SYSTEM |
| Performance | /system/health | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 35 ms, p95 54 ms | PASS | LIVE_SYSTEM |
| Performance | /alerts?open_only=true | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 27 ms, p95 47 ms | PASS | LIVE_SYSTEM |
| Performance | /incidents?state=ACTIVE | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 32 ms, p95 52 ms | PASS | LIVE_SYSTEM |
| Performance | /reports-center/alerts?days=7 | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 33 ms, p95 40 ms | PASS | LIVE_SYSTEM |
| Performance | /analytics/system?days=7 | GET x20 (warm, laptop over LAN) | p95 < 500 ms | median 47 ms, p95 54 ms | PASS | LIVE_SYSTEM |
| Data freshness | environment | latest row of sensor_readings | live (recent for its cadence) | stale - last 2026-10-11T19:17:34.336720+00:00 (21892 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | door | latest row of access_events | live (recent for its cadence) | stale - last 2026-10-16T00:25:21.246360+00:00 (1305 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | robots | latest row of robot_events | live (recent for its cadence) | stale - last 2026-10-14T15:26:08.717312+00:00 (8629 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | consumables | latest row of inventory_measurements | live (recent for its cadence) | stale - last 2026-10-12T23:51:19.930628+00:00 (4926 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | inventory | latest row of inventory_transactions | live (recent for its cadence) | stale - last 2026-10-12T22:45:51.772237+00:00 (63 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | cameras | latest row of security_events | live (recent for its cadence) | stale - last 2026-10-15T23:49:15.577769+00:00 (652 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | pcs | latest row of equipment_sessions | live (recent for its cadence) | live - last 2026-10-15T12:20:23.107002+00:00 (40 rows) | PASS | REAL_HARDWARE |
| Data freshness | automation | latest row of integration_events | live (recent for its cadence) | stale - last 2026-10-16T00:25:21.248497+00:00 (841 rows) | NOT_AVAILABLE | OFFLINE |
| Data freshness | alerts | latest row of alerts | live (recent for its cadence) | live - last 2026-10-16T00:25:21.230434+00:00 (374 rows) | PASS | REAL_HARDWARE |
| Health | PostgreSQL | background probe / heartbeat | ONLINE | ONLINE - query answered | PASS | LIVE_SYSTEM |
| Health | Backend API | background probe / heartbeat | ONLINE | ONLINE - answering this request | PASS | LIVE_SYSTEM |
| Health | Live stream | background probe / heartbeat | ONLINE | UNKNOWN - 0 browser(s) connected | NOT_AVAILABLE | LIVE_SYSTEM |
| Health | Face server | background probe / heartbeat | ONLINE | ONLINE - HTTP 200 | PASS | LIVE_SYSTEM |
| Health | AI (local model, Ollama) | background probe / heartbeat | ONLINE | ONLINE - HTTP 200 | PASS | LIVE_SYSTEM |
| Health | Automation (n8n) | background probe / heartbeat | ONLINE | ONLINE - HTTP 200 | PASS | LIVE_SYSTEM |
| Health | Project knowledge service | background probe / heartbeat | ONLINE | ONLINE - HTTP 200 | PASS | LIVE_SYSTEM |
| Health | Door camera (ESP32-CAM) | background probe / heartbeat | ONLINE | OFFLINE - ConnectTimeout | FAIL | LIVE_SYSTEM |
| Health | Entry Camera (ESP32-CAM) (CAM_LAB01) | background probe / heartbeat | ONLINE | UNKNOWN - has never reported | FAIL | REAL_HARDWARE |
| Health | Door Controller (Master ESP32) (MASTER_LAB01) | background probe / heartbeat | ONLINE | OFFLINE - last report 2026-10-12T23:51:13.773208+00:00 | FAIL | REAL_HARDWARE |
| Health | FANUC ER-4iA (physical) (FANUC_01) | background probe / heartbeat | ONLINE | DEGRADED - collector running, but no joint data from the controller | FAIL | REAL_HARDWARE |
| Health | UR5e (physical) (UR5E_01) | background probe / heartbeat | ONLINE | DEGRADED - collector running, but no joint data from the controller | FAIL | REAL_HARDWARE |
| Health | Security camera (SECCAM_LAB02) | background probe / heartbeat | ONLINE | ONLINE - last report 2026-10-17T12:46:54.449812+00:00 | PASS | REAL_HARDWARE |
| Health | Security camera (SECCAM_LAB01) | background probe / heartbeat | ONLINE | DEGRADED - camera service running, but no picture from the camera | FAIL | REAL_HARDWARE |
| Health | BIN_NODE_1 (BIN_NODE_1) | background probe / heartbeat | ONLINE | OFFLINE - last report 2026-10-12T23:51:19.930628+00:00 | FAIL | REAL_HARDWARE |
| Health | Environment node (ENV_LAB01) | background probe / heartbeat | ONLINE | OFFLINE - last report 2026-10-11T19:17:34.336720+00:00 | FAIL | REAL_HARDWARE |
| Health | REUSE_BIN_1 (REUSE_BIN_1) | background probe / heartbeat | ONLINE | OFFLINE - last report 2026-10-12T23:51:04.276434+00:00 | FAIL | REAL_HARDWARE |
| Cameras | SECCAM_LAB01 | GET :5100/health | camera picture with fps > 0 | camera=False fps=0.0 analysis_age=None s, errors=0 | FAIL | LIVE_SYSTEM |
| Cameras | SECCAM_LAB02 | GET :5101/health | camera picture with fps > 0 | camera=True fps=7.0 analysis_age=0.0 s, errors=0 | PASS | REAL_HARDWARE |
| Robots | UR5E_SIM | GET /robots (collector telemetry) | fresh joint values | state=OFFLINE joints=yes stale=None | SIMULATION | SIMULATION |
| Robots | UR5E_SIM master control | GET control (UR5e) | mode dry_run until sign-off; truthful phase | mode=dry_run phase=BLOCKED (no fresh telemetry - robot state unknown) | PASS | LIVE_SYSTEM |
| Robots | FANUC_SIM | GET /robots (collector telemetry) | fresh joint values | state=OFFLINE joints=yes stale=None | SIMULATION | SIMULATION |
| Robots | UR5E_01 | GET /robots (collector telemetry) | fresh joint values | state=TELEMETRY_STALE joints=no stale=None | FAIL | REAL_HARDWARE |
| Robots | UR5E_01 master control | GET control (UR5e) | mode dry_run until sign-off; truthful phase | mode=dry_run phase=BLOCKED (no fresh telemetry - robot state unknown) | PASS | LIVE_SYSTEM |
| Robots | FANUC_01 | GET /robots (collector telemetry) | fresh joint values | state=IDLE joints=no stale=None | FAIL | REAL_HARDWARE |
| PCs | enrolled PC agents | GET /equipment (kind PC) | >= 1 pilot PC reporting | 0 PC(s); online: 0 | NOT_AVAILABLE | REAL_HARDWARE |
| Reports | source traceability | GET /reports-center/access | names its source table and warns on stale data | source=access_events, rows=1305, warnings=1 | PASS | OFFLINE |
| Incidents | open incidents | GET /incidents?state=ACTIVE | listed with counts and escalation flags | {'OPEN': 68, 'ACKNOWLEDGED': 0, 'INVESTIGATING': 0, 'RESOLVED': 0} escalations=63 | PASS | LIVE_SYSTEM |
| AI | which labs are free now | POST /ai/ask (lab data) | answer contains ['Free']; < 3 s | HTTP 200 in 57 ms via ['instant:free_labs'] | PASS | LIVE_SYSTEM |
| AI | what is the UR5e home position | POST /ai/ask (project knowledge) | answer contains ['ROBOT_CONTROL.md']; < 3 s | HTTP 200 in 108 ms via ['instant:knowledge_lookup'] | PASS | LIVE_SYSTEM |
| AI | how does the global STOP work for the UR5e | POST /ai/ask (project knowledge) | answer contains ['STOP']; < 3 s | HTTP 200 in 129 ms via ['instant:knowledge_lookup'] | PASS | LIVE_SYSTEM |
| AI | how does the door controller decide to open the door | POST /ai/ask (project knowledge) | answer contains ['ACCESS', 'door']; < 3 s | HTTP 200 in 158 ms via ['instant:knowledge_lookup'] | PASS | LIVE_SYSTEM |
| AI | what is offline | POST /ai/ask (lab data) | answer contains ['Offline']; < 3 s | HTTP 200 in 53 ms via ['instant:offline'] | PASS | LIVE_SYSTEM |
| Backups | automatic dump | backups/backup_status.json via /system/health | state OK (recent, readable) | state=OK last_success=2026-10-17T10:36:00+00:00 file=auto_smartlab_20261017_1336.dump (1024 KB) | PASS | LIVE_SYSTEM |

