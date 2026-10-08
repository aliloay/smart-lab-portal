"""
FANUC joint angles -> the angles the 3D model / URDF uses.

FANUC controllers (R-30iA/B families) report J3 relative to the HORIZONTAL
("J2/J3 interaction"), while the ROS-Industrial URDF - and therefore the twin
- expects J3 relative to the upper arm, i.e. J3_urdf = J3_fanuc + J2. The
ROS-Industrial fanuc_driver applies the same correction. Angles from the
pendant are in degrees; the portal uses radians.

To be CONFIRMED on the lab's controller (and its exact arm model) before the
FANUC source is enabled: compare the twin with the real arm at 2-3 poses.
"""
from __future__ import annotations

import math


def fanuc_to_urdf(j_deg: list[float], j23_coupled: bool = True) -> list[float]:
    """Six FANUC joint angles in degrees -> six URDF joint angles in radians."""
    q = [math.radians(v) for v in j_deg]
    if j23_coupled:
        q[2] = q[2] + q[1]
    return q


def urdf_to_fanuc(q_rad: list[float], j23_coupled: bool = True) -> list[float]:
    q = list(q_rad)
    if j23_coupled:
        q[2] = q[2] - q[1]
    return [math.degrees(v) for v in q]
