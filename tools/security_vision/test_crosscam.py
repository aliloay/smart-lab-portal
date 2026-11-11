"""Cross-camera name sharing (SIMULATED: synthetic tracks and a synthetic floor map)."""
import time

from crosscam import ELIM_PASSES, STABLE_PASSES, CrossCam, FloorMap
from vision import Labeler, Track

W, H = 1000, 1000
# picture (0-1) -> floor: 10 m x 10 m room, identity-like map
FLOOR = FloorMap([{"px": [0, 0], "floor": [0, 0]}, {"px": [1, 0], "floor": [10, 0]},
                  {"px": [1, 1], "floor": [10, 10]}, {"px": [0, 1], "floor": [0, 10]}])


def box_at(x_m, y_m):          # a person standing at (x, y) metres -> box whose feet are there
    return (x_m * 100 - 40, y_m * 100 - 200, 80, 200)


def peer(now, *tracks, calibrated=True):
    return {"t": now, "calibrated": calibrated, "tracks": [
        {"id": i, "floor": [x, y], "label": lab, "name": lab, "role": "STUDENT", "source": src,
         "state": st, "crowded": cr} for i, x, y, lab, src, st, cr in tracks]}


def run(cc, tracks, lab, peer_fn, passes, t0=1000.0):
    for k in range(passes):
        now = t0 + k * 0.2
        cc.peer = peer_fn(now)
        cc.share(tracks, W, H, now, lab)


def test_confirmed_name_crosses_after_stable_passes_only():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    pf = lambda now: peer(now, (7, 3.1, 4.0, "USER1", "door", "CONFIRMED", False))
    run(cc, [t], lab, pf, STABLE_PASSES - 1)
    assert t.label is None                          # not yet: pairing must hold
    run(cc, [t], lab, pf, 1, t0=2000.0)
    assert t.label == "USER1" and t.source == "peer"


def test_last_unnamed_person_gets_the_last_free_name():
    # 2026-11-03 lab: Nour named on both cameras; Ali named by face on camera 2 but sitting at its bottom
    # edge (no floor position) - camera 1 names him by elimination, after the same stable passes.
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    nour, ali = Track(1, box_at(3, 4), 0, 0, hits=10), Track(2, box_at(7, 8), 0, 0, hits=10)
    nour.label = "USER6"
    pf = lambda now: {"t": now, "calibrated": True, "tracks": [
        {"id": 8, "floor": [3.05, 4.0], "label": "USER6", "name": "USER6", "role": "STUDENT", "source": "face",
         "state": "CONFIRMED", "crowded": False},
        {"id": 9, "floor": None, "label": "USER1", "name": "USER1", "role": "STUDENT", "source": "face",
         "state": "CONFIRMED", "crowded": False}]}
    # 2026-11-11: the head count alone names nobody (it would name a visitor in the blind spot just as well)
    seen_notes = []
    for k in range(ELIM_PASSES + 4):
        now = 1000.0 + k * 0.2
        cc.peer = pf(now)
        seen_notes += cc.share([nour, ali], W, H, now, lab)
    assert ali.label is None and nour.label == "USER6"
    assert [n["kind"] for n in seen_notes].count("CROSSCAM_AMBIGUOUS") == 1      # said once, not every pass


def _elim_case(my_look, their_look):
    import types as _t
    import numpy as _np

    def v(*w):
        a = _np.array(list(w) + [0.0] * (8 - len(w)), _np.float32)
        return a / _np.linalg.norm(a)
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    nour, ali = Track(1, box_at(3, 4), 0, 0, hits=10), Track(2, box_at(7, 8), 0, 0, hits=10)
    nour.label = "USER6"
    nour.look, ali.look = _t.SimpleNamespace(deep=v(0, 0, 1)), _t.SimpleNamespace(deep=v(*my_look))
    pf = lambda now: {"t": now, "calibrated": True, "tracks": [
        {"id": 8, "floor": [3.05, 4.0], "label": "USER6", "name": "USER6", "role": "STUDENT", "source": "face",
         "state": "CONFIRMED", "crowded": False, "deep": [float(x) for x in v(0, 0, 1)]},
        {"id": 9, "floor": None, "label": "USER1", "name": "USER1", "role": "STUDENT", "source": "face",
         "state": "CONFIRMED", "crowded": False, "deep": [float(x) for x in v(*their_look)]}]}
    return cc, lab, nour, ali, pf


