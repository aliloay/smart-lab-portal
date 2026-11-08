---
type: "source-mirror"
source_kind: "documentation"
source_path: "tools/ur5e_collector/README.md"
source_hash: "8d10eee5a0836e09c3b167f5b78c3debf375718f840de8364fd0320576534219"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/ur5e_collector/README.md` - edit the original in the repository, not this note.

Systems: none

# UR5e collector — read-only (Robotics Lab, Phase 5)

`ur5e_rtde_collector.py` reads the UR5e over **RTDE** (Universal Robots'
Real-Time Data Exchange, `ur_rtde` receive interface) and reports state to
the portal (`POST /api/equipment/state`). It **never** sends a command.

**Status:** written and syntax-checked; not yet run against this lab's
controller. Before relying on it, check the controller's software version
and confirm in its RTDE guide: `robot_mode`, `safety_mode`,
`runtime_state` (2 = playing), `actual_q`, `speed_scaling`.

```
pip install ur_rtde requests
set DEVICE_KEY=<the collector's key>        (Devices -> Issue own key, after its first report)
py ur5e_rtde_collector.py --robot 192.168.1.160 --device UR5E_01 --asset UR5E-01
```

State: FAULT if safety mode is not NORMAL/REDUCED, RUNNING while a program
plays, else IDLE. State every 5 s, numbers every 60 s. If the connection
drops it reports nothing (the portal marks the robot offline) and retries.

Measure (§X): update rate, state classification vs what the pendant shows,
fault detection, disconnect/reconnect, latency to the portal.

FANUC: no collector yet — identify the controller model, software version
and installed communication options first (§N).

