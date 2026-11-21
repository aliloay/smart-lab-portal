"""Measured body pose for tracked people (2026-11-21, audit F-16).

Before this, body parts came from box proportions only (activity.pose_visibility, basis "box_geometry"). This module
runs a real keypoint model - YOLOv8-pose in ONNX format, 17 COCO keypoints, each with its own confidence - on the
whole frame at a limited rate, matches each pose to its tracked person by box overlap and gives the track MEASURED
joints. Rules (the owner's): a joint below MIN_KP_CONF is reported OCCLUDED with no position - never invented; a pose
older than FRESH_S is not used; with no model file the cameras behave exactly as before.

Model file: models/yolov8n-pose.onnx (input 1x3x640x640, output 1x56xN: box, score, 17 x (x, y, conf)).
Turn off with SMARTLAB_POSE=0; rate with SMARTLAB_POSE_EVERY_S (default 0.5 s = at most 2 pose passes a second).
"""
from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np

COCO_KP = ("nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_elbow",
           "right_elbow", "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee", "right_knee",
           "left_ankle", "right_ankle")
# our body parts (activity.BODY_KEYPOINTS names) -> COCO keypoint indices
PART_KP = {"head": (0, 1, 2, 3, 4), "shoulders": (5, 6), "elbows": (7, 8), "wrists": (9, 10), "hips": (11, 12),
           "knees": (13, 14), "ankles": (15, 16)}
MIN_KP_CONF = 0.5           # below this a joint is not trusted: OCCLUDED, no xy
MIN_PERSON = 0.35           # pose box score
MATCH_IOU = 0.3             # pose box <-> track box
FRESH_S = 1.5               # a pose older than this is not shown
INPUT = 640
DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "yolov8n-pose.onnx")


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix, iy = max(0.0, min(ax + aw, bx + bw) - max(ax, bx)), max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    u = aw * ah + bw * bh - inter
    return inter / u if u > 0 else 0.0


