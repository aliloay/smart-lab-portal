"""Gemini audit 24 Nov 2026, identity bugs 1A-1C, 2A-2C, 4, the robot view and the seated posture: each one reproduced."""
import numpy as np

from activity import on_recorded_seat, posture
from crosscam import HANDOFF_PASSES, SEAT_PASSES, STABLE_PASSES, CrossCam, FloorMap, peer_view, seats_of
from labmap import LabNumbers
from robotvision import RobotVisualMotion
from vision import Labeler, Look, Track

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"}
W, H = 960, 540
FLOOR = FloorMap([{"px": [0, 0], "floor": [0, 0]}, {"px": [1, 0], "floor": [6, 0]},
                  {"px": [1, 1], "floor": [6, 10]}, {"px": [0, 1], "floor": [0, 10]}])


def look(seed, partial=False):
    v = np.random.default_rng(seed).normal(size=64).astype(np.float32)
    return Look(None, v / np.linalg.norm(v), partial=partial)


def track(i=1, seed=1, box=(400, 100, 60, 200)):
    t = Track(i, box, 0.0, 0.0, hits=10)
    t.look = look(seed)
    return t


def peer(now, *tracks, calibrated=True):
    return {"t": now, "frame_t": now, "calibrated": calibrated, "tracks": list(tracks)}


def p(t, label="USER1", source="peer", state="REID_CONFIRMED", pid=7, **kw):
    return {"id": pid, "floor": list(FLOOR.feet(t.box, W, H)), "desk": None, "seat": None, "label": label, "name": "Ali",
            "role": None, "source": source, "state": state, "crowded": False, "lab_no": None,
            "deep": [float(x) for x in t.look.deep], **kw}


def confirmed(lab, t, n=8, now=0.0):
    lab._give(t, ALI, "operator")
    for k in range(n):
        lab._doubt_confirmed([t], now + k * 0.2)


def swap(lab, t, seed=2, n=10, now=10.0):
    t.crowded = True
    lab._doubt_confirmed([t], now)
    t.crowded = False
    t.look = look(seed)
    for k in range(n):
        lab._doubt_confirmed([t], now + 0.2 * (k + 1))


# ---- 1A
def test_1a_a_copied_name_never_reconfirms_a_doubted_one():
    lab, t, cc = Labeler(), track(), CrossCam(None, "k", FLOOR)
    confirmed(lab, t)
    swap(lab, t)
    assert t.source == "look" and t.doubted == "USER1"
    for k in range(30):
        now = 20.0 + 0.2 * k
        cc.peer = peer(now, p(t))
        cc.share([t], W, H, now, lab)
        assert t.source == "look"
    # even door / staff names there do not bring the doubted name back here; this camera's own face or staff do
    for k in range(10):
        cc.peer = peer(30.0 + k * 0.2, p(t, source="operator", state="OPERATOR_CONFIRMED"))
        cc.share([t], W, H, 30.0 + k * 0.2, lab)
    assert t.source == "look"
    lab._give(t, ALI, "operator")
    assert t.source == "operator" and t.doubted is None


def test_1a_the_copy_on_the_other_camera_becomes_a_guess_too():
    lab, t, cc = Labeler(), track(), CrossCam(None, "k", FLOOR)
    lab._give(t, ALI, "peer", how="other camera")
    for k in range(STABLE_PASSES + 2):
        now = 20.0 + 0.2 * k
        cc.peer = peer(now, p(t, source="look", state="IDENTITY_UNCERTAIN", doubt="USER1"))
        cc.share([t], W, H, now, lab)
    assert t.source == "look" and t.doubted == "USER1"
    assert peer_view([t], FLOOR, W, H, 1.0)["tracks"][0]["doubt"] == "USER1"


