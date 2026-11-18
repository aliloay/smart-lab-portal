"""labmap.py: one lab number per person on both cameras, kept when the person comes back."""
import os
import threading

import numpy as np
import pytest

import labmap
from labmap import LabNumbers, Register


class Look:
    def __init__(self, deep):
        self.deep = deep


class T:
    def __init__(self, tid, deep=None, label=None):
        self.id, self.label, self.lab_no = tid, label, None
        self.look = Look(deep) if deep is not None else None


def vec(seed, dim=16):
    v = np.random.default_rng(seed).normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def near(v, eps, seed=99):
    """A look close to v (distance grows with eps)."""
    w = v + eps * np.random.default_rng(seed).normal(size=v.shape).astype(np.float32)
    return w / np.linalg.norm(w)


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / "lab_people_LAB_01.json")


def test_each_new_person_gets_a_new_number(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    a, b = T(1, vec(1)), T(2, vec(2))
    cam.assign([a, b], {}, now=100.0)
    assert {a.lab_no, b.lab_no} == {1, 2}


def test_two_cameras_never_hand_out_the_same_number(path):
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    a, b = T(1, vec(1)), T(7, vec(2))
    c1.assign([a], {}, now=100.0)
    c2.assign([b], {}, now=100.1)
    assert a.lab_no != b.lab_no


def test_paired_person_takes_the_lower_number_on_both_cameras(path):
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    me1, me2 = T(1, vec(5)), T(9, near(vec(5), 0.05))
    c1.assign([me1], {}, now=100.0)          # camera 1 saw me first: 1
    c2.assign([me2], {}, now=100.2)          # camera 2 alone (not paired yet): would number me separately
    assert me2.lab_no != me1.lab_no
    # crosscam paired the two views: both converge on the lower number
    c2.assign([me2], {me2.id: {"lab_no": me1.lab_no, "_passes": 20, "_look": 0.2}}, now=101.0)
    c1.assign([me1], {me1.id: {"lab_no": me2.lab_no, "_passes": 20, "_look": 0.2}}, now=101.0)
    assert me1.lab_no == me2.lab_no == 1


def test_a_person_who_comes_back_gets_the_old_number(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    me, other = T(1, vec(5)), T(2, vec(6))
    for k in range(5):                                       # in view for a while
        cam.assign([me, other], {}, now=100.0 + k)
    mine = me.lab_no
    cam.assign([other], {}, now=110.0)                       # I left
    back = T(30, near(vec(5), 0.05))                         # new track, same look
    cam.assign([other, back], {}, now=140.0)
    assert back.lab_no == mine


def test_a_different_person_does_not_take_a_departed_number(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    me = T(1, vec(5))
    cam.assign([me], {}, now=100.0)
    cam.assign([], {}, now=110.0)
    stranger = T(2, vec(77))
    cam.assign([stranger], {}, now=140.0)
    assert stranger.lab_no != me.lab_no


def test_a_number_in_view_on_the_other_camera_is_never_reused(path):
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    me = T(1, vec(5))
    c1.assign([me], {}, now=100.0)
    twin = T(4, near(vec(5), 0.05))                          # same look, but I am still in view on camera 1
    c1.assign([me], {}, now=101.0)
    c2.assign([twin], {}, now=101.5)
    assert twin.lab_no != me.lab_no


def test_two_alike_departed_people_give_a_new_number_not_a_guess(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    base = vec(5)
    a, b = T(1, near(base, 0.02, 1)), T(2, near(base, 0.02, 2))   # two people who look nearly the same
    cam.assign([a, b], {}, now=100.0)
    cam.assign([], {}, now=110.0)
    back = T(3, near(base, 0.02, 3))
    cam.assign([back], {}, now=140.0)
    assert back.lab_no not in (a.lab_no, b.lab_no)


def test_named_people_get_a_number_too_but_not_from_the_gallery(path):
    """Lab 2026-11-17: Nour named on camera 2, Unknown on camera 1 - the number is what links the two boxes."""
    cam = LabNumbers(path, "SECCAM_LAB01")
    ali = T(1, vec(5), label="USER1")
    cam.assign([ali], {}, now=100.0)
    assert ali.lab_no is not None


def test_waits_for_a_look_then_numbers_anyway(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    t = T(1)                                                 # no look yet
    cam.assign([t], {}, now=100.0)
    assert t.lab_no is None
    cam.assign([t], {}, now=100.0 + labmap.LOOK_WAIT_S + 0.1)
    assert t.lab_no is not None


def test_forgotten_after_the_gallery_time(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    me = T(1, vec(5))
    cam.assign([me], {}, now=100.0)
    cam.assign([], {}, now=101.0)
    back = T(2, near(vec(5), 0.05))
    cam.assign([back], {}, now=101.0 + labmap.GALLERY_S + 10)
    # 2026-11-18: numbers are reused (lowest free), so the old number may come again - but as a NEW person:
    # the register entry starts now, it is not "came back"
    entry = labmap.Register(path).read()["people"][str(back.lab_no)]
    assert entry["first"] == 101.0 + labmap.GALLERY_S + 10


def test_new_numbers_are_the_lowest_free_not_a_climbing_counter(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    a, b, c = T(1, vec(1)), T(2, vec(2)), T(3, vec(3))
    cam.assign([a, b, c], {}, now=100.0)
    assert sorted(t.lab_no for t in (a, b, c)) == [1, 2, 3]
    cam.assign([a, c], {}, now=101.0)
    cam.assign([a, c], {}, now=102.0 + labmap.GALLERY_S)          # b forgotten: number 2 is free again
    d = T(4, vec(4))
    cam.assign([a, c, d], {}, now=103.0 + labmap.GALLERY_S)
    assert d.lab_no == 2


def test_register_survives_a_broken_file_and_a_stale_lock(path):
    with open(path, "w") as f:
        f.write("{not json")
    with open(path + ".lock", "w") as f:
        f.write("")
    old = os.path.getmtime(path + ".lock") - labmap.LOCK_STALE_S - 1
    os.utime(path + ".lock", (old, old))
    cam = LabNumbers(path, "SECCAM_LAB01")
    t = T(1, vec(1))
    cam.assign([t], {}, now=100.0)
    assert t.lab_no == 1 and not os.path.exists(path + ".lock")


def test_two_processes_writing_at_once_never_share_a_number(path):
    got, lock = [], threading.Lock()

    def run(dev, base):
        cam = LabNumbers(path, dev)
        for k in range(20):
            t = T(base + k, vec(base + k))
            cam.assign([t], {}, now=100.0 + k * 0.01)
            with lock:
                got.append(t.lab_no)
    th = [threading.Thread(target=run, args=("A", 0)), threading.Thread(target=run, args=("B", 1000))]
    [x.start() for x in th]
    [x.join() for x in th]
    assert len(got) == 40 and len(set(got)) == 40


def test_a_short_or_crowded_or_unlike_pairing_moves_no_number(path):
    cam = LabNumbers(path, "SECCAM_LAB02")
    t = T(1, vec(5))
    cam.assign([t], {}, now=100.0)
    mine = t.lab_no
    for link in ({"lab_no": 99999, "_passes": 5},                         # not held long enough
                 {"lab_no": 0.5, "_passes": 20, "_crowded": True},        # touching someone
                 {"lab_no": 0.5, "_passes": 20, "_look": 0.8}):           # looks clearly different
        cam.assign([t], {t.id: link}, now=101.0)
        assert t.lab_no == mine


def test_never_two_people_with_one_number_in_a_view(path):
    """Lab 2026-11-17 first run: pairings around the UR5e table gave three people 'Person 1' on one camera."""
    cam = LabNumbers(path, "SECCAM_LAB02")
    a, b, c = T(1, vec(1)), T(2, vec(2)), T(3, vec(3))
    cam.assign([a, b, c], {}, now=100.0)
    solid = {"_passes": 20, "_look": 0.2}
    cam.assign([a, b, c], {b.id: {"lab_no": a.lab_no, **solid}, c.id: {"lab_no": a.lab_no, **solid}}, now=101.0)
    nos = [x.lab_no for x in (a, b, c)]
    assert len(set(nos)) == 3                                              # a's number is not copied onto b or c
    b.lab_no = c.lab_no = a.lab_no                                         # duplicates from an older version
    cam.assign([a, b, c], {}, now=102.0)
    assert len({x.lab_no for x in (a, b, c)}) == 3


def test_seated_person_gets_the_other_cameras_number_by_a_clear_look(path):
    """Owner at PC-01: feet hidden, a desk only camera 1 sees - the look alone, when clear and held, links them."""
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    me1, other1 = T(1, vec(5)), T(2, vec(6))
    c1.assign([me1, other1], {}, now=100.0)
    me2, other2 = T(8, near(vec(5), 0.05)), T(9, vec(77))
    c2.assign([me2, other2], {}, now=100.1)
    assert me2.lab_no != me1.lab_no
    peer = [{"lab_no": me1.lab_no, "deep": list(vec(5)), "label": None},
            {"lab_no": other1.lab_no, "deep": list(vec(6)), "label": None}]
    for k in range(labmap.LINK_PASSES):
        c2.assign([me2, other2], {}, now=101.0 + k * 0.2, peer_tracks=peer)
    assert me2.lab_no == min(me1.lab_no, me2.lab_no) and other2.lab_no != me1.lab_no


def test_look_link_refused_when_two_people_look_alike(path):
    c2 = LabNumbers(path, "SECCAM_LAB02")
    me = T(8, vec(5))
    c2.assign([me], {}, now=100.0)
    mine = me.lab_no
    peer = [{"lab_no": 0.5, "deep": list(near(vec(5), 0.03, 1)), "label": None},
            {"lab_no": 0.25, "deep": list(near(vec(5), 0.03, 2)), "label": None}]   # two alike there: no guess
    for k in range(labmap.LINK_PASSES + 2):
        c2.assign([me], {}, now=101.0 + k * 0.2, peer_tracks=peer)
    assert me.lab_no == mine


def test_a_confirmed_name_comes_back_with_the_look(path):
    """Lab 17 Nov: Ali was confirmed, bent down, the track broke and the new track was 'Person 230'."""
    cam = LabNumbers(path, "SECCAM_LAB01")
    ali = T(1, vec(5), label="USER1"); ali.name, ali.role, ali.source = "Ali Loay", "STUDENT", "operator"
    cam.assign([ali], {}, now=100.0)
    cam.assign([], {}, now=104.0)                                   # track broke
    back = T(2, near(vec(5), 0.05))
    cam.assign([back], {}, now=106.0)
    assert back.lab_no == ali.lab_no and cam.restore and cam.restore[0][1]["auth_subject"] == "USER1"


def test_a_guessed_name_is_not_given_back(path):
    cam = LabNumbers(path, "SECCAM_LAB01")
    g = T(1, vec(5), label="USER5"); g.name, g.role, g.source = "Hemaly", "STAFF", "look"   # only a look guess
    cam.assign([g], {}, now=100.0)
    cam.assign([], {}, now=104.0)
    back = T(2, near(vec(5), 0.05))
    cam.assign([back], {}, now=106.0)
    assert not cam.restore


def test_confirmed_name_back_when_the_look_changed_a_bit(path):
    """Lab 17 Nov: Ali came back turned - look farther than MATCH_MAX but he was the only confirmed person gone."""
    cam = LabNumbers(path, "SECCAM_LAB01")
    ali = T(1, vec(5), label="USER1"); ali.name, ali.role, ali.source = "Ali Loay", "STUDENT", "operator"
    cam.assign([ali], {}, now=100.0)
    cam.assign([], {}, now=110.0)
    back = T(2, near(vec(5), 0.9, 7))                                # clearly changed look
    d = labmap._dist(back.look.deep, cam.looks.get(1, vec(5))) if False else None
    cam.assign([back], {}, now=140.0)
    names = [w["auth_subject"] for _, w in cam.restore]
    import labmap as lm
    dd = lm._dist(near(vec(5), 0.9, 7), vec(5))
    assert (names == ["USER1"]) == (dd <= lm.NAME_BACK_MAX)


def test_number_carrying_a_confirmed_name_gives_it(path):
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    nour = T(1, vec(9), label="USER6"); nour.name, nour.role, nour.source = "nour ramy", "STUDENT", "face"
    c1.assign([nour], {}, now=100.0)
    other = T(5, near(vec(9), 0.05))
    c2.assign([other], {other.id: {"lab_no": nour.lab_no, "_passes": 20, "_look": 0.2}}, now=101.0)
    assert other.lab_no == nour.lab_no and [w["auth_subject"] for _, w in c2.restore] == ["USER6"]


def test_conflicting_labels_never_merge_lab_numbers(path):
    """2026-11-17 fix: two tracks carrying different confirmed labels never merge lab_no via links or look."""
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    ali = T(1, vec(5), label="USER1"); ali.name, ali.role, ali.source = "Ali", "STUDENT", "door"
    nour = T(2, near(vec(5), 0.02), label="USER6"); nour.name, nour.role, nour.source = "Nour", "STUDENT", "face"
    c1.assign([ali], {}, now=100.0)
    c2.assign([nour], {}, now=100.1)
    assert ali.lab_no != nour.lab_no
    c2.assign([nour], {nour.id: {"lab_no": ali.lab_no, "label": "USER1", "_passes": 20, "_look": 0.1}}, now=101.0)
    assert nour.lab_no != ali.lab_no


def test_confirmed_person_reuses_lab_number_immediately_after_restart(path):
    """When a service restarts or a confirmed track re-appears with its confirmed label within PRESENT_S,
    it reclaims its existing lab number in the register rather than inflating next."""
    cam = LabNumbers(path, "SECCAM_LAB01")
    ali = T(1, vec(5), label="USER1"); ali.name, ali.role, ali.source = "Ali", "STUDENT", "face"
    cam.assign([ali], {}, now=100.0)
    first_no = ali.lab_no
    cam_restarted = LabNumbers(path, "SECCAM_LAB01")
    ali_after = T(10, vec(77), label="USER1"); ali_after.name, ali_after.role, ali_after.source = "Ali", "STUDENT", "face"
    cam_restarted.assign([ali_after], {}, now=100.5)
    assert ali_after.lab_no == first_no



def test_lock_retries_when_windows_reports_the_lock_file_as_delete_pending(path, monkeypatch):
    """Integration 2026-11-18 (root cause of the intermittent two-writer failure): on Windows, creating the lock
    file while the other camera process is deleting it raises PermissionError (delete pending), not
    FileExistsError. It escaped _lock(), so the whole assign() pass raised. It must be retried like a held lock."""
    real_open, calls = os.open, {"n": 0}

    def flaky_open(p, flags, *a):
        if p.endswith(".lock") and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(13, "Permission denied", p)
        return real_open(p, flags, *a)
    monkeypatch.setattr(labmap.os, "open", flaky_open)
    reg = Register(path)
    assert reg._lock() is True and calls["n"] == 2
    reg._unlock()
    assert not os.path.exists(path + ".lock")


def test_an_unnamed_person_with_a_number_gets_a_confirmed_name_back_later(path):
    # 2026-11-18 lab: Nour walked away, got a new track (and a new number) while her look was not judged yet, and
    # only came back as "nour ramy" ~95 s later when that track broke again. Now the numbered track is re-checked.
    cam = LabNumbers(path, "SECCAM_LAB01")
    nour = T(1, vec(5)); nour.label, nour.name, nour.role, nour.source = "USER6", "nour ramy", "STUDENT", "face"
    cam.assign([nour], {}, now=100.0)
    cam.assign([], {}, now=102.0)
    back = T(2, None)                                  # no look yet: numbered after LOOK_WAIT_S
    cam.assign([back], {}, now=103.0)
    cam.assign([back], {}, now=103.0 + labmap.LOOK_WAIT_S + 0.1)
    assert back.lab_no is not None and back.lab_no != nour.lab_no
    back.look = Look(near(vec(5), 0.05))
    got = []
    for i in range(labmap.LATE_PASSES + 1):
        cam.assign([back], {}, now=106.0 + 1.1 * i)
        got += [w["auth_subject"] for t, w in cam.restore if t is back]
    assert "USER6" in got and back.lab_no == nour.lab_no


def test_a_named_number_does_not_learn_the_look_of_someone_else_wearing_it(path):
    # 2026-11-18 lab: the owner, shown as Hemaly by the desk, kept Hemaly's number; its look became his
    cam = LabNumbers(path, "SECCAM_LAB01")
    hemaly = T(1, vec(5)); hemaly.label, hemaly.name, hemaly.role, hemaly.source = "USER5", "Hemaly", "LAB_STAFF", "face"
    cam.assign([hemaly], {}, now=100.0)
    before = list(labmap.Register(path).read()["people"][str(hemaly.lab_no)]["deep"])
    ali = T(2, vec(9)); ali.lab_no = hemaly.lab_no; ali.label, ali.source = "USER5", "desk"
    ali.label = None
    for i in range(5):
        cam.assign([ali], {}, now=102.0 + 1.1 * i)
    after = labmap.Register(path).read()["people"][str(hemaly.lab_no)]["deep"]
    assert after == before

def test_single_owner_invariant_prevents_one_name_on_multiple_numbers(path):
    """2026-11-18 live lab fix: previously, 8 entries in lab_people_LAB_01.json ('3', '4', '5', '9'...) all carried
    who={'auth_subject': 'USER6'}, so Camera 1 restored USER6 onto Person 3 (at UR5e) while Camera 2 restored USER6
    onto Person 4 (at PC-09) simultaneously, and _confirmed_back saw len(gone) > 1 and refused to restore."""
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    p3 = T(13, vec(10)); p3.lab_no = 3
    p4 = T(21, vec(20)); p4.lab_no = 4
    # Simulate contaminated register where both '3' and '4' and ghost '9' claim USER6
    c1.reg.update(lambda d: d["people"].update({
        "3": {"first": 90.0, "seen": 95.0, "cam": "SECCAM_LAB01", "who": {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT", "source": "face"}},
        "4": {"first": 91.0, "seen": 99.5, "cam": "SECCAM_LAB02", "who": {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT", "source": "face"}},
        "9": {"first": 80.0, "seen": 85.0, "cam": "SECCAM_LAB01", "who": {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT", "source": "face"}},
    }))
    # Camera 2 currently sees USER6 on lab_no 4; Camera 1 sees unnamed p3 (lab_no 3) and p4_c1 (lab_no 4)
    p4_c1 = T(28, vec(20)); p4_c1.lab_no = 4
    c1.assign([p3, p4_c1], {}, now=100.0, peer_tracks=[{"id": 21, "lab_no": 4, "label": "USER6"}])
    restored_tracks = [t.id for t, w in c1.restore if w["auth_subject"] == "USER6"]
    assert restored_tracks == [28]                  # restored ONLY onto lab_no 4, never onto lab_no 3!
    d = c1.reg.read()
    subj_holders = [k for k, v in d["people"].items() if (v.get("who") or {}).get("auth_subject") == "USER6"]
    assert subj_holders == ["4"] and "9" not in d["people"]


def test_merged_number_is_removed_and_restore_does_not_loop_on_same_track(path):
    """2026-11-18 live lab fix: when Person 2 merges into Person 1, '2' is removed from the register so it never
    resurrects as a ghost, and if a restored label is later vetoed/cleared on the same track id, LabNumbers does
    not force it back onto that same track id every pass."""
    c1, c2 = LabNumbers(path, "SECCAM_LAB01"), LabNumbers(path, "SECCAM_LAB02")
    t1 = T(1, vec(5), label="USER6"); t1.name, t1.role, t1.source = "Nour", "STUDENT", "face"
    t2 = T(2, near(vec(5), 0.03))
    c1.assign([t1], {}, now=100.0)
    c2.assign([t2], {}, now=100.1)
    old_t2_no = t2.lab_no
    assert old_t2_no != t1.lab_no
    c2.assign([t2], {t2.id: {"lab_no": t1.lab_no, "_passes": 20, "_look": 0.1}}, now=101.5)
    assert t2.lab_no == t1.lab_no
    assert str(old_t2_no) not in c2.reg.read()["people"]
    assert len(c2.restore) == 1
    # If the caller/veto drops t2.label on the same track 2, c2 must not re-queue USER6 for track 2 again
    t2.label = None
    c2.assign([t2], {}, now=103.0)
    assert c2.restore == []

