"""Tests for the pieces of vision.py that need no camera: py -m pytest -q"""
import os

import cv2
import numpy as np
import pytest

from vision import PERSON, Detector, Labeler, Tracker, Track, ZoneWatcher, draw, iou

HERE = os.path.dirname(os.path.abspath(__file__))


def occ(subject, name, role, at):
    return {"auth_subject": subject, "name": name, "role": role, "entered_at": at}


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1
    assert iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0


def test_tracker_keeps_ids_and_confirms_after_three_frames():
    tr = Tracker()
    for i in range(3):
        out = tr.update([(10 + i, 10, 50, 100)], now=i * 0.3)
    assert len(out) == 1 and out[0].id == 1
    out = tr.update([(14, 10, 50, 100), (300, 10, 50, 100)], now=1.0)
    assert [t.id for t in out] == [1]              # the new one is not confirmed yet
    tr.update([], now=4.0)
    assert tr.tracks == []                          # both gone after MAX_MISS_S


def test_entrant_in_door_area_gets_that_name():
    lab = Labeler()
    door = (500, 0, 140, 480)
    a = Track(1, (520, 100, 60, 200), first_seen=100.0, last_seen=100.0)     # in the door area
    b = Track(2, (100, 100, 60, 200), first_seen=50.0, last_seen=100.0)      # already inside
    people = [occ("USER1", "Ali", "STUDENT", 40.0), occ("USER2", "Dr. Ramy", "LAB_STAFF", 98.0)]
    lab.assign([a, b], people, door, now=100.0)
    assert a.label == "USER2" and a.role == "LAB_STAFF"
    assert b.label == "USER1"                       # elimination: the only name left


def test_no_guessing_with_two_unknowns():
    lab = Labeler()
    a = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    b = Track(2, (300, 100, 60, 200), 10.0, 10.0)
    lab.assign([a, b], [occ("USER1", "Ali", "STUDENT", 0.0), occ("USER2", "R", "LAB_STAFF", 0.0)],
               None, now=10.0)
    assert a.label is None and b.label is None


def test_name_dropped_when_person_left():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    lab.assign([t], [occ("USER1", "Ali", "STUDENT", 0.0)], None, 10.0)
    assert t.label == "USER1"
    lab.assign([t], [], None, 20.0)
    assert t.label is None


def _scene(shift=0, light=1.0):
    img = np.full((360, 640), 90, np.uint8)
    cv2.rectangle(img, (100 + shift, 100), (220 + shift, 200), 200, -1)   # "a PC"
    cv2.circle(img, (160 + shift, 150), 20, 30, -1)
    return np.clip(img.astype(np.float32) * light, 0, 255).astype(np.uint8)


ZONE = [{"id": 1, "name": "PC-01", "x": 80 / 640, "y": 80 / 360, "w": 160 / 640, "h": 140 / 360}]


def test_zone_learns_then_flags_a_moved_item():
    zw = ZoneWatcher()
    assert zw.update(ZONE, _scene(), [], 0.0)[0].status == "OK"         # first clear view = reference
    assert zw.update(ZONE, _scene(light=0.6), [], 1.0)[0].status == "OK"  # lights dimmed: still OK
    zw.update(ZONE, _scene(shift=70), [], 2.0)
    zw.update(ZONE, _scene(shift=70), [], 3.0)
    st = zw.update(ZONE, _scene(shift=70), [], 6.5)[0]        # held 3 s after the motion stopped
    assert st.status == "CHANGED" and st.score > zw.CHANGE_AT
    zw.accept(1)
    assert zw.update(ZONE, _scene(shift=70), [], 7.0)[0].status == "OK"


def test_person_at_the_item_means_in_use():
    zw = ZoneWatcher()
    zw.update(ZONE, _scene(), [], 0.0)
    st = zw.update(ZONE, _scene(shift=70), [(0.2, 0.2, 0.2, 0.5)], 5.0)[0]
    assert st.status == "IN_USE"


def test_draw_does_not_crash():
    f = np.zeros((360, 640, 3), np.uint8)
    t = Track(1, (100, 100, 60, 200), 0, 0, label="USER1", name="Ali", role="STUDENT")
    draw(f, [t, Track(2, (300, 100, 60, 200), 0, 0)], ZONE, {}, (0.8, 0, 0.2, 1))
    assert f.any()


@pytest.mark.skipif(not os.path.isfile(os.path.join(HERE, "models", "object_detection_yolox_2022nov.onnx")),
                    reason="model not downloaded")
def test_detector_finds_a_person():
    img = cv2.imread(os.path.join(HERE, "..", "..", "firmware", "face_server", "portraits", "USER2.jpg"))
    if img is None:
        pytest.skip("no sample image on this machine")
    dets = Detector(os.path.join(HERE, "models", "object_detection_yolox_2022nov.onnx"), size=416).detect(img)
    assert any(d.cls == PERSON and d.score > 0.6 for d in dets)