def test_1a_an_undoubted_guess_is_still_confirmed_by_real_evidence_there_but_not_by_a_copy():
    for source, state, want in (("face", "FACE_CONFIRMED", "peer"), ("peer", "REID_CONFIRMED", "look")):
        lab, t, cc = Labeler(), track(), CrossCam(None, "k", FLOOR)
        lab.look_back(t, ALI, 0.0)
        for k in range(STABLE_PASSES + 2):
            now = 20.0 + 0.2 * k
            cc.peer = peer(now, p(t, source=source, state=state))
            cc.share([t], W, H, now, lab)
        assert t.source == want, source


# ---- 1B
def test_1b_crowded_at_the_confirmation_does_not_switch_the_check_off():
    lab, t = Labeler(), track()
    lab._give(t, ALI, "operator")
    t.crowded = True
    for k in range(5):
        lab._doubt_confirmed([t], k * 0.2)
    assert t.quarantine and any(n["kind"] == "CONFIRMED_NAME_TOUCHED_EARLY" for n in lab.notes)
    t.crowded = False
    for k in range(20):
        lab._doubt_confirmed([t], 2 + k * 0.2)
    assert not t.quarantine and t.source == "operator"
    swap(lab, t)
    assert t.source == "look"


def test_1b_touch_after_one_clean_frame_still_detects_the_swap_and_keeps_the_right_person():
    for seed, want in ((2, "look"), (1, "operator")):
        lab, t = Labeler(), track()
        confirmed(lab, t, n=1)
        swap(lab, t, seed=seed, n=12)
        assert t.source == want, seed


def test_1b_small_boxes_and_repeated_touches():
    lab, t = Labeler(), track(box=(400, 100, 20, 60))
    confirmed(lab, t)                                    # too small to judge: no reference yet
    t.box = (400, 100, 60, 200)
    for k in range(10):
        lab._doubt_confirmed([t], 5 + k * 0.2)
    for r in range(3):
        swap(lab, t, seed=1, now=10.0 + 5 * r)
    assert t.source == "operator"
    swap(lab, t, seed=2, now=40.0)
    assert t.source == "look"


# ---- 1C
def test_1c_the_other_persons_look_is_never_learnt():
    lab, t = Labeler(), track()
    t.look = look(1, partial=True)                       # confirmed while seated: no whole-body look known yet
    confirmed(lab, t)
    t.crowded = True
    lab._doubt_confirmed([t], 10.0)
    t.crowded, t.look = False, look(2)
    for k in range(9):                                   # before the doubt fires
        t.last_seen = 12 + k * 0.2
        lab._doubt_confirmed([t], 12 + k * 0.2)
        lab._learn([t])
        assert t.quarantine and "USER1" not in lab.identities


def test_1c_the_lab_number_keeps_its_own_look(tmp_path):
    ln, t = LabNumbers(str(tmp_path / "n.json"), "A"), track()
    t.label, t.name, t.source = "USER1", "Ali", "operator"
    ln.assign([t], {}, 100.0)
    deep = lambda: ln.reg.update(lambda d: d["people"][str(t.lab_no)]["deep"])
    before = deep()
    t.look, t.quarantine = look(2), True
    for k in range(9):
        ln.assign([t], {}, 103.0 + 3 * k)
    assert deep() == before
    t.look, t.quarantine = look(1), False
    ln.assign([t], {}, 150.0)


def test_1c_learning_goes_on_for_the_right_person_after_the_check():
    lab, t = Labeler(), track()
    confirmed(lab, t)
    swap(lab, t, seed=1, n=5)
    t.last_seen = 50.0
    lab._learn([t])
    assert not t.quarantine and "USER1" in lab.identities


# ---- 2A / 2B / 2C
SEATS = {"PC-09": (0.60, 0.56, 0.10, 0.23), "PC-09@B": (0.30, 0.2, 0.06, 0.1)}


def px(n):
    x, y, w, h = SEATS[n]
    return (x * W, y * H, w * W, h * H)


def seat_peer(seat, label="USER1", state="OPERATOR_CONFIRMED", i=7, **kw):
    return {"id": i, "seat": seat, "label": label, "name": "Ali", "source": "operator", "state": state, **kw}


