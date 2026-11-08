---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/robot_monitor/test_fanuc_joints.py"
source_hash: "a08f78a53c3bcb066ffc6d6463dbe62163a9ef9f1228525a7a371d6b851bea57"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/robot_monitor/test_fanuc_joints.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[tools_robot_monitor_fanuc_joints.py]] - tests

```py
import math

from fanuc_joints import fanuc_to_urdf, urdf_to_fanuc


def test_j3_is_measured_from_the_upper_arm_in_the_model():
    q = fanuc_to_urdf([0, 30, -10, 0, -90, 0])
    assert abs(q[2] - math.radians(20)) < 1e-9          # J3 + J2
    assert abs(q[4] - math.radians(-90)) < 1e-9


def test_round_trip_and_uncoupled():
    j = [12.5, -20.0, 35.0, 90.0, -45.0, 180.0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(urdf_to_fanuc(fanuc_to_urdf(j)), j))
    assert abs(fanuc_to_urdf(j, j23_coupled=False)[2] - math.radians(35.0)) < 1e-9

```
