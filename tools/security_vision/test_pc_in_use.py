"""PC 'in use' = someone SITTING at it, not standing in front (lab 2026-10-14, PC-11).
Boxes are the real ones from the lab screenshot, scaled to a 960x540 frame."""
import numpy as np

import vision

W, H = 960, 540
PC = {"id": 11, "name": "PC-11", "x": 0.55, "y": 0.55, "w": 0.08, "h": 0.06}
ROBOT = {"id": 20, "name": "UR5e", "x": 0.55, "y": 0.45, "w": 0.06, "h": 0.12, "alert_on_motion": False}


def norm(x, y, w, h):
    return (x / W, y / H, w / W, h / H)


STANDING = norm(530, 290, 30, 87)     # 60x175 at 1920 -> h/w 2.9
SEATED = norm(520, 300, 38, 69)       # 77x138 at 1920 -> h/w 1.8


def run(zone, person, seconds=7.0):
    zw, gray, st = vision.ZoneWatcher(), np.full((H, W), 120, np.uint8), None
    t = 0.0
    while t <= seconds:
        for s in zw.update([zone], gray, [person], t):
            st = s.status
        t += 0.2
    return st


def test_seated_person_at_a_pc_is_in_use():
    assert run(PC, SEATED) == "IN_USE"


def test_standing_person_in_front_of_a_pc_is_not_in_use():
    assert run(PC, STANDING) != "IN_USE"


def test_standing_at_a_robot_still_counts():
    assert run(ROBOT, STANDING) == "IN_USE"
