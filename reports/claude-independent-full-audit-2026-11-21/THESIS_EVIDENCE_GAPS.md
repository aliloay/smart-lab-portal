# Thesis evidence gaps

Each feature is listed under the strongest evidence that exists **today**. Evidence labels:

- **LIVE-VERIFIED:** observed directly during this audit.
- **TESTED – PASSED:** an automated test I ran passed.
- **VERIFIED FROM CODE:** I read the code that implements it.
- **HISTORICAL:** recorded earlier, not re-checked.
- **SIMULATED:** shown only with generated data.
- **UNVERIFIED:** no evidence found.

## Fully verified (live or tested in this audit)

| Feature | Evidence |
|---|---|
| Portal auth, RBAC, device keys, sign-up with approval, audit trail | 887 backend tests; code review (with one bug, F-01) |
| The five ESP32 nodes report to the portal (heartbeats, firmware versions match the source) | LIVE (DB ages < 30 s, ping 0 % loss) |
| Door controller component health (RFID, fingerprint, camera flags) | LIVE (component_state) |
| Consumables and reusable bins send measurements (about 1 Hz) and calibration state | LIVE (inventory_measurements, component_state); value correctness disputed (F-10) |
| Robot-control lockout (UNAVAILABLE) | LIVE (`ROBOT_CONTROL=off`) + code |
| Stale or offline display for robots and devices | code + DB state |
| Automated backups every 6 h with archive validation | LIVE (backup_status, TOC) |
| n8n automations running and recorded | LIVE (AUTOMATION_RUN rows, 0 failures in 7 days) |
| Knowledge retrieval with labelled citations; secret-question guard; answer cache | TESTED (measured) |
| Production frontend: lazy routes, about 227 KB gzip first load, CSP/HSTS | LIVE (measured) |
| Camera pipeline logic (tracking, naming rules, crosscam, seats, activity) | TESTED – 396 offline tests (logic only) |
| PC agent, relay and exam lockdown logic | TESTED (40 + 6) |

## Demonstrated only by historical recordings or reports

- Live camera tracking, cross-camera naming, seat/PC occupancy and equipment-moved alerts: cameras offline today.
- UR5e live twin (RTDE 48 Hz) and FANUC live twin: last data 18 Nov.
- The PC fleet with 10 machines, Hemaly's relay, screen wall, broadcast and exam mode: last heartbeats 18 Nov.
- AR detection accuracy (v8: 34/35 photos and similar figures): Colab and owner evaluation, not re-run.
- Door timing (under 10 ms after match, QR 161 ms, cold start 2.9 s): 21 Nov owner measurements.
- The 19 Oct GPU contention result (camera 7.0 → about 5 analyses/s), which justifies the camera-first gate.
- Assistant GPU latency of about 5 s (21 Nov benchmark). **Today it measures 11.7–18.4 s on the CPU.**
- The showcase films, 18–19 Nov.

## Claims with no evidence (do not state as results)

- Dead-zone recovery time on real people: only rules and simulation exist.
- Live ID-switch and false-name rates on real people (`scenario_bench` is simulated).
- **Full-body pose or keypoints:** not implemented. Body parts are box-geometry estimates.
- Phone AR end-to-end latency, frame rate and box stability.
- ESP32 Wi-Fi RSSI and reconnect statistics: not reported by the firmware.
- A successful **restore** from backup.
- Batched or stitched two-camera inference performance.
- "26/26 n8n workflows active" today: the live state was unreadable.

## Physical attendance at GIU required

- Cameras (live metrics and benchmark).
- Robots, including the .100 IP conflict with Hemaly's PC.
- Hemaly's PC and the relay; PC-10 agent update; PC-11 sticker check.
- AR on the robots and PCs.
- Assistant timing with the cameras live.
- Face re-enrolment for USER5/USER7.

## Home or owner tasks (not GIU)

- 1N4007 diode and buzzer.
- Physical re-tare of the consumables bin.
- Push the commits.
- Backup retention decision.
- Vault clean-up approval.
