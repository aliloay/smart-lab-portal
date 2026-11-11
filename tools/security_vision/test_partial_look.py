"""Half-body looks (2026-11-11): a box cut by the bottom of the picture is compared shirt-to-shirt and never stored
into a person's identity. Colour bands are synthetic here; the real-recording measurement is in vision.PARTIAL_LOOK."""
import numpy as np

import vision
from vision import Identity, Labeler, Look, Track, blend, is_partial, look_distance

N = 16


def bands(*colours):                      # one 16-bin histogram per body band, a single colour bin each
    c = np.zeros(3 * N, np.float32)
    for i, k in enumerate(colours):
        c[i * N + k] = 1.0
    return c


GREY, BLUE, BLACK, RED = 13, 7, 12, 0
ALI_FULL = Look(bands(GREY, BLUE, BLACK))                     # head, blue shirt, black trousers
ALI_HALF = Look(bands(GREY, BLUE, BLUE), partial=True)        # waist-up: the lower band is still the shirt
OTHER_HALF = Look(bands(GREY, RED, RED), partial=True)


def test_a_box_is_partial_only_when_cut_by_the_frame_bottom():
    assert is_partial((100, 400, 100, 120), 520)              # bottom at the frame edge, short box
    assert not is_partial((100, 100, 100, 120), 520)          # short but inside the picture (seated): not assumed
    assert not is_partial((100, 260, 100, 260), 520)          # touches the edge but already a full-height box


def test_waist_up_view_matches_the_same_person_and_not_another():
    same, other = look_distance(ALI_FULL, ALI_HALF), look_distance(ALI_FULL, OTHER_HALF)
    naive = look_distance(ALI_FULL, Look(ALI_HALF.color))      # as before: shirt compared with trousers
    assert same < naive and same < 0.6 < other
    assert look_distance(ALI_HALF, ALI_FULL) == same           # order does not matter


def test_partial_views_never_overwrite_the_stored_identity():
    lab = Labeler()
    lab.identities["USER1"] = Identity(ALI_FULL, Labeler.LOCK_SAMPLES + 2)
    t = Track(1, (100, 100, 100, 260), 0, 0, hits=10, label="USER1", name="Ali", look=ALI_HALF)
    t.source = "door"
    before = lab.identities["USER1"].samples
    lab._learn([t])
    assert lab.identities["USER1"].samples == before
    assert blend(ALI_FULL, ALI_HALF, 0.5).partial is False     # a blend with a whole view is a whole view


def test_switch_off_restores_the_old_behaviour(monkeypatch):
    monkeypatch.setattr(vision, "PARTIAL_LOOK", False)
    assert not is_partial((100, 400, 100, 120), 520)
