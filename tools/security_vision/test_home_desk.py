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


def test_a_person_in_front_overlapping_the_desk_is_not_named():
    """Lab 2026-10-14: the man seated at PC-08, in front, overlapped PC-09/PC-10 in the picture."""
    front = Track(1, (480, 260, 110, 190), 90.0, 100.0)    # big: much closer to the camera
    run([front], [HEMALY])
    assert front.label is None


DOOR = (72, 168, 48, 165)


def _desk_named(lab, entered_at=0.0):
    sitter = Track(1, SEATED, 90.0, 100.0)
    lab.home_desk([sitter], DESKS, ZONES, [dict(HEMALY, entered_at=entered_at)], {}, now=100.0)
    assert sitter.label == "USER5"
    return sitter


def test_a_newer_door_entry_takes_the_name_from_the_desk_sitter():
    """Owner (2026-10-14): someone sat at Hemaly's desk and got his name; when Hemaly then comes
    in through the door, the one walking in is him and the desk-sitter is not."""
    lab = Labeler()
    sitter = _desk_named(lab)
    walker = Track(7, (115, 200, 70, 180), 201.0, 202.0)                  # new person at the door
    # named once it has been in view ENTRY_SETTLE_S (2026-10-18: anyone right behind is seen first)
    lab.assign([sitter, walker], [dict(HEMALY, entered_at=200.0)], DOOR, now=201.0 + Labeler.ENTRY_SETTLE_S)
    assert walker.label == "USER5" and walker.named_by == "door"
    assert sitter.label is None


def test_without_a_new_entry_the_desk_name_stays():
    lab = Labeler()
    sitter = _desk_named(lab)
    other = Track(8, (600, 260, 70, 180), 20.0, 101.0)                    # someone else, unnamed
    lab.assign([sitter, other], [dict(HEMALY, entered_at=0.0)], DOOR, now=101.0)
    assert sitter.label == "USER5"


def test_ali_at_hemalys_desk_stays_ali_after_his_box_breaks():
    """Owner (2026-10-14): 'if I go to Hemaly's desk I should stay Ali Loay'. A box break there
    must give Ali his own name back - not Hemaly's by desk."""
    import test_vision as tv
    img, (a, b) = tv._frame((100, tv.ALI), (400, tv.SARA))
    la, lb = tv._looks(img, [a, b])
    zones = {"PC-09": (a[0], a[1] + a[3] // 3, a[2], a[3] // 3)}            # Hemaly's desk = where Ali sits
    people = [tv.occ("USER1", "Ali", "STUDENT", 0.0), tv.occ("USER2", "Sara", "STUDENT", 0.0), dict(HEMALY)]
    ali = Track(1, a, 0, 0, label="USER1", name="Ali", role="STUDENT", look=la)
    sara = Track(2, b, 0, 0, label="USER2", name="Sara", role="STUDENT", look=lb)
    lab = Labeler()
    tv._learnt(lab, [ali, sara], people)
    lab.assign([sara], people, None, now=10.0)                         # Ali's box breaks at the desk
    again = Track(3, a, 11.0, 11.0, look=la)
    lab.home_desk([sara, again], {"USER5": ["PC-09"]}, zones, people, {}, now=11.0,
                  standing_ratio=10.0)                                 # the drawn figure counts as seated
    assert again.label != "USER5"                                      # never Hemaly by desk
    lab.assign([sara, again], people, None, now=11.5)
    assert again.label == "USER1"                                      # Ali back


def test_sitting_beside_the_monitor_box_still_counts():
    """Live 2026-10-14: Hemaly's box centre 35 px left of the PC-09 box centre (box 33 px wide)."""
    zones = {"PC-09": (530, 267, 33, 24)}
    t = Track(1, (493, 247, 38, 46), 90.0, 100.0)
    lab = Labeler()
    lab.home_desk([t], {"USER5": ["PC-09"]}, zones, [HEMALY], {}, now=100.0)
    assert t.label == "USER5"


def test_a_desk_name_is_drawn_as_a_guess():
    import numpy as np
    from vision import draw
    t = Track(1, SEATED, 90.0, 100.0, hits=5)
    lab = Labeler()
    lab.home_desk([t], DESKS, ZONES, [HEMALY], {}, now=100.0)
    import vision
    seen = []
    orig = vision._tag                    # every tag in the picture is drawn by _tag (2026-10-19)
    vision._tag = lambda frame, text, *a, **k: (seen.append(text), orig(frame, text, *a, **k))[1]
    try:
        draw(np.zeros((540, 960, 3), np.uint8), [t], [], {})
    finally:
        vision._tag = orig
    assert any("? (desk)" in s for s in seen)
