"""Measured body pose (pose.py, 2026-11-21 audit F-16). Synthetic model outputs in the real YOLOv8-pose layout
(1 x 56 x N) - no model file, no camera, no people."""
import time
from types import SimpleNamespace

import numpy as np

import pose
from activity import describe


def _raw(people):
    """people: [(cx, cy, w, h, score, [(x, y, conf) x 17])] in 640-letterbox pixels -> (1, 56, N)."""
    a = np.zeros((56, len(people)), np.float32)
    for j, (cx, cy, w, h, s, kps) in enumerate(people):
        a[:5, j] = (cx, cy, w, h, s)
        a[5:, j] = np.array(kps, np.float32).reshape(-1)
    return a[None]


def _kps(conf_by_index=None, x=300.0, y=200.0):
    conf_by_index = conf_by_index or {}
    return [(x + i, y + 10 * i, conf_by_index.get(i, 0.9)) for i in range(17)]


def test_decode_maps_back_to_frame_pixels_and_drops_weak_people():
    raw = _raw([(320, 320, 100, 300, 0.9, _kps()), (100, 100, 20, 20, 0.1, _kps())])
    out = pose.decode(raw, scale=0.5, px=0, py=80)
    assert len(out) == 1
    x, y, w, h = out[0]["box"]
    assert (round(x), round(y), round(w), round(h)) == (540, 180, 200, 600)       # (320-50)/0.5, (320-150-80)/0.5
    assert abs(out[0]["kps"][0][2] - 0.9) < 1e-6 and round(out[0]["kps"][0][0]) == 600


def test_nms_keeps_one_box_per_person():
    p = (320, 320, 100, 300, 0.9, _kps())
    q = (322, 321, 100, 300, 0.8, _kps())
    assert len(pose.decode(_raw([p, q]), 1.0, 0, 0)) == 1


def test_low_confidence_joints_are_occluded_never_invented():
    kps = _kps({9: 0.2, 10: 0.1, 15: 0.3, 16: 0.2})               # both wrists and both ankles weak
    v = pose.measured_visibility(kps)
    assert v["wrists"] == {"state": "OCCLUDED", "confidence": 0.2, "xy": None, "basis": "keypoint_model"}
    assert v["ankles"]["state"] == "OCCLUDED" and v["ankles"]["xy"] is None
    assert v["head"]["state"] == "OBSERVED" and v["head"]["basis"] == "keypoint_model"
    assert v["torso"]["state"] == "OBSERVED"                        # shoulders and hips trusted


def test_torso_needs_both_shoulders_and_hips():
    v = pose.measured_visibility(_kps({11: 0.1, 12: 0.2}))         # hips hidden (behind a desk)
    assert v["hips"]["state"] == "OCCLUDED" and v["torso"]["state"] == "OCCLUDED"


def test_attach_matches_by_overlap_and_one_pose_per_track():
    a = SimpleNamespace(box=(100, 100, 50, 150))
    b = SimpleNamespace(box=(400, 100, 50, 150))
    poses = [{"box": (402, 102, 50, 150), "score": 0.9, "kps": _kps()},
             {"box": (1000, 1000, 10, 10), "score": 0.9, "kps": _kps()}]       # matches nobody
    assert pose.attach([a, b], poses, now=100.0) == 1
    assert not hasattr(a, "kp") and b.kp_at == 100.0


def test_old_pose_is_not_used():
    t = SimpleNamespace(box=(0, 0, 10, 10), kp=_kps(), kp_at=time.time() - pose.FRESH_S - 1)
    assert pose.fresh_kps(t) is None
    t.kp_at = time.time()
    assert pose.fresh_kps(t) is not None


def test_describe_uses_measured_pose_when_fresh_else_box_estimate():
    base = dict(id=1, label=None, name=None, source=None, lab_no=3, look=None, crowded=False, vel=(0.0, 0.0), hint=None)
    with_pose = SimpleNamespace(box=(300, 100, 120, 360), kp=_kps(), kp_at=time.time(), **base)
    without = SimpleNamespace(box=(300, 100, 120, 360), **base)
    a = describe([with_pose], [], 1280, 720)[0]["pose_visibility"]
    b = describe([without], [], 1280, 720)[0]["pose_visibility"]
    assert a["head"]["basis"] == "keypoint_model" and a["head"]["state"] == "OBSERVED"
    assert b["head"]["basis"] == "box_geometry" and b["head"]["state"] != "OBSERVED"


def test_no_model_file_means_pose_off(tmp_path, monkeypatch):
    assert pose.PoseModel.load(str(tmp_path / "missing.onnx")) is None
    monkeypatch.setenv("SMARTLAB_POSE", "0")
    assert pose.PoseModel.load(pose.DEFAULT_PATH) is None
