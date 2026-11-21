# Robots and digital twins audit

## Live state (19:11 local)

| Device | Source | DB state | last_seen (UTC) | Age | Displayed as |
|---|---|---|---|---|---|
| UR5E_01 "UR5e (physical)" | robot-collector-0.2 (ur), RTDE receive | `state: IDLE`, robot_mode null, fusion OFFLINE | 2026-11-18 16:39:31 | 3 days | OFFLINE: older than 90 s (backend) and older than 30 s (frontend `effective()`) |
| FANUC_01 "FANUC ER-4iA (physical)" | robot-collector-0.2 (fanuc), HTTP GET /MD/CURPOS.DG | `state: UNKNOWN`, q null | 2026-11-18 16:39:46 | 3 days | OFFLINE |
| UR5E_SIM / FANUC_SIM | simulation | MOVING (stored) | 2026-10-08 | 44 days | retired from watch alerts (B-07); OFFLINE |

- **Collectors:** both are running at home (pids 24256 / 30480). They retry 192.168.1.102 and .100, and both IPs are unreachable (ping 100 % loss).
- **No false online state:** `robot_collector.py:281-290` reports `TELEMETRY_STALE` once and then lets `last_seen` expire. Reconnect backoff is 2–3 s (`:332-364`).
- **Answer:** the twins are **not** showing current telemetry. The last real data is from 18 Nov. Calling this "connected" would be wrong.
- **Historical evidence (not re-verified):**
  - UR5e RTDE 48 Hz live-verified on 12–18 Oct, with a cable-pull stale test of 2.0 s.
  - FANUC read-only live-verified on 14 Oct (about 3 samples/s).
  - Source: `docs/PROGRESS_CHECKPOINT.md:475-488`, `docs/FANUC_LIVE_TWIN.md`.

## Control is UNAVAILABLE (LIVE-VERIFIED + VERIFIED FROM CODE)

- The live backend has `ROBOT_CONTROL=off` (`docker compose exec backend printenv`). The compose default is also `off` (`docker-compose.yml:165`).
- `services/robot_control.py`:
  - The base `Adapter.execute` returns UNAVAILABLE.
  - `FanucAdapter` has a monitoring-only blocker.
  - `URAdapter` returns UNAVAILABLE unless MODE is `dry_run` or `live`. `live` needs the UR agent in the same mode, plus Dashboard `load`/`play` replies.
  - `controller_mode()` defaults to UNKNOWN.
- Ownership, an allowlist, idempotent command IDs and an audit trail are implemented.
- The collectors use RTDE *receive* and an HTTP GET only, so they are read-only.
- **OPC UA** (`tools/opcua/opcua_server.py`, running): it serves the backend `/api/opcua/snapshot`, which is read-only. I saw no write nodes in the snapshot route. **I did not perform any OPC UA write.**

## UNKNOWN and stale handling

- **Backend (`devices.py:_derived_state`):** a non-simulation robot that is ONLINE but has no `q` and no `robot_mode` becomes DEGRADED, "collector running, robot not connected".
- **Frontend (`components/robot/robotLive.tsx:13-23`):** STALE after 3 s for MOVING/STATIONARY, OFFLINE after 30 s. Twins draw live joints only when `!stale && q.length == 6` (`RobotTwinPanel.tsx:246`).
- **Gap:** UNKNOWN or IDLE states younger than 30 s are not marked stale, but OFFLINE takes over at 30 s. This is acceptable.
- **Timestamps:** stored as `timestamptz` (UTC); the UI computes the age from `last_seen_at`.

## Network mapping

| Address | Holder (source) | Conflict |
|---|---|---|
| 192.168.1.100 | FANUC controller (FANUC_LIVE_TWIN.md, collector args) **and** Hemaly PC_ENG (reported IPs on 18 Nov) | **YES (F-03)** |
| 192.168.1.101 | UR External Control host / ROS laptop (LAB_TEST_2026-10-15.md:41) | check that Hemaly's PC is not .101 |
| 192.168.1.102 | UR5e pendant static (LAB_TEST_2026-10-15.md:170) | none known |
| 192.168.1.103 | mentioned as part of Hemaly's PC range .100–.103 (checkpoint 19 Nov) | potential |

## Simulation versus real

- The SIM devices are clearly named "(simulation)" and excluded from watch alerts.
- The physical devices carry `source` (FANUC_WEB) and a `robot-collector-0.2 (ur|fanuc)` firmware tag.

## Actions at GIU

See OWNER_ACTIONS_AND_HARDWARE_TEST_PLAN.md:

1. Fix Hemaly's IP.
2. Power on the controllers (operator present).
3. Ping .100 and .102.
4. Start the collectors.
5. Confirm both twins move with the pendant (read-only).
6. Record `last_seen` and sample rates.
