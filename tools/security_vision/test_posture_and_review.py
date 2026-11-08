"""2026-10-18: a person keeps their track through posture changes, and identity decisions that staff
should check are flagged (PERSON_IDENTITY_REVIEW) - never silent. Simulated boxes and looks."""
import numpy as np

from identity import IdentityLedger
from vision import Labeler, Look, Track, Tracker, upright


def look(seed):
    rng = np.random.default_rng(seed)
    c = rng.random(48).astype(np.float32)
    parts = [c[i * 16:(i + 1) * 16] / c[i * 16:(i + 1) * 16].sum() for i in range(3)]
    d = rng.normal(size=64).astype(np.float32)
    return Look(np.concatenate(parts), d / np.linalg.norm(d))


STAND = (300, 100, 100, 250)          # feet at (350, 350)
LIE = (230, 255, 250, 95)             # same spot, on the floor: feet at (355, 350)
CROUCH = (290, 200, 110, 150)


def _feed(tr, boxes_per_step, looks_per_step, t0=0.0, dt=0.15):
    out = None
    for i, (bs, ls) in enumerate(zip(boxes_per_step, looks_per_step)):
        out = tr.update(bs, t0 + i * dt, ls)
    return out


def test_lying_down_and_standing_up_keeps_the_same_track():
    tr = Tracker()
    a = look(1)
    stand_look, lie_look = a, look(2)                     # the colours change when lying down
    steps = [[STAND]] * 5 + [[LIE]] * 8 + [[CROUCH]] * 3 + [[STAND]] * 5
    looks = [[stand_look]] * 5 + [[lie_look]] * 8 + [[lie_look]] * 3 + [[stand_look]] * 5
    _feed(tr, steps, looks)
    assert len(tr.tracks) == 1 and tr.tracks[0].id == 1
    assert tr.tracks[0].posture_changed_at > -1e9


def test_posture_join_needs_a_unique_pair():
    """Two new boxes where one person was: no guess, the person's track is not continued by either."""
    tr = Tracker()
    a = look(1)
    _feed(tr, [[STAND]] * 5, [[a]] * 5)
    left, right = (215, 270, 130, 80), (330, 270, 130, 80)  # two low boxes around the same feet
    tr.update([left, right], 0.75, [look(3), look(4)])
    assert all(t.box in (left, right) and t.id != 1 for t in tr.tracks if t.last_seen == 0.75)


def test_clearly_different_look_is_not_joined_across_a_posture_change():
    tr = Tracker()
    me = look(1)
    _feed(tr, [[STAND]] * 5, [[me]] * 5)
    other = Look(1.0 - me.color + 1e-3, -me.deep)             # nothing alike
    other.color = other.color / other.color.reshape(3, -1).sum(1).repeat(16)
    tr.update([LIE], 0.75, [other])
    assert [t.id for t in tr.tracks if t.last_seen == 0.75] != [1]


def test_upright_helper():
    assert upright(STAND) and not upright(LIE) and not upright((0, 0, 100, 110))


def test_a_lying_person_does_not_change_or_veto_the_locked_look():
    lab = Labeler()
    t = Track(1, STAND, 0.0, 0.0)
    occ = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": 0.0}]
    Labeler._give(t, occ[0], "door")
    t.look = look(1)
    for i in range(6):                                    # learnt while standing alone
        lab.assign([t], occ, None, now=1.0 + i)
    locked = lab.identities["USER1"].look.color.copy()
    samples = lab.identities["USER1"].samples
    t.box, t.look = (100, 300, 300, 170), look(9)         # lying, very different colours, big box
    for i in range(20):
        lab.assign([t], occ, None, now=10.0 + i * 0.25)
    assert t.label == "USER1"                             # no veto from a lying view
    assert lab.identities["USER1"].samples == samples and np.allclose(lab.identities["USER1"].look.color, locked)


def test_a_name_on_two_people_is_flagged_for_review():
    lab = Labeler()
    occ = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": 0.0}]
    a, b = Track(1, (100, 100, 80, 200), 0.0, 5.0), Track(2, (400, 100, 80, 200), 3.0, 5.0)
    Labeler._give(a, occ[0], "door")
    Labeler._give(b, occ[0], "door")
    lab.assign([a, b], occ, None, now=5.0)
    assert [t.label for t in (a, b)].count("USER1") == 1
    assert any(e.kind == "PERSON_IDENTITY_REVIEW" and e.label == "USER1" for e in lab.events)


def test_a_crossing_re_deal_is_flagged_and_starts_at_look_confidence_not_door():
    lab = Labeler()
    occ = [{"auth_subject": "U1", "name": "One", "role": "STUDENT", "entered_at": 0.0},
           {"auth_subject": "U2", "name": "Two", "role": "STUDENT", "entered_at": 0.0}]
    l1, l2 = look(11), look(22)
    a, b = Track(1, (100, 100, 80, 200), 0.0, 0.0), Track(2, (500, 100, 80, 200), 0.0, 0.0)
    Labeler._give(a, occ[0], "door")
    Labeler._give(b, occ[1], "door")
    a.look, b.look = l1, l2
    for i in range(5):                                    # both looks locked while apart
        a.last_seen = b.last_seen = 1.0 + i
        lab.assign([a, b], occ, None, now=1.0 + i)
    # they touch, the tracker mixes them up, they come apart: track 1 now looks like U2 and vice versa
    a.look, b.look = l2, l1
    a.separated_at = b.separated_at = 10.0
    a.last_seen = b.last_seen = 11.0
    lab.assign([a, b], occ, None, now=11.0)
    assert a.label == "U2" and b.label == "U1"            # names went back to their looks
    assert any(e.kind == "PERSON_IDENTITY_REVIEW" for e in lab.events)
    rec = lab.ledger.records[a.id]
    crossing = [e for e in rec.evidence if e.kind == "crossing"][-1]
    assert crossing.score == lab.ledger.cfg.reacquire_strength      # look-level, not the door's 0.90


def test_ledger_treats_other_camera_names_as_reacquired():
    led = IdentityLedger()
    t = Track(3, STAND, 0.0, 0.0)
    t.label, t.source, t.named_by = "U1", "peer", "other camera"
    ev = led.update([t], 1.0)
    assert ev[0].kind == "PERSON_TRACK_REACQUIRED" and t.identity_confidence <= led.cfg.reacquire_strength
