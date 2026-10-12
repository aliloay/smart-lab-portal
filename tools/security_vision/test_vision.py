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
    person = [(0.2, 0.2, 0.2, 0.5)]
    st = zw.update(ZONE, _scene(shift=70), person, 5.0)[0]
    assert st.status == "OK"                                  # just arrived / passing: not in use
    st = zw.update(ZONE, _scene(shift=70), person, 5.0 + ZoneWatcher.IN_USE_AFTER_S)[0]
    assert st.status == "IN_USE"                              # stayed: using it


def test_walking_past_is_neither_use_nor_movement():
    zw = ZoneWatcher()
    zw.update(ZONE, _scene(), [], 0.0)
    for k in range(6):                                        # a person crossing in front, 0.4 s steps
        t = 1.0 + 0.4 * k
        st = zw.update(ZONE, _scene(shift=10 * k), [(0.1 + 0.05 * k, 0.2, 0.2, 0.5)], t)[0]
        assert st.status == "OK"


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


def test_boxes_follow_people_between_detections():
    """The live view is drawn 15 times a second, detection runs ~3: between
    detections each box moves on at the person's speed (capped), so boxes
    keep up with people instead of jumping."""
    from vision import Track, predicted
    t = Track(1, (100.0, 50.0, 40.0, 120.0), first_seen=0.0, last_seen=10.0, vel=(200.0, 0.0))
    p = predicted([t], now=10.2)[0]
    assert p.box[0] == pytest.approx(140.0) and p.box[1:] == t.box[1:]
    assert t.box[0] == 100.0                                   # the track itself is untouched
    far = predicted([t], now=13.0)[0]                          # long gap: never extrapolate wildly
    assert far.box[0] == pytest.approx(100.0 + 200.0 * predicted.MAX_AHEAD_S)


KNOWN = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"},
         {"auth_subject": "USER2", "name": "Dr. Ramy", "role": "LAB_STAFF"}]


def test_face_names_after_two_agreeing_matches_on_hold_until_the_door():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    lab.face_vote(1, "USER1", 10.0)
    lab.assign([t], [], None, now=10.0, known=KNOWN)
    assert t.label is None                          # one match is not enough
    lab.face_vote(1, "USER1", 11.5)
    lab.assign([t], [], None, now=11.5, known=KNOWN)
    assert (t.label, t.name, t.source, t.entered) == ("USER1", "Ali", "face", False)
    lab.assign([t], [], None, now=30.0, known=KNOWN)
    assert t.label == "USER1"                       # kept although nobody entered
    lab.assign([t], [occ("USER1", "Ali", "STUDENT", 31.0)], None, now=32.0, known=KNOWN)
    assert t.entered is True                        # the door confirmed it


def test_face_matches_that_disagree_or_are_old_name_nobody():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    lab.face_vote(1, "USER1", 10.0)
    lab.face_vote(1, "USER2", 11.0)
    lab.assign([t], [], None, now=11.0, known=KNOWN)
    assert t.label is None
    lab2 = Labeler()
    lab2.face_vote(1, "USER1", 0.0)
    lab2.face_vote(1, "USER1", 30.0)                # too far apart to count together
    lab2.assign([t], [], None, now=30.0, known=KNOWN)
    assert t.label is None


def test_door_name_is_not_overridden_by_a_face():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    lab.assign([t], [occ("USER2", "Dr. Ramy", "LAB_STAFF", 0.0)], None, 10.0, known=KNOWN)
    assert (t.label, t.source, t.entered) == ("USER2", "door", True)
    lab.face_vote(1, "USER1", 11.0)
    lab.face_vote(1, "USER1", 12.0)
    lab.assign([t], [occ("USER2", "Dr. Ramy", "LAB_STAFF", 0.0)], None, 12.0, known=KNOWN)
    assert t.label == "USER2"