def test_last_unnamed_person_gets_the_last_free_name_when_the_look_agrees(monkeypatch):
    # the 2026-11-03 case itself: Ali at camera 2's bottom edge (no floor position), same look on both cameras
    import crosscam as _cc
    monkeypatch.setattr(_cc, "HANDOFF", "off")             # this test is about the elimination rule alone
    cc, lab, nour, ali, pf = _elim_case((1,), (1, 0.3))
    run(cc, [nour, ali], lab, pf, ELIM_PASSES - 1)
    assert ali.label is None
    run(cc, [nour, ali], lab, pf, 1, t0=1000.0 + (ELIM_PASSES - 1) * 0.2)
    assert ali.label == "USER1" and nour.label == "USER6"


def test_elimination_refuses_a_different_looking_person():
    # same head count, one free name - but the unnamed person here does not look like that person there
    cc, lab, nour, ali, pf = _elim_case((1,), (0, 1))
    run(cc, [nour, ali], lab, pf, ELIM_PASSES + 4)
    assert ali.label is None


def test_not_shared_without_floor_map_or_when_stale():
    lab = Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    cc = CrossCam(None, "k", None)
    run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", "door", "CONFIRMED", False)), 10)
    assert t.label is None
    cc = CrossCam(None, "k", FLOOR)
    run(cc, [t], lab, lambda now: peer(now - 5, (7, 3, 4, "USER1", "door", "CONFIRMED", False)), 10)
    assert t.label is None


def test_unconfirmed_or_guessed_names_do_not_travel():
    for src, st in (("door", "CANDIDATE"), ("desk", "CONFIRMED"), ("look", "CONFIRMED")):
        cc, lab = CrossCam(None, "k", FLOOR), Labeler()
        t = Track(1, box_at(3, 4), 0, 0, hits=10)
        run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", src, st, False)), 10)
        assert t.label is None, (src, st)


def test_two_people_side_by_side_are_not_named_by_the_floor_alone():
    # 2026-11-03 lab: with two people in view and no measured look, the floor moved Nour's name onto Ali.
    # Now nobody gets a name that way - each person's own face (or a clear look) must name them.
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    a, b = Track(1, box_at(3.0, 4), 0, 0, hits=10), Track(2, box_at(3.6, 4), 0, 0, hits=10)
    pf = lambda now: peer(now, (8, 3.62, 4.0, "USER2", "face", "CONFIRMED", False),
                          (7, 3.02, 4.0, "USER1", "door", "CONFIRMED", False))
    run(cc, [b, a], lab, pf, 10)
    assert a.label is None and b.label is None


def test_crowded_or_conflicting_or_face_contradicted_never_changes():
    lab = Labeler()
    cc = CrossCam(None, "k", FLOOR)
    t = Track(1, box_at(3, 4), 0, 0, hits=10, crowded=True)
    run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", "door", "CONFIRMED", False)), 10)
    assert t.label is None                          # touching someone: wait
    t2 = Track(2, box_at(5, 5), 0, 0, hits=10, label="USER2", name="Nour", source="door")
    run(cc, [t2], lab, lambda now: peer(now, (9, 5, 5, "USER1", "door", "CONFIRMED", False)), 10)
    assert t2.label == "USER2"                      # conflict: nothing changes
    assert any(n["kind"] == "CROSSCAM_CONFLICT" for n in cc.notes)
    t3 = Track(3, box_at(6, 6), 0, 0, hits=10)
    lab.face_vote(3, "USER2", time.time()); lab.face_vote(3, "USER2", time.time())
    run(cc, [t3], lab, lambda now: peer(now, (4, 6, 6, "USER1", "door", "CONFIRMED", False)), 10)
    assert t3.label is None                         # its own face says someone else


def test_name_already_on_someone_here_is_not_duplicated():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    have = Track(1, box_at(1, 1), 0, 0, hits=10, label="USER1", name="Ali", source="door")
    t = Track(2, box_at(5, 5), 0, 0, hits=10)
    run(cc, [have, t], lab, lambda now: peer(now, (7, 5, 5, "USER1", "door", "CONFIRMED", False)), 10)
    assert t.label is None


def test_far_apart_is_not_the_same_person():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    run(cc, [t], lab, lambda now: peer(now, (7, 4.5, 4, "USER1", "door", "CONFIRMED", False)), 10)
    assert t.label is None                          # 1.5 m away > gate



