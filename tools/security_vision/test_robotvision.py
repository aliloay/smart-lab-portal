"""
Visual robot motion (robotvision.py) on synthetic frames: an "arm" bar that
rotates inside its box, a light change, camera shake, a person in front.

    py -m pytest test_robotvision.py -q
"""
import math

import cv2
import numpy as np

from robotvision import RobotVisualMotion

BOX = [{"id": 7, "x": 0.25, "y": 0.2, "w": 0.5, "h": 0.6}]


def scene(angle_deg=0.0, light=1.0, shift=0):
    img = np.full((360, 640), 70, np.uint8)
    rng = np.random.default_rng(3)
    for _ in range(60):                                 # fixed texture (cage, wall)
        x, y = int(rng.integers(0, 620)), int(rng.integers(0, 340))
        cv2.rectangle(img, (x, y), (x + 15, y + 15), int(rng.integers(90, 200)), -1)
    cx, cy, L = 320, 250, 110
    a = math.radians(angle_deg)
    cv2.line(img, (cx, cy), (int(cx + L * math.cos(a)), int(cy - L * math.sin(a))), 235, 14)
    img = np.clip(img.astype(np.float32) * light, 0, 255).astype(np.uint8)
    if shift:
        img = cv2.warpAffine(img, np.float32([[1, 0, shift], [0, 1, 0]]), (640, 360), borderValue=70)
    return img


def run(frames, people=()):
    v = RobotVisualMotion()
    res = None
    for i, f in enumerate(frames):
        res = v.update(BOX, f, list(people), now=100.0 + i * 0.33)[7]
    return res


def test_still_robot_is_still():
    assert run([scene(30)] * 5)["state"] == "STILL"


def test_rotating_arm_is_moving_with_a_direction():
    r = run([scene(30 + 6 * i) for i in range(6)])
    assert r["state"] == "MOVING" and r["moving_share"] > 0 and r["magnitude"] > 0


def test_light_change_is_not_motion():
    assert run([scene(30, light=1.0), scene(30, light=1.0), scene(30, light=0.7), scene(30, light=0.7)])["state"] == "STILL"


def test_whole_picture_shake_is_not_robot_motion():
    r = run([scene(30, shift=s) for s in (0, 6, 0, 6, 0)])
    assert r["state"] == "STILL"


def test_a_person_in_front_is_occluded_not_still():
    r = run([scene(30 + 6 * i) for i in range(5)], people=[(0.25, 0.1, 0.4, 0.8)])
    assert r["state"] == "OCCLUDED"