def test_face_that_agrees_with_the_door_verifies_the_name():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    inside = [occ("USER1", "Ali", "STUDENT", 0.0)]
    lab.assign([t], inside, None, 10.0, known=KNOWN)
    assert (t.label, t.verified) == ("USER1", False)          # the door alone named him
    lab.face_vote(1, "USER1", 11.0)
    lab.face_vote(1, "USER1", 12.0)
    lab.assign([t], inside, None, 12.0, known=KNOWN)
    assert t.verified is True and t.mismatch is None


def test_face_of_someone_else_than_the_badge_is_a_mismatch():
    """Ali's card was used, but the face is clearly Dr. Ramy's: card sharing."""
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    inside = [occ("USER1", "Ali", "STUDENT", 0.0)]
    lab.assign([t], inside, None, 10.0, known=KNOWN)
    lab.face_vote(1, "USER2", 11.0)
    lab.face_vote(1, "USER2", 12.0)
    lab.assign([t], inside, None, 12.0, known=KNOWN)
    assert t.label == "USER1" and t.verified is False         # the door's name stays...
    assert t.mismatch == "USER2"                              # ...and the face that contradicts it is flagged


def test_face_named_person_who_then_enters_is_verified():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 10.0, 10.0)
    lab.face_vote(1, "USER1", 10.0)
    lab.face_vote(1, "USER1", 11.0)
    lab.assign([t], [], None, 11.0, known=KNOWN)
    assert (t.entered, t.verified) == (False, False)          # on hold
    lab.assign([t], [occ("USER1", "Ali", "STUDENT", 12.0)], None, 13.0, known=KNOWN)
    assert (t.entered, t.verified) == (True, True)


def test_find_equipment_keeps_screens_and_drops_containers_and_weak_hits():
    """Tiled equipment search: weak hits dropped, a box that mostly contains
    another (cabinet around a monitor) keeps only the more confident one."""
    import numpy as np
    from vision import Detection, find_equipment

    class Fake:
        def detect(self, img):
            if img.shape[1] < 900:                    # tiles: nothing extra
                return []
            return [Detection(62, 0.89, (100, 100, 140, 120)),   # monitor
                    Detection(62, 0.66, (450, 90, 120, 160)),    # cabinet...
                    Detection(62, 0.73, (480, 150, 80, 80)),     # ...around this monitor
                    Detection(62, 0.22, (280, 220, 130, 80)),    # chair back
                    Detection(0, 0.95, (600, 200, 60, 200))]     # a person: not equipment
    kept = find_equipment(Fake(), np.zeros((540, 960, 3), np.uint8))
    assert sorted(round(d.score, 2) for d in kept) == [0.73, 0.89]


def _arm(angle):
    """A big box with a small 'arm' in it (like the UR5e in its frame)."""
    img = np.full((360, 640), 90, np.uint8)
    cv2.rectangle(img, (100, 100), (300, 300), 140, 3)
    cv2.line(img, (200, 120), (200 + angle, 200), 230, 9)
    return img


ARM = [{"id": 2, "name": "UR5e", "x": 80 / 640, "y": 80 / 360, "w": 240 / 640, "h": 240 / 360,
        "alert_on_motion": False}]


def test_a_moving_robot_shows_moving_until_it_really_stops_then_its_pose_is_normal():
    zw = ZoneWatcher()
    zw.update(ARM, _arm(0), [], 0.0)
    zw.update(ARM, _arm(25), [], 0.5)                          # one moving frame: not yet
    assert zw.update(ARM, _arm(50), [], 1.0)[0].status == "MOTION"
    assert zw.update(ARM, _arm(50), [], 3.0)[0].status == "MOTION"   # a pause: still moving
    assert zw.update(ARM, _arm(50), [], 6.0)[0].status != "MOTION"   # still for > 4 s
    assert zw.update(ARM, _arm(50), [], 12.0)[0].status == "OK"      # parked: the new pose is normal
    assert zw.update(ARM, _arm(50), [], 16.0)[0].status == "OK"


