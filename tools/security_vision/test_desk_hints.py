"""Owner 2026-10-21: an unnamed person seated at a known desk shows a GUESS ("Eng. Hemaly?" at his desk,
"TA?" at PC-16) instead of "Unknown" - shown only, never a name, never shared, replaced by a real name."""
from crosscam import peer_view
from vision import Labeler, Track, _person_label

ZONES = {"PC-04": (520, 270, 40, 30), "PC-01": (565, 270, 40, 30), "PC-16": (200, 200, 40, 30)}
HINTS = {"Eng. Hemaly?": ["PC-04", "PC-01"], "TA?": ["PC-16"]}
AT_04 = (525, 250, 45, 60)                    # seated at PC-04
AT_16 = (205, 180, 45, 60)                    # seated at PC-16
STANDING = (525, 200, 30, 110)                # standing in front of PC-04
ELSEWHERE = (800, 400, 45, 60)


def test_unnamed_seated_at_a_known_desk_gets_the_guess_as_its_tag():
    a, b, c = Track(1, AT_04, 0, 0), Track(2, AT_16, 0, 0), Track(3, ELSEWHERE, 0, 0)
    Labeler().desk_hints([a, b, c], HINTS, ZONES)
    assert (a.hint, b.hint, c.hint) == ("Eng. Hemaly?", "TA?", None)
    assert _person_label(a) == "Eng. Hemaly? (desk)" and _person_label(c) == "Unknown"


def test_a_guess_is_never_a_name_and_never_reaches_the_other_camera():
    t = Track(1, AT_04, 0, 0)
    Labeler().desk_hints([t], HINTS, ZONES)
    assert t.label is None and t.name is None and t.identity_state != "DOOR_CONFIRMED"
    assert peer_view([t], None, 1000, 1000, 1.0)["tracks"][0]["label"] is None


def test_standing_or_named_people_get_no_guess_and_it_clears_when_they_leave():
    s = Track(1, STANDING, 0, 0)
    n = Track(2, AT_04, 0, 0, label="USER1", name="Ali Loay")
    lab = Labeler()
    lab.desk_hints([s, n], HINTS, ZONES)
    assert s.hint is None and n.hint is None and _person_label(n).startswith("Ali Loay")
    t = Track(3, AT_04, 0, 0)
    lab.desk_hints([t], HINTS, ZONES)
    t.box = ELSEWHERE
    lab.desk_hints([t], HINTS, ZONES)
    assert t.hint is None