def hints(peers, tracks, n=SEAT_PASSES + 1):
    cc = CrossCam(None, "k", None)
    cc.all_seats = SEATS
    for k in range(n):
        now = 1000.0 + k * 0.2
        cc.peer = {"t": now, "frame_t": now, "calibrated": False, "tracks": peers}
        cc.seat_hints(tracks, W, H, now)
    return cc


def test_2a_two_people_at_one_pc_are_both_seen_and_nobody_gets_the_guess():
    assert seats_of([px("PC-09"), px("PC-09@B")], W, H, SEATS) == ["PC-09", "PC-09@B"]
    t = Track(1, px("PC-09"), 0, 0)
    hints([seat_peer("PC-09"), seat_peer("PC-09@B", label=None, i=8)], [t])
    assert t.hint is None
    a, b = Track(1, px("PC-09"), 0, 0), Track(2, px("PC-09@B"), 0, 0)
    hints([seat_peer("PC-09")], [a, b])
    assert a.hint is None and b.hint is None
    hints([seat_peer("PC-09@B")], [t])
    assert t.hint == "Ali?"                              # one person here, one there, either spot of the PC


def test_2b_only_confirmed_states_and_the_hint_never_outlives_its_reason():
    for state in ("IDENTITY_CONFLICT", "OCCLUDED", "IDENTITY_UNCERTAIN", "UNKNOWN", "TENTATIVE", None):
        t = Track(1, px("PC-09"), 0, 0)
        hints([seat_peer("PC-09", state=state)], [t])
        assert t.hint is None, state
    t = Track(1, px("PC-09"), 0, 0)
    cc = hints([seat_peer("PC-09")], [t])
    assert t.hint == "Ali?" and t.label is None
    cc.peer = {"t": 1010.0, "frame_t": 1010.0, "calibrated": False, "tracks": []}
    cc.seat_hints([t], W, H, 1010.0)
    assert t.hint is None and t.hint_kind is None
    t.hint = "Eng. Hemaly?"                              # another rule's hint is left alone
    cc.seat_hints([t], W, H, 1010.2)
    assert t.hint == "Eng. Hemaly?"


def test_2c_the_same_desk_never_names_anyone():
    for source, state in (("operator", "OPERATOR_CONFIRMED"), ("face", "FACE_CONFIRMED"), ("peer", "REID_CONFIRMED")):
        for guess in (None, "look", "desk"):
            cc, lab, t = CrossCam(None, "k", None), Labeler(), track(box=(410, 380, 100, 150))
            cc.desk_link, cc.desks = {"PC-08": "PC-08"}, {"PC-08": (0.42, 0.7, 0.12, 0.28)}
            if guess:
                lab._give(t, {"auth_subject": "USER1" if guess == "look" else "USER9", "name": "x"}, guess)
            for k in range(STABLE_PASSES + 8):
                now = 1000.0 + k * 0.2
                cc.peer = peer(now, {**p(t, source=source, state=state), "desk": "PC-08", "floor": None}, calibrated=False)
                cc.share([t], W, H, now, lab)
            assert t.source in (guess, "look"), (source, guess)  # at most the look guess, never confirmed


# ---- 4
def test_4_the_veto_holds_on_every_path():
    t = track()
    t.not_names = frozenset({"USER1"})
    # floor pairing, handoff, elimination-free share
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    for k in range(HANDOFF_PASSES + 6):
        now = 1000.0 + k * 0.2
        cc.peer = peer(now, p(t, source="face", state="FACE_CONFIRMED"))
        cc.share([t], W, H, now, lab)
        assert t.label is None
    # seat guess
    s = Track(1, px("PC-09"), 0, 0)
    s.not_names = frozenset({"USER1"})
    hints([seat_peer("PC-09")], [s])
    assert s.hint is None
    # stored look
    lab.identities["USER1"] = type("I", (), {"look": t.look, "samples": 9})()
    for k in range(40):
        lab._look_guess([t], {"USER1": ALI}, 100.0 + k)
    assert t.label is None
    t.not_names = frozenset()
    for k in range(40):
        lab._look_guess([t], {"USER1": ALI}, 200.0 + k)
    assert t.label == "USER1" and t.source == "look"     # the same path works without the veto


