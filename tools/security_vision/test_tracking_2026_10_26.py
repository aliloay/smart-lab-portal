"""Tracking changes chosen on reviewed lab clips (2026-10-26, docs/CV_BENCHMARK_2026-10-26.md):
low-confidence second stage, a separate new-track threshold, upper-body part boxes, rectangular detector input."""
import os

import numpy as np
import pytest

import vision
from vision import Tracker, drop_slivers

MODELS = os.path.join(os.path.dirname(__file__), "models")


def run(tr, frames, t0=0.0, dt=0.1, **kw):
    out = None
    for i, f in enumerate(frames):
        boxes, low = f if isinstance(f, tuple) else (f, None)
        out = tr.update(boxes, t0 + i * dt, low=low, **kw)
    return out


def test_low_confidence_box_keeps_a_confirmed_person():
    """A seated person behind a monitor drops to 0.2-0.3 for a while: the track (and its name) must survive."""
    p = (100, 100, 40, 90)
    tr = Tracker()
    run(tr, [[p]] * 5)                                   # confirmed
    tid = tr.tracks[0].id
    out = run(tr, [([], [p])] * 30, t0=0.5)             # 3 s of LOW boxes only (longer than MAX_MISS_S)
    assert [t.id for t in out] == [tid] and len(tr.tracks) == 1


def test_low_confidence_box_never_starts_a_person():
    tr = Tracker()
    out = run(tr, [([], [(300, 100, 40, 90)])] * 20)
    assert out == [] and tr.tracks == []


def test_low_box_must_overlap_where_the_track_is():
    tr = Tracker()
    run(tr, [[(100, 100, 40, 90)]] * 5)
    run(tr, [([], [(400, 100, 40, 90)])] * 30, t0=0.5)   # a low box elsewhere is not this person
    assert all(t.box[0] == 100 for t in tr.tracks)


def test_without_low_boxes_the_old_behaviour_is_unchanged():
    tr = Tracker()
    run(tr, [[(100, 100, 40, 90)]] * 5)
    out = run(tr, [[]] * 30, t0=0.5)
    assert out == []                                     # gone after the miss window, as before


def test_weak_confident_box_may_extend_but_not_start_a_track():
    p, q = (100, 100, 40, 90), (400, 100, 40, 90)
    tr = Tracker()
    run(tr, [[p]] * 5)
    out = run(tr, [[p, q]] * 10, t0=0.5, starts=[True, False])   # q scored 0.35-0.60: no new person
    assert len(out) == 1 and len(tr.tracks) == 1
    out = run(tr, [[p, q]] * 5, t0=1.5, starts=[True, True])     # once it scores >= 0.60 it may start
    assert len(tr.tracks) == 2


def test_upper_body_part_box_is_dropped_but_a_person_behind_is_kept():
    whole = (100, 50, 60, 150)
    upper = (102, 52, 55, 70)                            # same top, similar width, inside: same person
    behind = (110, 110, 50, 80)                          # seated behind: lower top edge -> kept
    assert drop_slivers([whole, upper]) == [whole]
    assert set(drop_slivers([whole, behind])) == {whole, behind}
    assert set(drop_slivers([whole, upper], parts=False)) == {whole, upper}


@pytest.mark.skipif(not os.path.isfile(os.path.join(MODELS, "yolo26s_544x960.onnx")), reason="model not downloaded")
def test_rectangular_model_reads_its_input_shape_and_finds_a_person():
    d = vision.Yolo26Detector(os.path.join(MODELS, "yolo26s_544x960.onnx"), conf=0.35)
    assert d.in_hw == (544, 960)
    img = np.full((540, 960, 3), 200, np.uint8)
    assert d.detect(img) == []                           # an empty grey frame: nobody
    assert d.detect(img, conf=0.15) == []                # the low threshold adds no ghosts on it