def test_states_the_identity_ledger_really_produces_are_shared_and_doubtful_ones_are_not():
    """2026-10-18: the shared states must be the ledger's own (DOOR_CONFIRMED ...), not made-up ones."""
    from identity import STATES
    from crosscam import SHARE_STATES
    assert {"DOOR_CONFIRMED", "FACE_CONFIRMED", "FUSED_CONFIRMED", "REID_CONFIRMED"} <= SHARE_STATES
    assert not ({"UNKNOWN", "TENTATIVE", "OCCLUDED", "IDENTITY_UNCERTAIN", "IDENTITY_CONFLICT"} & SHARE_STATES)
    assert {"DOOR_CONFIRMED", "FUSED_CONFIRMED"} <= set(STATES)
    for st, shared in (("DOOR_CONFIRMED", True), ("IDENTITY_UNCERTAIN", False), ("IDENTITY_CONFLICT", False)):
        cc, lab = CrossCam(None, "k", FLOOR), Labeler()
        t = Track(1, box_at(3.0, 4.0), 0.0, 0.0)
        run(cc, [t], lab, lambda now: peer(now, (7, 3.0, 4.0, "USER1", "door", st, False)), 10)
        assert (t.label == "USER1") is shared, st


def test_elimination_refuses_people_far_apart_on_the_floor():
    # Gemini ACT-06: same head count, but the free person here stands 7 m from the free name there -
    # two different people in each camera's blind spot; no name by elimination.
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    nour, other = Track(1, box_at(3, 4), 0, 0, hits=10), Track(2, box_at(7, 8), 0, 0, hits=10)
    nour.label = "USER6"
    pf = lambda now: peer(now, (8, 3.05, 4.0, "USER6", "face", "CONFIRMED", False),
                          (9, 2.0, 2.0, "USER1", "face", "CONFIRMED", False))
    run(cc, [nour, other], lab, pf, ELIM_PASSES + 2)
    assert other.label is None


# ---------------------------------------------------------------- handoff (2026-11-10) ---
# The name of a person the other camera confirmed crosses on a CLEAR look when the floor cannot carry it:
# feet hidden in either view, or the person has already left the other view. SIMULATED looks (unit vectors).
import types

import numpy as np

import crosscam
from crosscam import HANDOFF_PASSES, HANDOFF_S


def look(*weights):                     # a unit "appearance" vector; equal weights = the same look
    v = np.zeros(8, np.float32)
    v[:len(weights)] = weights
    return v / np.linalg.norm(v)


ALI, NOUR, ALMOST_ALI = look(1), look(0, 1), look(1, 0.75)       # ALI-ALMOST_ALI 0.17, ALI-NOUR 0.83
CUT = (400, 700, 80, 300)               # box touching the bottom of the picture: feet not seen, no floor position


def person(tid, box, deep, label=None):
    t = Track(tid, box, 0, 0, hits=10)
    t.look = types.SimpleNamespace(deep=deep)
    t.label = label
    return t


def seen(now, *people):                 # (id, floor or None, label, deep[, source, state, crowded])
    out = []
    for q in people:
        i, floor, lab, deep = q[:4]
        src, st, cr = (list(q[4:]) + ["face", "CONFIRMED", False][len(q) - 4:])
        out.append({"id": i, "floor": floor, "desk": None, "label": lab, "name": lab, "role": "STUDENT",
                    "source": src, "state": st, "crowded": cr, "deep": [float(x) for x in deep]})
    return {"t": now, "calibrated": True, "tracks": out}


def test_handoff_feet_hidden_in_both_views():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = person(1, CUT, ALI)
    pf = lambda now: seen(now, (7, None, "USER1", ALI))
    run(cc, [t], lab, pf, HANDOFF_PASSES - 1)
    assert t.label is None                                      # the look must hold first
    run(cc, [t], lab, pf, 1, t0=1000.0 + (HANDOFF_PASSES - 1) * 0.2)
    assert t.label == "USER1" and t.source == "peer"
    assert cc.notes[-1]["kind"] == "CROSSCAM_HANDOFF"


def test_handoff_after_the_person_left_the_other_view():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)          # camera 1 confirmed USER1
    t = person(1, box_at(4, 5), ALI)                                                    # 10 s later, on camera 2
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES, t0=1010.0)                 # camera 1 sees nobody now
    assert t.label == "USER1"
    assert "last seen there" in cc.notes[-1]["detail"]


