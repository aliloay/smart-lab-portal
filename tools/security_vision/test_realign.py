"""
Re-aligning boxes after the camera's view moves (realign.py), without a
camera: a textured "room" picture, shifted / cut by known amounts.

    py -m pytest test_realign.py -q
"""
import cv2
import numpy as np

import realign


def room(seed=7, w=960, h=540):
    """A picture with plenty of fixed corners and edges (like a real room)."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 200, np.uint8)
    for _ in range(140):
        x, y = int(rng.integers(0, w - 60)), int(rng.integers(0, h - 60))
        cw, ch = int(rng.integers(15, 70)), int(rng.integers(15, 70))
        col = tuple(int(c) for c in rng.integers(0, 255, 3))
        cv2.rectangle(img, (x, y), (x + cw, y + ch), col, -1)
    for _ in range(60):
        cv2.line(img, tuple(int(v) for v in rng.integers(0, w, 2) % [w, h]),
                 tuple(int(v) for v in rng.integers(0, w, 2) % [w, h]), (20, 20, 20), 2)
    return img


def shifted(img, dx, dy):
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderValue=(200, 200, 200))


BOX = {"id": 1, "x": 0.40, "y": 0.40, "w": 0.10, "h": 0.12}


def test_still_view_is_not_moved():
    img = room()
    ref = realign.make_reference(img, [], "k")
    m = realign.compare(ref, img, [])
    assert m.confident and not m.moved


def test_a_pan_moves_every_box_by_the_same_amount():
    img = room()
    ref = realign.make_reference(img, [], "k")
    m = realign.compare(ref, shifted(img, 60, -25), [])        # camera turned: picture slides
    assert m.confident and m.moved
    nb = realign.move_box(m.homography, BOX)
    assert nb is not None
    assert abs(nb["x"] - (0.40 + 60 / 960)) < 0.01 and abs(nb["y"] - (0.40 - 25 / 540)) < 0.01
    assert abs(nb["w"] - 0.10) < 0.01 and abs(nb["h"] - 0.12) < 0.01


def test_a_box_that_left_the_picture_is_reported_lost():
    img = room()
    ref = realign.make_reference(img, [], "k")
    m = realign.compare(ref, shifted(img, -200, 0), [])
    edge = {"id": 2, "x": 0.02, "y": 0.4, "w": 0.1, "h": 0.1}   # slid out on the left
    assert m.confident and realign.move_box(m.homography, edge) is None


def test_a_different_room_is_not_confident():
    m = realign.compare(realign.make_reference(room(1), [], "k"), room(99), [])
    assert not m.confident                                      # never guess


def test_people_are_not_part_of_the_room():
    img = room()
    ref = realign.make_reference(img, [(400, 200, 120, 300)], "k")
    for kp in ref.keypoints:                                    # no feature inside the masked person
        x, y = kp.pt
        s = realign.WORK_WIDTH / 960
        assert not (400 * s < x < 520 * s and 200 * s < y < 500 * s)


def test_zones_key_changes_when_a_box_changes():
    a = realign.zones_key([BOX], None)
    assert a == realign.zones_key([dict(BOX)], None)
    assert a != realign.zones_key([{**BOX, "x": 0.41}], None)
    assert a != realign.zones_key([BOX], {"id": 9, "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.2})
