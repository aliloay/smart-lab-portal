# Digital twin: physical state mapping

| Physical quantity | Read from | Stored as | Shown in the twin |
|---|---|---|---|
| Joint angles q1-q6 | UR RTDE `getActualQ` (rad); FANUC page degrees → radians once (J3 += J2 coupling, to be confirmed on real poses) | `component_state.q` | Arm pose, per-joint bars against limits |
| TCP pose | RTDE actual TCP; FANUC page mm → m | `component_state` | Tool position readout |
| Robot mode, safety mode | RTDE receive | `component_state` | Mode and safety text ("not reported" when missing) |
| Motion | Collector's RobotMotion (change between samples) | robot events, movements | MOVING / STATIONARY / HOME, movement history |
| Freshness | Laptop receive time (FANUC has no controller timestamp) | sample time | Age; TELEMETRY_STALE after 2 s |
| Camera view | `robotvision.py` optical flow in the robot's box | camera state | Visual motion indicator, outage warning |

Sync: the collector samples at 50 Hz and reports the latest state every 0.2 s; the portal polls the state, so the twin lags the robot by roughly the report interval plus the poll interval. It is not a hard real-time mirror.
