"""Lab 24 Nov 2026: a staff-confirmed name that clearly no longer fits after people touched becomes a marked guess."""
import numpy as np

from vision import Labeler, Look, Track

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"}


def look(seed, partial=False):
    v = np.random.default_rng(seed).normal(size=64).astype(np.float32)
    return Look(None, v / np.linalg.norm(v), partial=partial)


def run(after, touch=True, n=40, before=8):
    lab, t = Labeler(), Track(3, (100, 100, 60, 200), 0.0, 0.0)
    lab._give(t, ALI, "operator")
    now = 0.0
    for _ in range(before):
        t.look, t.crowded = look(1), False
        now += 0.2
        lab._doubt_confirmed([t], now)
    if touch:
        t.crowded = True
        lab._doubt_confirmed([t], now)
        t.crowded = False
    for _ in range(n):
        t.look = after
        now += 0.2
        lab._doubt_confirmed([t], now)
    return lab, t


def test_other_look_after_a_touch_becomes_a_guess_and_keeps_no_confirmed_status():
    lab, t = run(look(2))
    assert t.source == "look" and "USER1" in lab.look_guessed and "USER1" not in lab.face_named
    assert any(n["kind"] == "CONFIRMED_NAME_DOUBTED" for n in lab.notes)


def test_same_look_keeps_the_staff_name():
    assert run(look(1))[1].source == "operator"


def test_without_a_touch_nothing_is_doubted():
    assert run(look(2), touch=False)[1].source == "operator"


def test_no_reference_no_doubt():
    assert run(look(2), before=0)[1].source == "operator"


def test_a_new_confirmation_starts_again():
    lab, t = run(look(2), n=5)
    lab._give(t, ALI, "operator")
    t.confirmed_at = 99.0
    for i in range(40):
        lab._doubt_confirmed([t], 10 + i * 0.2)
    assert t.source == "operator"
