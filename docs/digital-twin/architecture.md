# Digital twin: architecture

```mermaid
flowchart LR
  UR["UR5e controller"] -- "RTDE receive (read-only), 50 Hz" --> COL["robot_collector.py<br/>RobotMotion: events, HOME, stale logic"]
  FA["FANUC controller"] -- "HTTP GET /MD/CURPOS.DG (read-only)" --> COL
  CAM["Security vision<br/>robotvision.py (motion in the robot's box)"] --> API
  COL -- "POST /api/robots/telemetry every 0.2 s<br/>POST /api/robots/events" --> API["FastAPI robots routes"]
  API --> DB[("Device.component_state<br/>robot events, movements")]
  API -- "GET /api/robots/{id} (polled), /ws/activity" --> UI["Portal: RobotTwin (three.js / react-three-fiber)"]
```

| Part | File |
|---|---|
| Collector (UR and FANUC sources, motion detection, back-off when unreachable) | [`tools/robot_monitor/robot_collector.py`](../../tools/robot_monitor/robot_collector.py) |
| Backend routes: state, events, movements, control status | [`backend/app/api/routes/robots.py`](../../backend/app/api/routes/robots.py) |
| 3D twin and panel | [`frontend/src/components/robot/RobotTwin.tsx`](../../frontend/src/components/robot/RobotTwin.tsx), `RobotTwinPanel.tsx`, `robotLive.tsx` |
| Kinematics and joint limits | `frontend/src/components/robot/kinematics.ts` |
| Robot detail page | [`frontend/src/pages/RobotDetail.tsx`](../../frontend/src/pages/RobotDetail.tsx) |

Camera fusion: if the camera sees motion in the robot's box while telemetry is stale, the backend raises VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE.
