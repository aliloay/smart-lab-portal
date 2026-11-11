"""Look guess (2026-11-11, owner: "after a restart I am Unknown again"). SIMULATED looks.

A person this camera named before comes back from the stored look as a MARKED GUESS (source "look"): never a
confirmed name, never shared with the other camera, never learnt from, confirmed only by the face."""
import os
import tempfile

import numpy as np

import vision
from crosscam import SHARE_SOURCES
from vision import Identity, Labeler, Look, Track, _person_label

N = Labeler.LOOK_GUESS_PASSES
BOX = (400, 100, 100, 260)                 # upright, big enough to judge


def unit(*w):
    v = np.zeros(16, np.float32)
    v[:len(w)] = w
    return v / np.linalg.norm(v)


def colour(seed):
    rng = np.random.default_rng(seed)
    return np.concatenate([rng.dirichlet(np.full(16, 1.0)) for _ in range(3)]).astype(np.float32)


ALI, NOUR = Look(colour(1), unit(1)), Look(colour(2), unit(0, 1))
WHO = {"USER1": {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"},
       "USER6": {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT"}}


def labeler_knowing(*labels, now=1000.0):
    lab = Labeler()
    for label in labels:
        lab.identities[label] = Identity(ALI if label == "USER1" else NOUR, Labeler.LOCK_SAMPLES + 2)
        lab.face_named[label] = (WHO[label], now)
    return lab


def person(tid, look, box=BOX, t=1000.0):
    return Track(tid, box, t, t, hits=10, look=look)


def run(lab, tracks, passes, t0=1000.0, occupants=()):
    for k in range(passes):
        now = t0 + k * 0.15
        for t in tracks:
            t.last_seen = now
        lab.assign(tracks, list(occupants), None, now)


def test_name_comes_back_as_a_marked_guess_after_the_passes():
    lab, t = labeler_knowing("USER1"), person(1, ALI)
    run(lab, [t], N - 1)
    assert t.label is None                                   # the look must hold first
    run(lab, [t], 2, t0=1000.0 + (N - 1) * 0.15)
    assert t.label == "USER1" and t.source == "look" and t.named_by == "look"
    assert t.identity_state == "IDENTITY_UNCERTAIN"          # a guess, shown with "?"
    assert "? (look)" in _person_label(t)
    assert "look" not in SHARE_SOURCES                       # never travels to the other camera


def test_a_restart_keeps_the_candidates_and_still_only_guesses():
    lab = labeler_knowing("USER1", now=1000.0)
    path = os.path.join(tempfile.mkdtemp(), "ids.npz")
    lab.save(path)
    fresh = Labeler()
    assert fresh.load(path, 1060.0) == 1 and "USER1" in fresh.face_named     # one minute later: a candidate
    t = person(1, ALI, t=1060.0)
    run(fresh, [t], N + 1, t0=1060.0)
    assert t.label == "USER1" and t.source == "look"
    stale = Labeler()
    stale.load(path, 1000.0 + Labeler.FACE_KEEP_S + 60)                       # long after: forgotten
    assert "USER1" not in stale.face_named


def test_a_different_looking_person_is_not_guessed():
    lab, t = labeler_knowing("USER1"), person(1, NOUR)
    run(lab, [t], N + 5)
    assert t.label is None


def test_two_stored_people_who_look_alike_give_no_guess():
    lab = labeler_knowing("USER1", "USER6")
    lab.identities["USER6"] = Identity(Look(ALI.color.copy(), unit(1, 0.2)), Labeler.LOCK_SAMPLES + 2)
    t = person(1, ALI)
    run(lab, [t], N + 5)
    assert t.label is None                                   # could be either: stays Unknown


def test_two_unnamed_people_who_both_fit_give_no_guess():
    lab = labeler_knowing("USER1")
    a, b = person(1, ALI, (100, 100, 100, 260)), person(2, Look(ALI.color.copy(), unit(1, 0.15)), (700, 100, 100, 260))
    run(lab, [a, b], N + 5)
    assert a.label is None and b.label is None


def test_small_crouching_or_touching_people_are_not_guessed():
    for box in ((400, 100, 30, 70), (400, 100, 260, 100)):   # too small to judge / not upright
        lab, t = labeler_knowing("USER1"), person(1, ALI, box)
        run(lab, [t], N + 5)
        assert t.label is None, box
    lab, t = labeler_knowing("USER1"), person(1, ALI)
    t.crowded = True
    run(lab, [t], N + 5)
    assert t.label is None


def test_the_face_confirms_or_drops_the_guess():
    lab, t = labeler_knowing("USER1", "USER6"), person(1, ALI)
    run(lab, [t], N + 1)
    assert t.source == "look"
    now = 1000.0 + (N + 1) * 0.15
    lab.face_vote(1, "USER1", now)
    lab.face_vote(1, "USER1", now)
    lab.assign([t], [], None, now, known=list(WHO.values()))
    assert t.label == "USER1" and t.source == "face"         # confirmed by this camera's face
    lab2, t2 = labeler_knowing("USER1", "USER6"), person(1, ALI)
    run(lab2, [t2], N + 1)
    lab2.face_vote(1, "USER6", now)
    lab2.face_vote(1, "USER6", now)
    lab2.assign([t2], [], None, now, known=list(WHO.values()))
    assert t2.label != "USER1"                               # the face says someone else: the guess is gone


def test_a_guess_never_teaches_the_stored_look():
    lab, t = labeler_knowing("USER1"), person(1, ALI)
    run(lab, [t], N + 1)
    before = lab.identities["USER1"].samples
    run(lab, [t], 20, t0=1100.0)
    assert t.source == "look" and lab.identities["USER1"].samples == before


def test_off_and_observe_modes_change_nothing(monkeypatch):
    for mode in ("off", "observe"):
        monkeypatch.setattr(Labeler, "LOOK_GUESS", mode)
        lab, t = labeler_knowing("USER1"), person(1, ALI)
        run(lab, [t], N + 5)
        assert t.label is None, mode
    assert vision.Labeler.LOOK_GUESS in ("off", "observe")