def letterbox(frame: np.ndarray, size: int = INPUT):
    h, w = frame.shape[:2]
    s = min(size / w, size / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    import cv2
    img = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    out = np.full((size, size, 3), 114, np.uint8)
    px, py = (size - nw) // 2, (size - nh) // 2
    out[py:py + nh, px:px + nw] = img
    x = out[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0   # BGR -> RGB, NCHW
    return np.ascontiguousarray(x), s, px, py


def decode(raw: np.ndarray, scale: float, px: int, py: int, min_score: float = MIN_PERSON, iou_thr: float = 0.5) -> list:
    """(1, 56, N) -> [{box: (x, y, w, h), score, kps: [(x, y, conf) x 17]}] in original frame pixels."""
    a = raw[0] if raw.ndim == 3 else raw
    if a.shape[0] != 56 and a.shape[-1] == 56:
        a = a.T
    keep = a[4] >= min_score
    a = a[:, keep]
    if a.shape[1] == 0:
        return []
    cx, cy, bw, bh = a[0], a[1], a[2], a[3]
    boxes = np.stack([(cx - bw / 2 - px) / scale, (cy - bh / 2 - py) / scale, bw / scale, bh / scale], 1)
    scores = a[4]
    order, chosen = np.argsort(-scores), []
    for i in order:                                   # greedy NMS (few people: plain Python is fine)
        if all(_iou(boxes[i], boxes[j]) < iou_thr for j in chosen):
            chosen.append(i)
    out = []
    for i in chosen:
        k = a[5:, i].reshape(17, 3)
        kps = [(float((x - px) / scale), float((y - py) / scale), float(c)) for x, y, c in k]
        out.append({"box": tuple(float(v) for v in boxes[i]), "score": float(scores[i]), "kps": kps})
    return out


def attach(tracks, poses: list, now: Optional[float] = None) -> int:
    """Give each track the pose whose box overlaps it most (>= MATCH_IOU); one pose per track. Returns matches."""
    now = time.time() if now is None else now
    used, n = set(), 0
    for t in tracks:
        best, bi = 0.0, None
        for i, p in enumerate(poses):
            if i in used:
                continue
            o = _iou(t.box, p["box"])
            if o > best:
                best, bi = o, i
        if bi is not None and best >= MATCH_IOU:
            used.add(bi)
            t.kp, t.kp_at, t.kp_score = poses[bi]["kps"], now, poses[bi]["score"]
            n += 1
    return n


def fresh_kps(t, now: Optional[float] = None):
    kp, at = getattr(t, "kp", None), getattr(t, "kp_at", None)
    if kp is None or at is None:
        return None
    return kp if ((time.time() if now is None else now) - at) <= FRESH_S else None


def measured_visibility(kps) -> dict:
    """Per body part from MEASURED keypoints: OBSERVED (xy = mean of the trusted joints, confidence = their mean) or
    OCCLUDED (no xy) when no joint of that part reaches MIN_KP_CONF. The torso needs a trusted shoulder AND hip."""
    out = {}
    for part, idx in PART_KP.items():
        ok = [kps[i] for i in idx if kps[i][2] >= MIN_KP_CONF]
        if ok:
            out[part] = {"state": "OBSERVED", "confidence": round(sum(c for _, _, c in ok) / len(ok), 2),
                         "xy": (round(sum(x for x, _, _ in ok) / len(ok), 1), round(sum(y for _, y, _ in ok) / len(ok), 1)),
                         "basis": "keypoint_model"}
        else:
            best = max(kps[i][2] for i in idx)
            out[part] = {"state": "OCCLUDED", "confidence": round(best, 2), "xy": None, "basis": "keypoint_model"}
    sh, hp = out["shoulders"], out["hips"]
    if sh["state"] == "OBSERVED" and hp["state"] == "OBSERVED":
        out["torso"] = {"state": "OBSERVED", "confidence": round(min(sh["confidence"], hp["confidence"]), 2),
                        "xy": (round((sh["xy"][0] + hp["xy"][0]) / 2, 1), round((sh["xy"][1] + hp["xy"][1]) / 2, 1)),
                        "basis": "keypoint_model"}
    else:
        out["torso"] = {"state": "OCCLUDED", "confidence": round(min(sh["confidence"], hp["confidence"]), 2),
                        "xy": None, "basis": "keypoint_model"}
    return out


class PoseModel:
    """The keypoint model on the GTX 1650 (DirectML) when it works, otherwise the CPU. None-safe: `load()` returns
    None when the file is missing or SMARTLAB_POSE=0, and the camera service then simply skips pose."""

    def __init__(self, sess, input_name: str, engine: str):
        self.sess, self.input, self.engine = sess, input_name, engine
        self.ms: list[float] = []

    @classmethod
    def load(cls, path: str = DEFAULT_PATH) -> Optional["PoseModel"]:
        if os.environ.get("SMARTLAB_POSE", "1") == "0" or not os.path.isfile(path):
            return None
        import onnxruntime as ort
        dev = int(os.environ.get("SMARTLAB_POSE_DML_DEVICE", "1"))        # this laptop: GTX 1650 = DirectML device 1
        if "DmlExecutionProvider" in ort.get_available_providers():
            try:
                so = ort.SessionOptions()
                so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
                s = ort.InferenceSession(path, so, providers=[("DmlExecutionProvider", {"device_id": dev})])
                return cls(s, s.get_inputs()[0].name, f"directml-gpu{dev}")
            except Exception:
                pass
        s = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        return cls(s, s.get_inputs()[0].name, "cpu")

    def infer(self, frame: np.ndarray) -> list:
        x, s, px, py = letterbox(frame)
        t = time.perf_counter()
        raw = self.sess.run(None, {self.input: x})[0]
        self.ms = (self.ms + [(time.perf_counter() - t) * 1000])[-100:]
        return decode(raw, s, px, py)
