"""2026-10-21 lab: Ali (standing) and Nour (seated) 0.6 m apart at the UR5e. Camera 1's Ali landed 0.24 m from
camera 2's Nour, so the two floor pairings scored the same and Nour's name never reached camera 1. Their looks
differ (measured: same person ~0.31, different people ~0.79): the look breaks the tie. SIMULATED."""
import numpy as np

import crosscam
from crosscam import STABLE_PASSES, CrossCam, FloorMap
from vision import Labeler, Look, Track

W, H = 1000, 1000
FLOOR = FloorMap([{"px": [0, 0], "floor": [0, 0]}, {"px": [1, 0], "floor": [10, 0]},
                  {"px": [1, 1], "floor": [10, 10]}, {"px": [0, 1], "floor": [0, 10]}])
GREEN, BLACK = np.eye(8, dtype=np.float32)[0], np.eye(8, dtype=np.float32)[1]


def box_at(x, y):
    return (x * 100 - 40, y * 100 - 200, 80, 200)


def track(i, x, y, deep):
    t = Track(i, box_at(x, y), 0, 0, hits=10)
    t.look = Look(np.zeros(3, np.float32))
    t.look.deep = deep
    return t


def peer(now, *tr):
    return {"t": now, "calibrated": True, "tracks": [
        {"id": i, "floor": [x, y], "label": lab, "name": lab, "role": "STUDENT", "source": "face",
         "state": "FACE_CONFIRMED", "crowded": False, "deep": [float(v) for v in deep]} for i, x, y, lab, deep in tr]}


def run(cc, mine, lab, pf, passes=STABLE_PASSES + 2):
    for k in range(passes):
        cc.peer = pf(1000.0 + 0.2 * k)
        cc.share(mine, W, H, 1000.0 + 0.2 * k, lab)


def test_the_look_breaks_a_floor_tie_the_right_way():
    # live (18:18): here Ali (3.88, 3.91), Nour (4.62, 4.09); there Ali (3.75, 4.31) = USER1, Nour (4.11, 3.99) =
    # USER6. Ali here shifted 0.1 m (detector noise): then the floor alone prefers Ali-here = Nour-there.
    ali, nour = track(1, 3.95, 3.95, GREEN), track(2, 4.62, 4.09, BLACK)
    pf = lambda now: peer(now, (7, 3.75, 4.31, "USER1", GREEN), (8, 4.11, 3.99, "USER6", BLACK))
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [ali, nour], lab, pf)
    assert (ali.label, nour.label) == ("USER1", "USER6")


def test_without_the_tie_break_the_same_scene_names_the_wrong_way_or_nobody(monkeypatch):
    monkeypatch.setattr(crosscam, "TIE_BREAK", False)
    monkeypatch.setattr(crosscam, "APPEARANCE", "observe")      # the floor alone
    ali, nour = track(1, 3.95, 3.95, GREEN), track(2, 4.62, 4.09, BLACK)
    pf = lambda now: peer(now, (7, 3.75, 4.31, "USER1", GREEN), (8, 4.11, 3.99, "USER6", BLACK))
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [ali, nour], lab, pf)
    assert (ali.label, nour.label) != ("USER1", "USER6")


def test_a_clear_look_pairs_up_to_the_wide_gate_only():
    t = track(1, 3.0, 4.0, GREEN)
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [t], lab, lambda now: peer(now, (7, 3.0 + crosscam.GATE_WIDE_M + 0.3, 4.0, "USER1", GREEN)))
    assert t.label is None                                   # beyond 2 m: never, however alike
    t2 = track(2, 3.0, 4.0, GREEN)
    run(cc, [t2], lab, lambda now: peer(now, (8, 4.2, 4.0, "USER1", GREEN)))   # 1.2 m, same look: paired
    assert t2.label == "USER1"


def test_two_people_who_look_alike_are_not_paired_by_look():
    a, b = track(1, 3.0, 4.0, GREEN), track(2, 3.3, 5.0, GREEN)              # twins in green
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    run(cc, [a, b], lab, lambda now: peer(now, (7, 4.4, 4.5, "USER1", GREEN)))  # both > 0.7 m away
    assert a.label is None and b.label is None
