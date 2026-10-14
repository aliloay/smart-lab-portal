# Robot control (Home / approved routines / software stop)

Status 2026-10-14: **ownership, checks, audit and UI are implemented and tested with mocked adapters.
Every real adapter answers UNAVAILABLE. Nothing can reach a robot controller from the portal.**

| | UR5e (192.168.1.102) | FANUC ER-4iA (192.168.1.100, R-30iB Mate Plus, HandlingTool V9.30) |
|---|---|---|
| Today | RTDE **receive** (monitoring) | HTTP GET `/MD/CURPOS.DG` (monitoring) |
| Commands | UNAVAILABLE | UNAVAILABLE |
| Controller mode read | not yet (reported UNKNOWN, blocks all) | not yet (UNKNOWN, blocks all) |

## What the server enforces (`backend/app/services/robot_control.py`, `/api/robots/{id}/control*`)

- Staff only. One portal owner per robot; 5 min expiry; explicit release; only an admin can force a release.
  Ownership lives in memory, so a backend restart clears it (never a stale owner).
- Commands: `home`, `routine` (allowlist per robot, empty today), `stop`. Movements need `confirmed: true`.
- Each needs: ownership, telemetry < 2 s old, controller mode `REMOTE_READY` read from the controller.
- `command_id` de-duplication: a repeated id is answered `DUPLICATE`, never executed twice.
- Every request is audited (`ROBOT_CONTROL_REQUEST/RELEASE`, `ROBOT_COMMAND` with result).
- Result states: `REJECTED`, `UNAVAILABLE`, `REQUESTED`, `DUPLICATE`. `REQUESTED` never means "moved" or
  "stopped": only measured telemetry shows that. The twin is driven by telemetry only.
- The portal lock does **not** stop the teach pendant. The software stop is **not** an emergency stop.

## Commissioning (authorized robotics operator, robot in a safe state, one step at a time)

### UR5e
1. On the pendant decide whether Remote Control is allowed in this lab (Settings > System > Remote Control).
   The portal never switches the mode.
2. Write and validate on the pendant, at reduced speed, the programs: `home.urp` and each approved routine.
   Positions and speeds come from the operator, never from the portal.
3. Implement `URAdapter` with the Dashboard Server (port 29999): read `is in remote control`, `robotmode`,
   `safetymode` -> `controller_mode()`; `load home.urp` + `play` for Home; `stop`/`pause` for the software stop.
4. Test with the robot in Local mode first (must be refused), then Remote with the operator at the pendant.

### FANUC
1. Confirm which licensed remote option the controller has (e.g. PC/remote program start, Socket Messaging,
   or UOP/PNS signals). Do not use undocumented web endpoints. The `/MD/CURPOS.DG` collector stays read-only.
2. Write and validate TP programs (`HOME`, approved routines) on the pendant at reduced speed.
3. Implement `FanucAdapter` on that verified interface: read TP enable / remote / ready -> `controller_mode()`.
4. Same staged tests as the UR5e. J2/J3 coupling stays twin-only (`Collector.twin_q`).

Until each step is signed off, leave the adapter returning UNAVAILABLE.