def test_handoff_upper_body_only_after_leaving():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)
    t = person(1, CUT, ALMOST_ALI)                              # partial body: a slightly different look, no feet
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES, t0=1020.0)
    assert t.label == "USER1"


def test_handoff_refuses_a_different_look():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)
    t = person(1, CUT, NOUR)
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES + 5, t0=1010.0)
    assert t.label is None


def test_handoff_refuses_when_two_remembered_people_look_alike():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI), (8, [6.0, 4.0], "USER6", ALMOST_ALI)), 3)
    t = person(1, CUT, ALI)
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES + 5, t0=1010.0)
    assert t.label is None                                      # similar clothing: nobody is named


def test_handoff_refuses_when_two_people_here_look_alike():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)
    a, b = person(1, CUT, ALI), person(2, box_at(7, 8), ALMOST_ALI)
    run(cc, [a, b], lab, lambda now: seen(now), HANDOFF_PASSES + 5, t0=1010.0)
    assert a.label is None and b.label is None


def test_handoff_names_the_right_one_of_two_different_people():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI), (8, [6.0, 4.0], "USER6", NOUR)), 3)
    a, b = person(1, CUT, NOUR), person(2, box_at(7, 8), ALI)
    run(cc, [a, b], lab, lambda now: seen(now), HANDOFF_PASSES, t0=1010.0)
    assert a.label == "USER6" and b.label == "USER1"


def test_handoff_refuses_a_place_too_far_to_have_walked_to():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [1.0, 1.0], "USER1", ALI)), 3)
    t = person(1, box_at(7.5, 9.5), ALI)                        # 10.7 m away, 1 to 4 s later
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES + 3, t0=1001.0)
    assert t.label is None
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES, t0=1020.0)      # 20 s later it is walkable
    assert t.label == "USER1"


def test_handoff_forgets_after_handoff_s():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)
    t = person(1, CUT, ALI)
    run(cc, [t], lab, lambda now: seen(now), HANDOFF_PASSES + 5, t0=1000.0 + HANDOFF_S + 5)
    assert t.label is None and not cc.seen


def test_handoff_never_takes_a_name_already_here_or_an_unconfirmed_one():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [], lab, lambda now: seen(now, (7, [3.0, 4.0], "USER1", ALI)), 3)
    named, t = person(1, box_at(7, 8), NOUR, label="USER1"), person(2, CUT, ALI)
    run(cc, [named, t], lab, lambda now: seen(now), HANDOFF_PASSES + 5, t0=1010.0)
    assert t.label is None                                      # USER1 is already on someone in this view
    for extra in (("desk", "CONFIRMED", False), ("door", "CANDIDATE", False), ("face", "CONFIRMED", True)):
        cc, t = CrossCam(None, "k", FLOOR), person(3, CUT, ALI)
        run(cc, [t], lab, lambda now: seen(now, (7, None, "USER1", ALI) + extra), HANDOFF_PASSES + 5)
        assert t.label is None and not cc.seen, extra           # guessed, unconfirmed or crowded there


def test_handoff_not_for_a_crowded_track_or_a_silent_peer():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = person(1, CUT, ALI)
    t.crowded = True
    run(cc, [t], lab, lambda now: seen(now, (7, None, "USER1", ALI)), HANDOFF_PASSES + 5)
    assert t.label is None
    t.crowded = False
    run(cc, [t], lab, lambda now: seen(now - 5, (7, None, "USER1", ALI)), HANDOFF_PASSES + 5, t0=2000.0)
    assert t.label is None                                      # the other camera's answer is 5 s old


def test_handoff_observe_mode_logs_and_changes_nothing(monkeypatch):
    monkeypatch.setattr(crosscam, "HANDOFF", "observe")
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = person(1, CUT, ALI)
    said = []
    for k in range(HANDOFF_PASSES + 3):
        now = 1000.0 + k * 0.2
        cc.peer = seen(now, (7, None, "USER1", ALI))
        said += [n["kind"] for n in cc.share([t], W, H, now, lab)]
    assert t.label is None and said == ["CROSSCAM_HANDOFF_OBSERVED"]
    monkeypatch.setattr(crosscam, "HANDOFF", "off")
    cc = CrossCam(None, "k", FLOOR)
    run(cc, [t], lab, lambda now: seen(now, (7, None, "USER1", ALI)), HANDOFF_PASSES + 3)
    assert t.label is None and not cc.seen
