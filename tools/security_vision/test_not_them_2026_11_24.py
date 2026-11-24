"""Lab 24 Nov 2026: a name by look never goes to someone who was in view together with the confirmed person."""
import numpy as np

from labmap import LabNumbers
from test_labmap import Look, T, near, vec

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"}


def named(t):
    t.label, t.name, t.role, t.source, t.verified = "USER1", "Ali", "STUDENT", "face", True
    return t


def unnamed(tid, look):
    t = T(tid, look)
    t.name = t.role = t.source = None
    t.verified = t.crowded = False
    return t


def restored(cam, tracks, start, n=40):
    got = []
    for i in range(n):
        cam.assign(tracks, {}, now=start + i * 0.3)
        got += [t.id for t, w in cam.restore if w["auth_subject"] == "USER1"]
    return got


def run(tmp_path, together):
    cam = LabNumbers(str(tmp_path / "p.json"), "SECCAM_LAB02")
    look = vec(1)
    ali, other = named(unnamed(93, look)), unnamed(35, near(look, 0.05))
    for i in range(20):
        cam.assign([ali, other] if together else [ali], {}, now=100 + i * 0.3)
    return restored(cam, [other], 110.0)


def test_person_seen_together_with_the_confirmed_one_is_not_them(tmp_path):
    assert run(tmp_path, together=True) == []


def test_a_new_track_still_gets_the_guess(tmp_path):
    assert run(tmp_path, together=False) == [35]


def peer_run(tmp_path, passes, paired=False):
    cam = LabNumbers(str(tmp_path / "p.json"), "SECCAM_LAB01")
    look = vec(1)
    ali = named(unnamed(5, look))
    cam.assign([ali], {}, now=100.0)
    cam.assign([ali], {}, now=100.5)
    seated = unnamed(52, near(look, 0.05))
    far = vec(7)
    seated.look = Look(far)                                  # numbered as somebody else first
    for i in range(8):
        cam.assign([seated], {}, now=101.0 + i)
    p = {"id": 93, "label": "USER1", "source": "face", "lab_no": 1, "crowded": True, "deep": None}
    for i in range(passes):
        cam.assign([seated], {52: p} if paired else {}, now=110.0 + i * 0.2, peer_tracks=[p])
    return cam.not_them.get(52, set())


def test_someone_here_while_the_other_camera_shows_the_person_is_not_them(tmp_path):
    assert "USER1" in peer_run(tmp_path, 15)


def test_short_or_paired_views_do_not_exclude(tmp_path):
    assert "USER1" not in peer_run(tmp_path, 3)
    assert "USER1" not in peer_run(tmp_path, 15, paired=True)
