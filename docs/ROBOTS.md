# Robot monitoring (read-only)

```
robot ──read-only──► tools/robot_monitor/robot_collector.py ──HTTP──► backend /api/robots/*
                       RobotMotion at ~50 Hz                     events, HOME, fusion, WebSocket
camera ─► tools/security_vision (robotvision.py: flow in the robot's box) ─► camera state ─┘
```

**Nothing sends commands.**
- The UR source uses `ur_rtde`'s *receive* interface only.
- No FANUC protocol is implemented until the controller is inspected.
- The backend has no endpoint that talks to a controller; a test enforces this.

## Motion (tools/robot_monitor/robot_state.py)

**Per joint**, a joint starts moving when either:
- its velocity is above 0.02 rad/s; or
- it is more than 0.002 rad away from where it last stood still.

It counts as stopped when its velocity is below 0.005 rad/s and its position
changes by no more than 0.0005 rad for 0.5 s (hysteresis, so no flicker).

**Events:**
- `MOVEMENT_STARTED` (lists which joints) and `MOVEMENT_STOPPED`;
- `JOINT_MOVED` (from, to, delta in rad and degrees, peak velocity, duration). One joint moving is enough, even if the tool tip barely moves.
- `TELEMETRY_STALE` after 2 s without a sample. This is never shown as "stationary".
- `TELEMETRY_RESTORED`.

None of these thresholds is tuned on the real robots yet.

## HOME (versioned)

An administrator presses "Calibrate HOME" while the robot stands still.
- The current joints become HOME version N; older versions are kept.
- State: HOME when every joint is within the tolerance (default ±1°), NEAR_HOME within 5×, otherwise NOT_HOME.
- MOVING always takes precedence on screen.
- The portal records `HOME_LEFT` / `HOME_RETURNED`.

## Telemetry + camera fusion (backend/app/services/robot_fusion.py)

| Telemetry | Camera (robot's box) | Result |
|---|---|---|
| moving | motion seen | MOVEMENT_VERIFIED |
| moving | person in front | VISUALLY_OCCLUDED |
| moving | nothing seen | MOVEMENT_TELEMETRY_ONLY → event after 3 s |
| still | still | STATIONARY_VERIFIED |
| still | motion seen | VISUAL_ANOMALY → `VISUAL_TELEMETRY_DISAGREEMENT` (WARNING) after 3 s |
| stale / offline | motion seen | VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE (WARNING) |
| simulation | - | SIMULATION (never compared with the real camera) |

Every decision is stored with its evidence (telemetry, camera, kinematics).

**Kinematic check: NOT CALIBRATED.** The check of direction and size of
movement needs the camera-to-robot calibration (robot base and reference points
picked in the picture while the robot moves known joints). Until then,
agreement means motion against no motion only, and the evidence says so.

## Event severity (movement started)

- **NOTICE:** a booking is in force.
- **WARNING:** no booking, but someone entered at the door.
- **CRITICAL:** no booking and nobody entered.

Simulation data is always INFO and stored with provenance DEMO_DATA. The
context saved with each event (booking, who was inside according to the door,
what the camera saw at the robot's box) is evidence for a likely actor. It is
never a claim of who moved the robot.

## 3D twins (frontend/src/components/robot)

- **UR5e:** Universal Robots' published DH parameters (links drawn as cylinders).
- **FANUC:** PLACEHOLDER geometry (generic 6-axis arm) until the arm model is
  known. Change `MODELS.FANUC.dh` in `kinematics.ts` to the real model's DH
  parameters.
- **Another robot:** add an entry to `MODELS`.

## Simulation (development only)

    cd tools\robot_monitor
    py robot_collector.py --source sim --device UR5E_SIM --name "UR5e (simulation)" --model UR5e
    py robot_collector.py --source sim --device FANUC_SIM --name "FANUC (simulation)" --model FANUC

These are shown everywhere as **DEMO DATA**. Stop them (Ctrl+C) when not
needed: each robot writes a few events per 24-second cycle.
