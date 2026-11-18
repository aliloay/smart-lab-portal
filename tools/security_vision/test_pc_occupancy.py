"""Which PC a seated person is at (2026-10-21 lab: sitting at PC-07 showed 'PC-08 in use' on both cameras -
the body covers the next monitor box). Seat areas and the PCs' power (LAN) decide. SIMULATED geometry."""
from seat_capture import pick
from vision import ZoneWatcher

FW, FH = 1000, 1000
# two monitors side by side; the person sits at PC-07 but the body covers PC-08's box
PC07 = {"id": 7, "name": "PC-07", "x": 0.40, "y": 0.40, "w": 0.04, "h": 0.04}
PC08 = {"id": 8, "name": "PC-08", "x": 0.46, "y": 0.40, "w": 0.04, "h": 0.04}
SEATED = (0.455, 0.38, 0.06, 0.08)            # covers PC-08's box only, 1.3x taller than wide
STANDING = (0.455, 0.30, 0.03, 0.20)


def occ(zones, people):
    return ZoneWatcher().pc_occupancy(zones, people, FW, FH)


def test_without_power_or_seats_nothing_changes():
    assert occ([PC07, PC08], [SEATED]) == {7: False, 8: True}
    assert occ([PC07, PC08], [STANDING]) == {7: False, 8: False}


def test_the_pc_that_is_on_beside_the_person_wins_over_a_covered_pc_that_is_off():
    zones = [{**PC07, "pc_on": True}, {**PC08, "pc_on": False}]
    assert occ(zones, [SEATED]) == {7: True, 8: False}


def test_covering_an_on_and_an_off_pc_means_the_one_that_is_on():
    wide = (0.40, 0.38, 0.11, 0.09)           # covers both boxes
    zones = [{**PC07, "pc_on": False}, {**PC08, "pc_on": True}]
    assert occ(zones, [wide]) == {7: False, 8: True}


def test_unknown_power_or_both_on_keeps_the_covered_box():
    assert occ([{**PC07, "pc_on": None}, {**PC08, "pc_on": False}], [SEATED]) == {7: False, 8: True}
    assert occ([{**PC07, "pc_on": True}, {**PC08, "pc_on": True}], [SEATED]) == {7: False, 8: True}


def test_a_recorded_seat_decides_and_its_person_does_not_count_for_the_neighbour():
    zones = [{**PC07, "seat": list(SEATED)}, PC08]
    assert occ(zones, [SEATED]) == {7: True, 8: False}
    assert occ(zones, [(0.10, 0.10, 0.05, 0.07)]) == {7: False, 8: False}   # someone elsewhere


def test_seat_capture_picks_the_seated_person_nearest_the_monitor():
    state = {"frame": [1000, 1000], "zones": [{"name": "PC-07", "box": [0.40, 0.40, 0.04, 0.04]}],
             "tracks": [{"box": [455, 380, 60, 80]}, {"box": [455, 300, 30, 200]}, {"box": [900, 900, 60, 80]}]}
    box, why = pick(state, "PC-07")
    assert why == "" and [round(v, 3) for v in box] == [0.455, 0.38, 0.06, 0.08]
    assert pick(state, "PC-99")[0] is None


def test_one_seated_person_is_at_one_seat_even_when_far_seats_overlap():
    # 2026-11-18 lab: camera 1, PC-13/14/15 seats recorded far away overlap; one person showed all three in use
    from vision import ZoneWatcher
    zw = ZoneWatcher()
    zones = [{"id": i, "name": n, "x": 0.3, "y": 0.45, "w": 0.02, "h": 0.03, "seat": s}
             for i, n, s in ((13, "PC-13", (0.341, 0.508, 0.050, 0.128)), (14, "PC-14", (0.316, 0.499, 0.047, 0.149)),
                             (15, "PC-15", (0.299, 0.487, 0.051, 0.151)))]
    occ = zw.pc_occupancy(zones, [(0.300, 0.490, 0.052, 0.150)], 960, 540)
    assert occ == {13: False, 14: False, 15: True}


def test_a_robot_with_recorded_spots_is_in_use_only_by_someone_at_a_spot():
    # 2026-11-18 lab: a person right in front of camera 2 overlapped the UR5e area -> "UR5e in use"
    import numpy as np
    from vision import ZoneWatcher
    zw = ZoneWatcher()
    z = {"id": 1, "name": "UR5e", "x": 0.143, "y": 0.311, "w": 0.044, "h": 0.209, "alert_on_motion": False,
         "seat": (0.308, 0.3955, 0.0568, 0.234), "spots": [(0.308, 0.3955, 0.0568, 0.234), (0.133, 0.3376, 0.0877, 0.3844)]}
    gray = np.zeros((540, 960), np.uint8)
    near_camera = (0.0, 0.58, 0.13, 0.42)
    for t in range(0, 12):
        st = zw.update([z], gray, [near_camera], 100.0 + t)
    assert st[0].status != "IN_USE"
    zw2 = ZoneWatcher()
    for t in range(0, 12):
        st = zw2.update([z], gray, [(0.31, 0.40, 0.057, 0.23)], 100.0 + t)
    assert st[0].status == "IN_USE"
