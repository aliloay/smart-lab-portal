"""Lab 2026-10-19 19:05 (camera 2): Nour's name (USER6), rightly handed over from camera 1, stayed on camera 2's
track through a crossing in which it went onto Ali - camera 2's own face matches said USER1 and the name stayed
(PERSON_IDENTITY_CONFLICT, name not switched). A name only carried over (other camera, desk) now gives way to this
camera's agreeing face matches; a door name keeps its mismatch flag instead."""
from vision import Labeler, Track

ALI = {"auth_subject": "USER1", "name": "Ali Loay", "role": "STUDENT", "entered_at": 1000.0}
NOUR = {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT", "entered_at": 1050.0}


def named(source, label="USER6", name="Nour", crowded=False):
    t = Track(16, (400, 120, 80, 220), 1100.0, 1138.0, label=label, name=name, role="STUDENT", source=source)
    t.crowded = crowded
    return t


def faces(lab, t, label, now):
    lab.face_vote(t.id, label, now - 1.0)
    lab.face_vote(t.id, label, now - 0.5)


def notes(lab):
    return [n["kind"] for n in getattr(lab, "notes", [])]


def test_a_name_from_the_other_camera_gives_way_to_this_cameras_face():
    lab, t = Labeler(), named("peer")
    faces(lab, t, "USER1", 1138.0)
    lab.assign([t], [ALI, NOUR], None, now=1138.0)
    assert t.label == "USER1" and t.source == "face"
    assert "NAME_DROPPED_FACE_DISAGREES" in notes(lab)


def test_a_desk_guess_gives_way_to_the_face_too():
    lab, t = Labeler(), named("desk", label="USER5", name="Eng. Hemaly")
    faces(lab, t, "USER1", 1138.0)
    lab.assign([t], [ALI, NOUR, {"auth_subject": "USER5", "name": "Eng. Hemaly", "role": "STAFF", "entered_at": 900.0}],
               None, now=1138.0)
    assert t.label == "USER1"


def test_a_door_name_is_not_dropped_by_the_face():
    lab, t = Labeler(), named("door")
    faces(lab, t, "USER1", 1138.0)
    lab.assign([t], [ALI, NOUR], None, now=1138.0)
    assert t.label == "USER6"
    assert "NAME_DROPPED_FACE_DISAGREES" not in notes(lab)


def test_while_people_touch_the_face_does_not_move_a_name():
    lab, t = Labeler(), named("peer", crowded=True)
    faces(lab, t, "USER1", 1138.0)
    lab.assign([t], [ALI, NOUR], None, now=1138.0)
    assert t.label == "USER6"


def test_one_face_match_is_not_enough():
    lab, t = Labeler(), named("peer")
    lab.face_vote(t.id, "USER1", 1137.5)
    lab.assign([t], [ALI, NOUR], None, now=1138.0)
    assert t.label == "USER6"
