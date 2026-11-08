---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_door_entry.py"
source_hash: "ab36c3196c063d3e03a0324e2c0142db85b19d13ead141ae2f34309a1a791591"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_door_entry.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_vision.py]] - tests

```py
"""Named at the door (lab 2026-10-14): the entry was recorded but nobody was named - the
detector first saw the person with the centre already past the narrow door box."""
from vision import Labeler, Track, at_door

DOOR = (72, 168, 48, 165)                       # the lab's door box in the 960x540 frame


def test_person_just_through_the_door_counts():
    assert at_door((115, 200, 70, 180), DOOR)       # centre at x 150: right of the box, overlapping the zone


def test_person_across_the_room_does_not():
    assert not at_door((356, 278, 81, 181), DOOR)


def test_new_person_at_the_door_gets_the_entrant_name_without_a_face():
    lab = Labeler()
    t = Track(7, (115, 200, 70, 180), 100.0, 100.0)
    other = Track(4, (600, 260, 70, 180), 20.0, 100.0)  # someone else in the room, unnamed
    ali = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 95.0}
    lab.assign([t, other], [ali], DOOR, now=100.0)
    assert t.label is None                          # 2026-10-18: waits ENTRY_SETTLE_S for anyone right behind
    lab.assign([t, other], [ali], DOOR, now=100.0 + Labeler.ENTRY_SETTLE_S)
    assert t.label == "USER1" and t.named_by == "door" and other.label is None


def test_someone_already_inside_is_not_named_by_a_new_entry():
    lab = Labeler()
    old = Track(3, (115, 200, 70, 180), 10.0, 100.0)    # in view since t=10, entry at 95
    other = Track(4, (600, 260, 70, 180), 20.0, 100.0)  # a 2nd unnamed person: no naming by elimination
    ali = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 95.0}
    lab.assign([old, other], [ali], DOOR, now=100.0)
    assert old.label is None and other.label is None


def test_elimination_ignores_an_entry_from_hours_ago_nobody_has_seen_since():
    """Live 2026-10-14: test entries are never closed by an exit; USER2 entered 2.2 h earlier and
    was never seen - elimination would have named a stranger USER2."""
    lab = Labeler()
    stranger = Track(9, (600, 260, 70, 180), 7900.0, 8000.0)
    old = {"auth_subject": "USER2", "name": "Old Entry", "role": "STUDENT", "entered_at": 0.0}
    lab.assign([stranger], [old], DOOR, now=8000.0)
    assert stranger.label is None


def test_no_elimination_even_for_a_recent_entry():
    """2026-10-15: naming by elimination is off - a recent entry no longer names the only
    unnamed person; the door area (entry match) or the face does."""
    lab = Labeler()
    t = Track(9, (600, 260, 70, 180), 7900.0, 8000.0)
    recent = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 7000.0}
    lab.assign([t], [recent], DOOR, now=8000.0)
    assert t.label is None


# ---- 2026-10-18: entry-to-camera association never names by timing alone -------------------------
ALI = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 95.0}
SARA = {"auth_subject": "USER2", "name": "Sara", "role": "STUDENT", "entered_at": 96.0}


def _run(lab, tracks, occupants, t0, t1, step=0.15):
    t = t0
    while t <= t1 + 1e-9:
        lab.assign(tracks, occupants, DOOR, now=t)
        t += step


def test_two_people_in_together_for_one_entry_are_both_left_unknown_and_flagged():
    lab = Labeler()
    a = Track(7, (115, 200, 70, 180), 100.0, 100.0)
    b = Track(8, (95, 190, 70, 185), 100.6, 100.6)          # right behind, also through the door
    _run(lab, [a, b], [ALI], 100.0, 103.0)
    assert a.label is None and b.label is None              # timing cannot tell who badged
    kinds = [e.kind for e in lab._review] + [n["kind"] for n in lab.notes]
    assert "DOOR_ENTRY_AMBIGUOUS" in kinds


def test_two_entries_and_two_people_together_name_nobody():
    lab = Labeler()
    a = Track(7, (115, 200, 70, 180), 100.0, 100.0)
    b = Track(8, (95, 190, 70, 185), 100.5, 100.5)
    _run(lab, [a, b], [ALI, SARA], 100.0, 103.0)
    assert a.label is None and b.label is None


def test_review_event_is_raised_once_for_an_ambiguous_entry():
    lab = Labeler()
    a = Track(7, (115, 200, 70, 180), 100.0, 100.0)
    b = Track(8, (95, 190, 70, 185), 100.4, 100.4)
    events = []
    t = 100.0
    while t <= 104.0:
        lab.assign([a, b], [ALI], DOOR, now=t)
        events += [e for e in lab.events if e.kind == "PERSON_IDENTITY_REVIEW"]
        t += 0.15
    assert len(events) == 2                                 # one per person, not one per pass


def test_someone_who_walks_to_the_door_after_an_entry_does_not_inherit_the_name():
    lab = Labeler()
    walker = Track(5, (400, 220, 70, 180), 96.0, 96.0)      # first seen in the room, after the entry
    lab.assign([walker], [ALI], DOOR, now=96.0)
    walker.box = (115, 200, 70, 180)                        # ...then stands at the door
    _run(lab, [walker], [ALI], 97.0, 100.0)
    assert walker.label is None


def test_someone_already_at_the_door_before_the_entry_is_not_the_entrant():
    lab = Labeler()
    waiting = Track(6, (115, 200, 70, 180), 80.0, 80.0)     # at the door 15 s before the badge
    _run(lab, [waiting], [ALI], 80.0, 100.0, step=0.5)
    assert waiting.label is None


def test_one_entrant_then_a_tailgater_later_only_the_first_is_named():
    lab = Labeler()
    a = Track(7, (115, 200, 70, 180), 100.0, 100.0)
    _run(lab, [a], [ALI], 100.0, 102.0)
    assert a.label == "USER1"
    b = Track(9, (115, 200, 70, 180), 106.0, 106.0)          # 6 s later, no entry of their own
    _run(lab, [a, b], [ALI], 106.0, 108.0)
    assert a.label == "USER1" and b.label is None

```
