"""Lab 2026-10-19, camera 1 log: whoever sat at PC-09/PC-10 got Hemaly's name (USER5) from a door entry
2.7 h old, while camera 2's face match said USER1 (4 episodes, CROSSCAM_CONFLICT x243). And each time a
seated person was missed for a moment, the name was logged lost and the desk gave it to a second track
(NAME_ON_TWO_PEOPLE x24). The desk now only continues evidence; a track the tracker still keeps holds
its name."""
from vision import Labeler, Track

DESKS = {"USER5": ["PC-09", "PC-10"]}
ZONES = {"PC-09": (520, 270, 40, 30), "PC-10": (565, 270, 40, 30)}
SEATED = (525, 250, 45, 60)


def hemaly(entered_at):
    return {"auth_subject": "USER5", "name": "Eng. Hemaly", "role": "STAFF", "entered_at": entered_at}


def kinds(lab):
    return [n["kind"] for n in getattr(lab, "notes", [])]


def test_18_36_episode_a_door_entry_hours_old_does_not_name_whoever_sits_at_the_desk():
    lab = Labeler()
    now = 1792424152.6
    sitter = Track(15, SEATED, now - 1, now)
    lab.home_desk([sitter], DESKS, ZONES, [hemaly(now - 9712)], {}, now=now)
    assert sitter.label is None
    assert "DESK_NOT_USED" in kinds(lab)


def test_right_after_the_door_entry_the_desk_still_names_its_owner():
    lab = Labeler()
    sitter = Track(1, SEATED, 99.0, 100.0)
    lab.home_desk([sitter], DESKS, ZONES, [hemaly(40.0)], {}, now=100.0)
    assert sitter.label == "USER5"


def test_a_desk_name_carries_on_through_a_box_break_long_after_the_entry():
    """Chain of evidence: named at the desk right after entering, then present all afternoon - a box
    break hours later is bridged because the name was on a track moments before."""
    lab = Labeler()
    occ = [hemaly(40.0)]
    first = Track(1, SEATED, 99.0, 100.0)
    lab.home_desk([first], DESKS, ZONES, occ, {}, now=100.0)
    assert first.label == "USER5"
    for t in range(101, 3 * 3600, 60):                     # seated for three hours, seen every minute
        first.last_seen = float(t)
        lab.assign([first], occ, None, now=float(t))
    end = first.last_seen
    lab.assign([], occ, None, now=end + 30)                # the box breaks behind the monitor
    again = Track(2, SEATED, end + 35, end + 40)
    lab.home_desk([again], DESKS, ZONES, occ, {}, now=end + 40)
    assert again.label == "USER5"


def test_after_the_desk_was_empty_for_long_the_chain_is_broken():
    lab = Labeler()
    occ = [hemaly(40.0)]
    first = Track(1, SEATED, 99.0, 100.0)
    lab.home_desk([first], DESKS, ZONES, occ, {}, now=100.0)
    lab.assign([first], occ, None, now=101.0)
    lab.assign([], occ, None, now=102.0)                   # gone
    later = 101.0 + Labeler.DESK_FRESH_S + 60              # someone sits there 11 min later
    stranger = Track(9, SEATED, later - 1, later)
    lab.home_desk([stranger], DESKS, ZONES, occ, {}, now=later)
    assert stranger.label is None


def test_a_track_missed_for_a_moment_keeps_its_name_and_nobody_else_gets_it():
    lab = Labeler()
    occ = [hemaly(40.0)]
    her = Track(1, SEATED, 99.0, 100.0)
    lab.home_desk([her], DESKS, ZONES, occ, {}, now=100.0)
    lab.assign([her], occ, None, now=100.2)
    lab.notes = []
    # missed for a second (detector), the tracker still keeps her; a fragment box appears at the desk
    fragment = Track(2, (530, 255, 40, 55), 101.0, 101.2)
    lab.assign([fragment], occ, None, now=101.2, coasting=[her])
    lab.home_desk([fragment], DESKS, ZONES, occ, {}, now=101.2)
    assert fragment.label is None                          # not a second "Hemaly"
    assert "NAME_LOST" not in kinds(lab)                   # and not reported lost
    her.last_seen = 101.6
    lab.assign([her], occ, None, now=101.6)                # back under her own id
    assert her.label == "USER5" and "NAME_LOST" not in kinds(lab)


def test_when_the_tracker_lets_go_the_name_is_reported_lost_once():
    lab = Labeler()
    occ = [hemaly(40.0)]
    her = Track(1, SEATED, 99.0, 100.0)
    lab.home_desk([her], DESKS, ZONES, occ, {}, now=100.0)
    lab.assign([her], occ, None, now=100.2)
    lab.assign([], occ, None, now=101.0, coasting=[her])
    lab.assign([], occ, None, now=106.5)                   # the tracker dropped her (6 s still)
    assert kinds(lab).count("NAME_LOST") == 1