def test_a_pc_that_moved_stays_changed():
    zw = ZoneWatcher()
    pc = [{**ARM[0], "name": "PC-01", "alert_on_motion": True}]
    zw.update(pc, _arm(0), [], 0.0)
    zw.update(pc, _arm(25), [], 0.5)
    zw.update(pc, _arm(50), [], 1.0)
    for t in (6.0, 8.0, 12.0, 16.0):
        st = zw.update(pc, _arm(50), [], t)[0]
    assert st.status == "CHANGED"


def test_door_open_from_the_red_leaf():
    from vision import DoorWatcher, red_share
    wall = np.full((100, 100, 3), 200, np.uint8)
    door = wall.copy()
    door[10:90, 10:60] = (30, 30, 200)                     # BGR red leaf
    box = (0.0, 0.0, 1.0, 1.0)
    dw = DoorWatcher()
    assert dw.update(red_share(wall, box)) is False        # never seen red: closed
    assert dw.update(red_share(door, box)) is True
    half = wall.copy()
    half[10:90, 10:35] = (30, 30, 200)                     # someone half in front: no flicker
    assert dw.update(red_share(half, box)) is True
    assert dw.update(red_share(wall, box), occupied=True) is True   # a person hides it: not "closed"
    assert dw.update(red_share(wall, box)) is False


def test_a_face_name_comes_back_by_look_after_the_track_was_lost():
    """Ali is named by face near the camera, walks back to his laptop (the
    track breaks, the face is too small there): he gets 'Ali - not entered'
    back by his look. A stranger does not."""
    img, (a,) = _frame((100, ALI))
    la = _looks(img, [a])[0]
    lab = Labeler()
    t = Track(1, a, 10.0, 10.0, look=la)
    lab.face_vote(1, "USER1", 10.0)
    lab.face_vote(1, "USER1", 11.0)
    for k in range(4):                                   # seen clear: the look is learnt
        lab.assign([t], [], None, now=11.0 + k, known=KNOWN)
    assert (t.label, t.source, t.entered) == ("USER1", "face", False)
    back = Track(9, (400, 60, 60, 240), 40.0, 40.0, look=la)    # a new track, no face match yet
    lab.assign([back], [], None, now=40.0, known=KNOWN)
    assert back.label is None                            # by look alone: no (2026-10-12 fix)
    lab.face_vote(9, "USER1", 41.0)                      # one face match of this person ...
    lab.assign([back], [], None, now=41.0, known=KNOWN)
    assert (back.label, back.source, back.entered) == ("USER1", "face", False)   # ... plus the look: yes
    stranger_img, (s,) = _frame((300, ((0, 0, 0), (0, 200, 255), (200, 200, 0))))
    lab2 = Labeler()
    lab2.face_named = dict(lab.face_named)
    lab2.identities = dict(lab.identities)
    stranger = Track(10, s, 50.0, 50.0, look=_looks(stranger_img, [s])[0])
    lab2.assign([stranger], [], None, now=50.0, known=KNOWN)
    assert stranger.label is None


def test_a_small_robot_move_is_logged_as_a_new_pose():
    zw = ZoneWatcher()
    zw.update(ARM, _arm(0), [], 0.0)
    zw.update(ARM, _arm(14), [], 0.5)                    # moved a bit, in one frame
    for t in (1.0, 3.0, 7.0):
        st = zw.update(ARM, _arm(14), [], t)[0]
    assert st.new_pose and st.status == "OK"


def test_a_face_name_never_lands_on_a_small_half_hidden_person():
    """18:27 in the lab: Ali's face name jumped onto Eng. Hemaly, seen only as
    a small head behind the monitors. Small people are never given a face name."""
    img, (a,) = _frame((100, ALI))
    la = _looks(img, [a])[0]
    lab = Labeler()
    t = Track(1, a, 10.0, 10.0, look=la)
    lab.face_vote(1, "USER1", 10.0)
    lab.face_vote(1, "USER1", 11.0)
    for k in range(4):
        lab.assign([t], [], None, now=11.0 + k, known=KNOWN)
    head = Track(5, (440, 237, 32, 45), 40.0, 40.0, look=la)         # same colours, but tiny
    lab.assign([head], [], None, now=40.0, known=KNOWN)
    assert head.label is None
    # Two big unnamed people who both fit: not clearly one of them - nobody.
    p1 = Track(6, (100, 60, 60, 240), 70.0, 70.0, look=la)          # long after: not by place
    p2 = Track(7, (400, 60, 60, 240), 70.0, 70.0, look=la)
    lab.assign([p1, p2], [], None, now=70.0, known=KNOWN)
    assert p1.label is None and p2.label is None


