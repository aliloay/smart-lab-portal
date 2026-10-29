"""
Reusable-bin detector (2026-10-28, owner: "detect the bin on the floor, on the table, near and far").
A YOLO model trained on the owner's photos (tools/vision_train), exported to ONNX. It answers only "is the reusable
bin in this frame, and where"; there is one reusable bin, so a detection names SLAB:D:REUSE_BIN_1. Used by
/scan/appearance when the photo matcher says UNKNOWN. A hint like the matcher: identity and live data still come from
the QR marker.
Runtime: ONNX Runtime on the CPU (2 threads - the GPU stays with the cameras); OpenCV's DNN module as a fallback
(2026-10-29: OpenCV DNN took ~525 ms a frame for this model).
"""
import os
from typing import Optional

MODEL = os.path.join(os.path.dirname(__file__), "..", "..", "data", "models", "bin_detector.onnx")
CODE = "SLAB:D:REUSE_BIN_1"
CONF = float(os.getenv("BIN_DETECTOR_CONF", "0.4"))   # round 4: no-bin pictures top out at 0.19 (eval_bin.py)
SIZE = 640

_RT = None          # ("ort", session, input name) | ("cv2", net)
_LOADED = False


def _runtime():
    global _RT, _LOADED
    if not _LOADED:
        _LOADED = True
        if os.path.exists(MODEL):
            try:
                import onnxruntime as ort
                o = ort.SessionOptions()
                o.intra_op_num_threads, o.inter_op_num_threads = 2, 1
                s = ort.InferenceSession(MODEL, o, providers=["CPUExecutionProvider"])
                _RT = ("ort", s, s.get_inputs()[0].name)
            except ImportError:
                import cv2
                _RT = ("cv2", cv2.dnn.readNetFromONNX(MODEL))
    return _RT


def available() -> bool:
    return _runtime() is not None


def engine() -> Optional[str]:
    rt = _runtime()
    return rt[0] if rt else None


def letterbox(img):
    """BGR frame -> (1, 3, 640, 640) float RGB 0..1, the frame centred on grey 114 as in training; scale, pad x, pad y."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    s = SIZE / max(h, w)
    nh, nw = int(round(h * s)), int(round(w * s))
    px, py = (SIZE - nw) // 2, (SIZE - nh) // 2
    pad = np.full((SIZE, SIZE, 3), 114, np.uint8)
    pad[py:py + nh, px:px + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    x = pad[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(x), s, px, py


def detect(img) -> Optional[dict]:
    """img: BGR array -> {"confidence", "box" (0..1 x/y/w/h)} for the best bin above CONF, else None."""
    rt = _runtime()
    if rt is None:
        return None
    import numpy as np
    x, s, px, py = letterbox(img)
    if rt[0] == "ort":
        out = rt[1].run(None, {rt[2]: x})[0][0]
    else:
        rt[1].setInput(x)
        out = rt[1].forward()[0]
    if out.shape[0] != 5:                                     # (5, N): cx, cy, w, h, score (one class)
        out = out.T
    i = int(np.argmax(out[4]))
    conf = float(out[4, i])
    if conf < CONF:
        return None
    h, w = img.shape[:2]
    cx, cy, bw, bh = (float(v) for v in out[:4, i])
    x1, y1 = max(0.0, (cx - bw / 2 - px) / s), max(0.0, (cy - bh / 2 - py) / s)
    x2, y2 = min(float(w), (cx + bw / 2 - px) / s), min(float(h), (cy + bh / 2 - py) / s)
    return {"confidence": round(conf, 3),
            "box": {"x": round(x1 / w, 4), "y": round(y1 / h, 4), "w": round((x2 - x1) / w, 4), "h": round((y2 - y1) / h, 4)}}