def test_4_labmap_fills_the_veto_and_staff_or_a_doubt_clear_it(tmp_path):
    ln = LabNumbers(str(tmp_path / "n.json"), "A")
    a, b = track(1, 1), track(2, 2, box=(700, 100, 60, 200))
    a.label, a.name, a.source = "USER1", "Ali", "operator"
    ln.assign([a, b], {}, 100.0)
    assert b.vetoed("USER1") and not a.vetoed("USER1")
    ln.assign([a, b], {2: {"id": 9, "label": "USER1", "lab_no": 5}}, 101.0, [{"id": 9, "label": "USER1", "source": "peer", "lab_no": 5}])
    assert b.vetoed("USER1")                             # seen beside the staff-confirmed person: a pairing does not undo it
    a.label = a.name = None
    a.source, a.doubted = None, "USER1"                  # the holder was the wrong one: the other may be the real one
    ln.assign([a, b], {}, 102.0)
    assert not b.vetoed("USER1") and a.vetoed("USER1")


def test_handoff_by_look_is_a_guess():
    cc, lab, t = CrossCam(None, "k", FLOOR), Labeler(), track(box=(400, 300, 60, 239))      # feet cut
    for k in range(HANDOFF_PASSES + 2):
        now = 1000.0 + k * 0.2
        cc.peer = peer(now, {**p(t, source="face", state="FACE_CONFIRMED"), "floor": None})
        cc.share([t], W, H, now, lab)
    assert t.label == "USER1" and t.source == "look"


# ---- robot view
ZONE = [{"id": 1, "x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6}]


def robot(person=None, arm=False, n=14):
    """Synthetic pictures: a textured still scene, a person-sized textured block that walks, an arm-sized one that turns."""
    rng = np.random.default_rng(5)
    base = rng.integers(60, 190, (240, 320)).astype(np.uint8)
    import cv2
    base = cv2.GaussianBlur(base, (7, 7), 0)
    tex = cv2.GaussianBlur(rng.integers(0, 255, (240, 320)).astype(np.uint8), (5, 5), 0)
    v, out = RobotVisualMotion(), []
    for k in range(n):
        g, boxes = base.copy(), []
        if person:
            x = person[0] + person[1] * k
            g[90:200, x:x + 24] = tex[90:200, 10:34]
            boxes = [(x / 320, 90 / 240, 24 / 320, 110 / 240)]
        if arm:
            dx, dy = 4 * k, (3 * k) % 17
            g[56 + dy:84 + dy, 170 + dx % 40:215 + dx % 40] = tex[20:48, 60:105]
        out.append(v.update(ZONE, g, boxes, now=100.0 + 0.15 * k).get(1, {}).get("state"))
    return out


def test_robot_view_people_are_not_robot_motion_and_a_moving_robot_is_still_seen():
    assert set(robot()[2:]) == {"STILL"}
    assert "MOVING" not in robot(person=(80, 4))          # walks in front of a still robot
    assert "MOVING" not in robot(person=(120, 0))         # stands in front of it
    assert "MOVING" in robot(arm=True)
    assert "MOVING" in robot(person=(75, 0), arm=True)    # arm moves, partly beside a person


# ---- seated posture
def test_a_small_box_on_a_recorded_seat_is_seated_and_walking_past_is_not():
    zones = [{"name": "PC-08", "seat": [0.55, 0.52, 0.03, 0.125]}]
    t = Track(1, (0.55 * W, 0.52 * H, 0.03 * W, 0.125 * H), 0, 0)
    assert on_recorded_seat(t, zones, W, H) and posture(t.box, seated=True) == "seated or leaning"
    t.vel = (40.0, 0.0)
    assert not on_recorded_seat(t, zones, W, H)
    tall = Track(2, (0.55 * W, 0.40 * H, 0.04 * W, 0.26 * H), 0, 0)
    assert not on_recorded_seat(tall, zones, W, H)
    assert posture((0, 0, 40, 120)) == "standing"