def test_a_seated_person_who_drops_out_gets_the_name_back_at_the_same_place():
    """Hemaly at the back is a 33x48 px head behind the monitors: the detector
    loses him and finds him again as a new track. Same place, moments later:
    same person - by place, not by look."""
    lab = Labeler()
    t = Track(1, (435, 235, 33, 48), 10.0, 10.0)
    lab.face_vote(1, "USER5", 10.0)
    lab.face_vote(1, "USER5", 11.0)
    lab.assign([t], [], None, now=11.0, known=KNOWN5)
    assert t.label == "USER5"
    lab.assign([], [], None, now=14.0, known=KNOWN5)                   # lost behind the monitor
    again = Track(2, (437, 236, 31, 47), 15.0, 15.0)
    elsewhere = Track(3, (100, 300, 70, 150), 15.0, 15.0)
    lab.assign([again, elsewhere], [], None, now=15.0, known=KNOWN5)
    assert again.label == "USER5" and elsewhere.label is None
    lab.assign([], [], None, now=16.0, known=KNOWN5)
    late = Track(4, (437, 236, 31, 47), 60.0, 60.0)                   # long after: not handed back
    lab.assign([late], [], None, now=60.0, known=KNOWN5)
    assert late.label is None


def test_no_hand_back_when_two_new_people_are_at_the_place():
    lab = Labeler()
    t = Track(1, (435, 235, 40, 60), 10.0, 10.0)
    lab.face_vote(1, "USER5", 10.0)
    lab.face_vote(1, "USER5", 11.0)
    lab.assign([t], [], None, now=11.0, known=KNOWN5)
    lab.assign([], [], None, now=12.0, known=KNOWN5)
    a, b = Track(2, (436, 236, 40, 60), 13.0, 13.0), Track(3, (446, 240, 40, 60), 13.0, 13.0)
    lab.assign([a, b], [], None, now=13.0, known=KNOWN5)
    assert a.label is None and b.label is None


KNOWN5 = [{"auth_subject": "USER5", "name": "Eng. Hemaly", "role": "LAB_STAFF"}]


