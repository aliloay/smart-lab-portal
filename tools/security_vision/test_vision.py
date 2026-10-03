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


# ------------------------------------------------- identity lock (looks) ---
from vision import Appearance, Look, color_signature, look_distance  # noqa: E402

# Two people as the camera would roughly see them (BGR): hair, top, trousers.
ALI = ((30, 30, 40), (40, 40, 200), (140, 80, 30))          # dark hair, red top, blue jeans
SARA = ((90, 210, 230), (235, 235, 235), (25, 25, 25))      # blonde, white top, black trousers
GREEN = ((40, 40, 40), (60, 170, 60), (60, 60, 60))


def _person(img, x, colors, y=60, w=60, h=240):
    hair, top, legs = colors
    cv2.rectangle(img, (x, y), (x + w, y + int(0.18 * h)), hair, -1)
    cv2.rectangle(img, (x, y + int(0.18 * h)), (x + w, y + int(0.55 * h)), top, -1)
    cv2.rectangle(img, (x, y + int(0.55 * h)), (x + w, y + h), legs, -1)
    return (float(x), float(y), float(w), float(h))


def _frame(*people):
    """people: (x, colors) drawn left to right in the given order (later = in front)."""
    img = np.full((360, 640, 3), 120, np.uint8)
    return img, [_person(img, x, c) for x, c in people]


def _looks(img, boxes):
    return Appearance().looks(img, boxes)


def test_looks_tell_two_people_apart():
    img, (a, b) = _frame((100, ALI), (400, SARA))
    img2, (a2,) = _frame((250, ALI))
    la, lb, la2 = Look(color_signature(img, a)), Look(color_signature(img, b)), Look(color_signature(img2, a2))
    assert look_distance(la, la2) < 0.1                     # the same person elsewhere
    assert look_distance(la, lb) > 0.5                      # someone else


def test_crossing_paths_keep_their_own_ids():
    tr = Tracker()
    ids = {}
    xs = list(range(60, 461, 40))                           # Ali walks right, Sara walks left
    for i, xa in enumerate(xs):
        xb = 520 - (xa - 60)
        img, boxes = _frame((xa, ALI), (xb, SARA))
        if abs(xa - xb) < 30:                               # fully overlapped: one box only
            boxes = [boxes[1]]
        out = tr.update(boxes, i / 3.0, _looks(img, boxes))
        if i == 3:
            ids = {("ALI" if t.box[0] < 300 else "SARA"): t.id for t in out}
    img, boxes = _frame((500, ALI), (40, SARA))
    out = tr.update(boxes, len(xs) / 3.0, _looks(img, boxes))
    by_x = {("ALI" if t.box[0] > 300 else "SARA"): t.id for t in out}
    assert by_x == ids                                      # nobody swapped


def _learnt(lab, tracks, occupants, frames=4, t0=0.0):
    for k in range(frames):
        lab.assign(tracks, occupants, None, t0 + k)


def test_names_go_back_to_their_looks_after_a_mix_up():
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    tb = Track(2, b, 0, 0, label="USER2", name="Sara", role="STUDENT", look=lb)
    people = [occ("USER1", "Ali", "STUDENT", 0.0), occ("USER2", "Sara", "STUDENT", 0.0)]
    lab = Labeler()
    _learnt(lab, [ta, tb], people)
    # They bumped into each other and the tracker mixed the boxes up.
    ta.look, tb.look = lb, la
    ta.separated_at = tb.separated_at = 10.0
    lab.assign([ta, tb], people, None, now=11.0)
    assert ta.label == "USER2" and tb.label == "USER1"      # each name follows its look


def test_no_swap_when_the_looks_still_fit():
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    tb = Track(2, b, 0, 0, label="USER2", name="Sara", role="STUDENT", look=lb)
    people = [occ("USER1", "Ali", "STUDENT", 0.0), occ("USER2", "Sara", "STUDENT", 0.0)]
    lab = Labeler()
    _learnt(lab, [ta, tb], people)
    ta.separated_at = tb.separated_at = 10.0
    lab.assign([ta, tb], people, None, now=11.0)
    assert ta.label == "USER1" and tb.label == "USER2"


def test_name_comes_back_after_being_hidden_but_never_to_a_stranger():
    img, (a, b, c) = _frame((60, ALI), (260, SARA), (460, GREEN))
    la, lb, lc = _looks(img, [a, b, c])
    people = [occ("USER1", "Ali", "STUDENT", 0.0), occ("USER2", "Sara", "STUDENT", 0.0),
              occ("USER3", "Omar", "STUDENT", 0.0)]
    lab = Labeler()
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    tb = Track(2, b, 0, 0, label="USER2", name="Sara", role="STUDENT", look=lb)
    tc = Track(3, c, 0, 0, label="USER3", name="Omar", role="STUDENT", look=lc)
    _learnt(lab, [ta, tb, tc], people)
    # Ali and Sara walk behind the robot (their tracks end); Ali comes back.
    back = Track(7, (300, 60, 60, 240), 20.0, 20.0, look=la)
    lab.assign([back, tc], people, None, now=20.0)
    assert back.label == "USER1"
    # A stranger in a green top while two names are free: stays Unknown.
    stranger_img, (s,) = _frame((300, ((0, 0, 0), (0, 200, 255), (200, 200, 0))))
    stranger = Track(8, s, 30.0, 30.0, look=_looks(stranger_img, [s])[0])
    lab.assign([stranger, tc], people, None, now=30.0)
    assert stranger.label is None


def test_looks_are_not_learnt_while_people_touch():
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    lab = Labeler()
    t = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    people = [occ("USER1", "Ali", "STUDENT", 0.0)]
    _learnt(lab, [t], people)
    before = lab.identities["USER1"].samples
    t.crowded, t.look = True, lb                            # touching Sara: the look is mixed
    lab.assign([t], people, None, now=50.0)
    assert lab.identities["USER1"].samples == before


REID = os.path.join(HERE, "models", "person_reid_youtu_2021nov.onnx")


@pytest.mark.skipif(not os.path.isfile(REID), reason="re-id model not downloaded")
def test_reid_model_gives_unit_vectors():
    img, boxes = _frame((100, ALI), (400, SARA))
    looks = Appearance(REID).looks(img, boxes)
    for lk in looks:
        assert lk.deep is not None and abs(float(np.linalg.norm(lk.deep)) - 1) < 1e-3
    assert look_distance(looks[0], looks[1]) > 0.2


def test_body_model_runs_when_people_are_close_and_once_a_second_otherwise():
    app = Appearance()
    apart = [(60.0, 60.0, 60.0, 240.0), (400.0, 60.0, 60.0, 240.0)]
    close = [(100.0, 60.0, 60.0, 240.0), (130.0, 60.0, 60.0, 240.0)]
    assert app.wants_deep(apart, 0.0)
    app._last_deep = 0.0
    assert not app.wants_deep(apart, 0.3)                   # alone and recent: colours only
    assert app.wants_deep(close, 0.6)                       # touching: every frame
    app._last_deep = 0.6
    assert app.wants_deep(apart, 1.5)                       # just apart: still every frame
    app._last_deep = 2.7
    assert not app.wants_deep(apart, 3.0)                   # settled again: back to once a second
