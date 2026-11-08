"""Cross-camera fixes of 2026-10-19 (SIMULATED: synthetic tracks, synthetic floor map - same helpers as
test_crosscam.py). Lab cases: feet cut off by the picture edge gave positions of -45 m / 148 m; a desk
GUESS on camera 1 ("Eng. Hemaly ? (desk)") stayed on Ali while camera 2's face had confirmed Ali."""
from types import SimpleNamespace

import numpy as np

import crosscam
from crosscam import STABLE_PASSES, CrossCam, deep_distance, feet_floor, peer_view
from test_crosscam import FLOOR, H, W, box_at, peer, run
from vision import Labeler, Track


def test_feet_cut_off_by_the_picture_edge_give_no_position():
    t = Track(1, (400, 700, 100, 300), 0, 0, hits=10)        # bottom at 1000 = the frame bottom
    assert feet_floor(FLOOR, t.box, W, H) is None
    assert np.allclose(feet_floor(FLOOR, box_at(3, 4), W, H), (3.0, 4.0))


def test_position_outside_the_room_is_dropped():
    far = FloorMap_like = crosscam.FloorMap([{"px": [0, 0], "floor": [0, 0]}, {"px": [1, 0], "floor": [100, 0]},
                                             {"px": [1, 1], "floor": [100, 100]}, {"px": [0, 1], "floor": [0, 100]}])
    assert feet_floor(far, box_at(3, 4), W, H) is None        # 30 m, 40 m: not in the lab


def test_no_name_crosses_to_a_person_whose_feet_are_not_seen():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, (260, 700, 80, 300), 0, 0, hits=10)          # cut off at the bottom edge
    run(cc, [t], lab, lambda now: peer(now, (7, 3, 9.9, "USER1", "door", "DOOR_CONFIRMED", False)), 10)
    assert t.label is None


def test_confirmed_name_on_the_other_camera_replaces_a_desk_guess():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    Labeler._give(t, {"auth_subject": "USER5", "name": "Eng. Hemaly"}, "desk", how="desk")
    run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", "face", "FACE_CONFIRMED", False)), STABLE_PASSES)
    assert t.label == "USER1" and t.source == "peer"
    assert any(n["kind"] == "CROSSCAM_OVERRIDES_DESK_GUESS" for n in cc.notes)


def test_a_confirmed_name_is_never_replaced_only_logged():
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    Labeler._give(t, {"auth_subject": "USER5", "name": "Eng. Hemaly"}, "door")
    run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", "face", "FACE_CONFIRMED", False)), STABLE_PASSES + 2)
    assert t.label == "USER5"
    assert any(n["kind"] == "CROSSCAM_CONFLICT" for n in cc.notes)


def test_desk_guess_is_not_replaced_while_crowded_or_by_an_unconfirmed_name():
    for st, src, crowded in (("TENTATIVE", "face", False), ("FACE_CONFIRMED", "face", True)):
        cc, lab = CrossCam(None, "k", FLOOR), Labeler()
        t = Track(1, box_at(3, 4), 0, 0, hits=10)
        Labeler._give(t, {"auth_subject": "USER5", "name": "Eng. Hemaly"}, "desk", how="desk")
        run(cc, [t], lab, lambda now: peer(now, (7, 3, 4, "USER1", src, st, crowded)), STABLE_PASSES + 2)
        assert t.label == "USER5", (st, crowded)


def _deep(seed):
    v = np.random.default_rng(seed).normal(size=64).astype(np.float32)
    return v / np.linalg.norm(v)


def test_deep_distance_scale():
    a = _deep(1)
    assert deep_distance(a, a) == 0.0
    assert deep_distance(a, -a) == 1.0
    assert deep_distance(a, None) is None and deep_distance(a, a[:10]) is None


def test_peer_view_shares_the_embedding_and_no_position_for_cut_off_feet():
    t = Track(3, (400, 700, 100, 300), 0, 0, hits=10)
    t.look = SimpleNamespace(deep=_deep(2), color=None)
    v = peer_view([t], FLOOR, W, H, 5.0)["tracks"][0]
    assert v["floor"] is None and len(v["deep"]) == 64


def _peer_deep(now, x, y, label, deep):
    p = peer(now, (7, x, y, label, "face", "FACE_CONFIRMED", False))
    p["tracks"][0]["deep"] = list(map(float, deep))
    return p


def test_observe_mode_never_changes_a_decision(monkeypatch):
    monkeypatch.setattr(crosscam, "APPEARANCE", "observe")
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    t.look = SimpleNamespace(deep=_deep(1), color=None)
    run(cc, [t], lab, lambda now: _peer_deep(now, 3.0, 5.0, "USER1", _deep(1)), 10)   # 1.0 m apart
    assert t.label is None                                 # outside the 0.7 m gate: as before


def test_on_mode_same_look_bridges_a_wider_gap_but_different_look_vetoes(monkeypatch):
    monkeypatch.setattr(crosscam, "APPEARANCE", "on")
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    t.look = SimpleNamespace(deep=_deep(1), color=None)
    run(cc, [t], lab, lambda now: _peer_deep(now, 3.0, 5.0, "USER1", _deep(1)), STABLE_PASSES)
    assert t.label == "USER1"                              # 1.0 m, same look, nobody else
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    t.look = SimpleNamespace(deep=_deep(1), color=None)
    run(cc, [t], lab, lambda now: _peer_deep(now, 3.0, 4.1, "USER1", -_deep(1)), 10)
    assert t.label is None                                 # same spot, clearly another person


def test_on_mode_wide_gate_refuses_when_two_look_alikes_compete(monkeypatch):
    monkeypatch.setattr(crosscam, "APPEARANCE", "on")
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    t = Track(1, box_at(3, 4), 0, 0, hits=10)
    t.look = SimpleNamespace(deep=_deep(1), color=None)

    def two(now):
        p = _peer_deep(now, 3.0, 5.0, "USER1", _deep(1))
        q = _peer_deep(now, 4.0, 4.6, "USER6", _deep(1))["tracks"][0]
        q["id"] = 8
        p["tracks"].append(q)
        return p
    run(cc, [t], lab, two, 10)
    assert t.label is None                                 # similar clothes, both out of the tight gate


def test_peer_answers_from_the_future_or_too_old_are_ignored():
    """Both services stamp time.time() (epoch, time-zone free) on the same laptop; the camera's own
    overlay clock is never used. An answer stamped ahead (clock step) or stale must not share a name."""
    for shift in (+5.0, -5.0):
        cc, lab = CrossCam(None, "k", FLOOR), Labeler()
        t = Track(1, box_at(3, 4), 0, 0, hits=10)
        run(cc, [t], lab, lambda now: peer(now + shift, (7, 3, 4, "USER1", "door", "DOOR_CONFIRMED", False)), 10)
        assert t.label is None, shift