def test_robot_home_saved_then_at_home_away_and_resave():
    import numpy as np
    from vision import ZoneWatcher
    zw = ZoneWatcher()
    rng = np.random.default_rng(1)
    home = rng.integers(0, 255, (200, 200), dtype=np.uint8)
    robot = {"id": 1, "name": "UR5e", "x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4, "alert_on_motion": False}
    pc = {"id": 2, "name": "PC-01", "x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}
    assert zw.save_home([robot, pc], home) == ["UR5e"]          # PCs have no HOME
    st = {s.id: s for s in zw.update([robot], home, [], 0.0)}
    assert st[1].home == "AT_HOME"
    away = rng.integers(0, 255, (200, 200), dtype=np.uint8)
    st = {s.id: s for s in zw.update([robot], away, [], 1.0)}
    assert st[1].home == "AWAY"
    moved = {**robot, "x": 0.25}
    st = {s.id: s for s in zw.update([moved], home, [], 2.0)}
    assert st[1].home == "RESAVE"                                # box moved: HOME must be saved again


def test_a_wrong_name_on_a_different_look_is_dropped():
    """The owner's case: a person in black ends up with Ali's (white top) name -
    after a few clear checks that do not look like Ali, the name is dropped."""
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    people = [occ("USER1", "Ali", "STUDENT", 0.0)]
    lab = Labeler()
    _learnt(lab, [ta], people)
    wrong = Track(5, b, 20.0, 20.0, label="USER1", name="Ali", role="STUDENT", look=lb)
    for k in range(Labeler.VETO_CHECKS):
        lab.assign([wrong], people, None, now=20.0 + k)
    assert wrong.label is None                      # Unknown rather than the wrong name


def test_face_named_person_keeps_the_name_through_a_crossing():
    """Named by face (not entered at the door): a tracker mix-up while passing
    someone is undone by the look, like a door name."""
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    lab = Labeler()
    ali = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"}
    lab.face_named["USER1"] = (ali, 0.0)
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    ta.source = "face"
    tb = Track(2, b, 0, 0, look=lb)
    _learnt(lab, [ta, tb], [])
    ta.look, tb.look = lb, la                       # mixed up while passing
    ta.separated_at = tb.separated_at = 10.0
    lab.assign([ta, tb], [], None, now=11.0)
    assert tb.label == "USER1" and ta.label is None


def test_locked_looks_and_face_names_survive_a_restart(tmp_path):
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    lab = Labeler()
    ali = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"}
    lab.face_named["USER1"] = (ali, 100.0)
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    ta.source = "face"
    _learnt(lab, [ta], [])
    p = str(tmp_path / "ids.npz")
    lab.save(p)
    fresh = Labeler()
    assert fresh.load(p, now=200.0) == 1
    assert "USER1" not in fresh.face_named                    # a face name needs the face again
    assert look_distance(fresh.identities["USER1"].look, la) < 0.05


def test_person_working_beside_a_robot_makes_it_in_use():
    """The UR5e box sits on the arm under the gantry; the person works beside / below it."""
    robot = [{"id": 9, "name": "UR5e", "x": 0.4, "y": 0.1, "w": 0.1, "h": 0.2, "alert_on_motion": False}]
    zw = ZoneWatcher()
    zw.update(robot, _scene(), [], 0.0)
    beside = [(0.52, 0.25, 0.08, 0.3)]                      # next to the arm, not overlapping its box
    zw.update(robot, _scene(), beside, 1.0)
    st = zw.update(robot, _scene(), beside, 1.0 + ZoneWatcher.IN_USE_AFTER_S)[0]
    assert st.status == "IN_USE"


def test_a_lost_name_goes_to_the_best_look_not_the_first_unnamed_person():
    """2026-10-12: Ali's door name went to whoever was unnamed first. Now it goes
    to the person who looks like Ali, and to nobody if two fit about equally."""
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    people = [occ("USER1", "Ali", "STUDENT", 0.0)]
    lab = Labeler()
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    _learnt(lab, [ta], people)
    sara = Track(20, b, 20.0, 19.0, look=lb)          # seen first, does not look like Ali
    ali = Track(21, a, 20.0, 20.0, look=la)
    lab.assign([sara, ali], people, None, now=20.0)
    assert ali.label == "USER1" and sara.label is None


def test_a_name_is_never_on_two_people():
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    people = [occ("USER1", "Ali", "STUDENT", 0.0)]
    lab = Labeler()
    ta = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    _learnt(lab, [ta], people)
    twin = Track(2, b, 5.0, 5.0, label="USER1", name="Ali", role="STUDENT", look=lb)
    lab.assign([ta, twin], people, None, now=10.0)
    assert [t.label for t in (ta, twin)] == ["USER1", None]


def test_a_track_keeps_its_clean_look_while_people_touch():
    """Root cause #2: during a crossing the box holds parts of the other person;
    the track must not take that mixed look as its own."""
    tr = Tracker()
    img, (a, b) = _frame((100, ALI), (400, SARA))
    la, lb = _looks(img, [a, b])
    tr.update([a, b], 0.0, [la, lb])
    ali_id = next(t.id for t in tr.tracks if t.box[0] < 300)
    near_a, near_b = (a[0] + 150, a[1], a[2], a[3]), (a[0] + 190, b[1], b[2], b[3])   # side by side
    tr.update([near_a, near_b], 0.3, [lb, la])                        # looks mixed while touching
    ali = next(t for t in tr.tracks if t.id == ali_id)
    assert look_distance(ali.look, la) < 0.1                          # still Ali's own look
