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


def test_elimination_still_works_for_a_recent_entry():
    lab = Labeler()
    t = Track(9, (600, 260, 70, 180), 7900.0, 8000.0)
    recent = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 7000.0}
    lab.assign([t], [recent], DOOR, now=8000.0)
    assert t.label == "USER1" and t.named_by == "elimination"
