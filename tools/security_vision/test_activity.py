"""Live activity lines (2026-11-11): colour / posture / nearest mapped box, from data the service already has."""
import types

import numpy as np

from activity import describe, nearest_zone, posture, top_colour

N = 16                                                    # 12 hue + 4 value bins per band


def bands(top_hue=None, top_val=None):
    c = np.zeros(3 * N, np.float32)
    for b in range(3):
        c[b * N + 13] = 1.0                               # neutral grey everywhere...
    if top_hue is not None:                               # ...and the upper-body band set by the test
        c[N:2 * N] = 0
        c[N + top_hue] = 1.0
    if top_val is not None:
        c[N:2 * N] = 0
        c[N + 12 + top_val] = 1.0
    return c


def test_colour_of_the_upper_body_band():
    assert top_colour(bands(top_hue=4)) == "green"
    assert top_colour(bands(top_hue=7)) == "blue"
    assert top_colour(bands(top_val=0)) == "black"
    assert top_colour(None) is None


def test_posture_from_the_box_shape():
    assert posture((0, 0, 100, 260)) == "standing"
    assert posture((0, 0, 100, 260), vel=(120, 0)) == "walking"
    assert posture((0, 0, 100, 170)) == "seated or leaning"
    assert posture((0, 0, 140, 140)) == "bending or crouching"
    assert posture((0, 0, 260, 100)) == "lying down"


def test_nearest_mapped_box_overlap_or_close_only():
    zones = [{"name": "UR5e", "x": 0.5, "y": 0.2, "w": 0.2, "h": 0.5}, {"name": "PC-04", "x": 0.0, "y": 0.6, "w": 0.1, "h": 0.1}]
    assert nearest_zone((520, 250, 100, 260), zones, 1000, 1000) == ("UR5e", True)
    assert nearest_zone((400, 250, 60, 200), zones, 1000, 1000) == ("UR5e", False)    # close, not touching
    assert nearest_zone((900, 900, 30, 60), zones, 1000, 1000) is None                # far from everything


def test_sentences_named_first_and_guesses_keep_their_question_mark():
    zones = [{"name": "UR5e", "x": 0.5, "y": 0.2, "w": 0.2, "h": 0.5}]
    look = lambda c: types.SimpleNamespace(color=c)
    a = types.SimpleNamespace(id=9, label=None, name=None, source=None, box=(520, 250, 140, 140), vel=(0, 0),
                              crowded=False, look=look(bands(top_hue=7)))
    b = types.SimpleNamespace(id=3, label="USER1", name="Ali", source="look", box=(100, 100, 100, 260), vel=(0, 0),
                              crowded=False, look=look(bands(top_hue=4)))
    out = describe([a, b], zones, 1000, 1000)
    assert [e["who"] for e in out] == ["Ali ?", "Person 9"]
    assert out[0]["text"] == "Ali ? (green top) - standing"
    assert out[1]["text"] == "Person 9 (blue top) - bending or crouching - most likely at UR5e"
