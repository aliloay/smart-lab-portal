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
