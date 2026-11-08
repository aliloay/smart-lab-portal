---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_identity_lock.py"
source_hash: "b0d7be85848a161b2d3a1691694114924b1256b776a9aa832f9834666d276763"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_identity_lock.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_vision.py]] - tests

```py
"""
Identity-lock regressions (SIMULATED: synthetic boxes, no camera). They prove the
association / naming rules, not real-world recognition accuracy.

Root causes fixed 2026-10-15:
  1. Tracker matched boxes to tracks greedily (best pair first): two people walking side by
     side could lose a track (new id, name gone) or swap - now one optimal assignment per frame.
  2. A name could be given by elimination ("one free name, one unnamed person") or handed back
     by place alone (a small box where a named person vanished) - both are guesses; now off.
"""
import itertools

from vision import Labeler, Track, Tracker, assign_max


def test_assign_max_beats_greedy():
    # greedy takes (1,0)=0.67 and leaves track 0 unmatched; the optimum matches both
    score = [[0.43, None], [0.67, 0.33]]
    assert sorted(assign_max(score)) == [(0, 0), (1, 1)]


def test_assign_max_is_optimal_on_random_small_matrices():
    import random
    rnd = random.Random(7)
    for _ in range(200):
        n, m = rnd.randint(1, 4), rnd.randint(1, 4)
        s = [[(rnd.random() if rnd.random() > 0.3 else None) for _ in range(m)] for _ in range(n)]
        got = sum(s[i][j] for i, j in assign_max(s))
        best = 0.0
        for perm in itertools.permutations(range(m), min(n, m)):
            for rows in itertools.combinations(range(n), min(n, m)):
                v = sum(s[i][j] for i, j in zip(rows, perm) if s[i][j] is not None)
                best = max(best, v)
        assert abs(got - best) < 1e-9


def _two_side_by_side():
    tr = Tracker()
    a, b = (0, 0, 100, 200), (60, 0, 100, 200)
    for k in range(4):
        tr.update([a, b], now=k * 0.1)
    ids = {t.box[0]: t.id for t in tr.tracks}
    return tr, ids[0], ids[60]


def test_side_by_side_people_keep_their_tracks():
    tr, ida, idb = _two_side_by_side()
    # both step right by ~45 px; greedy gave b1 to B and made a NEW track for b2
    tr.update([(40, 0, 100, 200), (110, 0, 100, 200)], now=0.4)
    by = {t.id: t.box for t in tr.tracks if t.last_seen == 0.4}
    assert by.get(ida) == (40, 0, 100, 200)
    assert by.get(idb) == (110, 0, 100, 200)
    assert len(tr.tracks) == 2                    # no new id


def test_detection_order_does_not_change_tracks():
    for order in ([(40, 0, 100, 200), (110, 0, 100, 200)], [(110, 0, 100, 200), (40, 0, 100, 200)]):
        tr, ida, idb = _two_side_by_side()
        tr.update(order, now=0.4)
        by = {t.id: t.box for t in tr.tracks if t.last_seen == 0.4}
        assert by[ida][0] == 40 and by[idb][0] == 110


def _track(i, box, now, **kw):
    t = Track(i, box, now - 5, now, hits=10)
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_no_name_by_elimination():
    lab = Labeler()
    now = 1000.0
    occupants = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": now - 60}]
    t = _track(1, (300, 100, 80, 200), now)      # one unnamed person, one free fresh name
    lab.assign([t], occupants, door_rect=None, now=now)
    assert t.label is None                        # not "must be them"


def test_no_name_back_by_place_alone():
    lab = Labeler()
    now = 1000.0
    occ = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": now - 30}]
    named = _track(1, (300, 100, 40, 60), now, label="USER1", name="Ali", source="door")
    lab.assign([named], occ, door_rect=None, now=now)
    # the named (small, seated) track vanishes; a NEW small box appears at the same place
    newcomer = Track(2, (302, 101, 40, 60), now + 1.0, now + 1.0, hits=5)
    lab.assign([newcomer], occ, door_rect=None, now=now + 1.0)
    assert newcomer.label is None                 # someone else may sit there


def test_confirmed_name_survives_short_occlusion_on_same_track():
    lab = Labeler()
    now = 1000.0
    occ = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": now - 30}]
    t = _track(1, (300, 100, 80, 200), now, label="USER1", name="Ali", source="door")
    lab.assign([t], occ, None, now)
    t.crowded = True                              # someone passes in front
    lab.assign([t], occ, None, now + 0.5)
    t.crowded = False
    lab.assign([t], occ, None, now + 1.0)
    assert t.label == "USER1"


def test_a_weak_single_face_vote_never_overwrites_a_confirmed_name():
    lab = Labeler()
    now = 1000.0
    occ = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": now - 30},
           {"auth_subject": "USER2", "name": "Nour", "role": "STUDENT", "entered_at": now - 30}]
    t = _track(1, (300, 100, 80, 200), now, label="USER1", name="Ali", source="door")
    lab.assign([t], occ, None, now)
    lab.face_vote(1, "USER2", now + 0.2, 0.40)    # one vote for someone else
    lab.assign([t], occ, None, now + 0.3)
    assert t.label == "USER1"

```
