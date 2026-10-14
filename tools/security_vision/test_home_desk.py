"""Owner's rule (lab 2026-10-14): Hemaly's desk (PC-09 / PC-10) names him - only once the door or
his face placed him in the lab, and only if exactly one unnamed seated person is there."""
from vision import Labeler, Track

DESKS = {"USER5": ["PC-09", "PC-10"]}
ZONES = {"PC-09": (520, 270, 40, 30), "PC-10": (565, 270, 40, 30)}
HEMALY = {"auth_subject": "USER5", "name": "Eng. Hemaly", "role": "STAFF", "entered_at": 0.0}
SEATED = (525, 250, 45, 60)                     # at PC-09, h/w 1.3
STANDING = (525, 200, 30, 110)                  # at PC-09, h/w 3.7


def run(tracks, occupants):
    lab = Labeler()
    lab.home_desk(tracks, DESKS, ZONES, occupants, {}, now=100.0)
    return lab


def test_seated_at_his_desk_after_the_door_entry_is_named():
    t = Track(1, SEATED, 90.0, 100.0)
    run([t], [HEMALY])
    assert t.label == "USER5" and t.named_by == "desk"


def test_not_known_to_be_in_the_lab_no_name():
    t = Track(1, SEATED, 90.0, 100.0)
    run([t], [])
    assert t.label is None


def test_face_recognised_counts_as_in_the_lab():
    t = Track(1, SEATED, 90.0, 100.0)
    lab = Labeler()
    lab.face_named["USER5"] = (HEMALY, 95.0)
    lab.home_desk([t], DESKS, ZONES, [], {}, now=100.0)
    assert t.label == "USER5"


def test_two_people_at_the_desk_nobody_named():
    a, b = Track(1, SEATED, 90.0, 100.0), Track(2, (570, 252, 45, 58), 90.0, 100.0)
    run([a, b], [HEMALY])
    assert a.label is None and b.label is None


def test_someone_standing_at_his_desk_is_not_named():
    t = Track(1, STANDING, 90.0, 100.0)
    run([t], [HEMALY])
    assert t.label is None
