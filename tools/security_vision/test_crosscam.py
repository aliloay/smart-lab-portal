"""Cross-camera name sharing (SIMULATED: synthetic tracks and a synthetic floor map)."""
import time

from crosscam import STABLE_PASSES, CrossCam, FloorMap
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


def test_two_people_side_by_side_get_their_own_names():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    a, b = Track(1, box_at(3.0, 4), 0, 0, hits=10), Track(2, box_at(3.6, 4), 0, 0, hits=10)
    # the other camera reports them in the opposite order
    pf = lambda now: peer(now, (8, 3.62, 4.0, "USER2", "face", "CONFIRMED", False),
                          (7, 3.02, 4.0, "USER1", "door", "CONFIRMED", False))
    run(cc, [b, a], lab, pf, 10)
    assert a.label == "USER1" and b.label == "USER2"


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
