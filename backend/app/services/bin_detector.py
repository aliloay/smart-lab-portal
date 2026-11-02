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
import threading
from typing import Optional

MODEL = os.path.join(os.path.dirname(__file__), "..", "..", "data", "models", "bin_detector.onnx")
CODE = "SLAB:D:REUSE_BIN_1"
CONF = float(os.getenv("BIN_DETECTOR_CONF", "0.45"))  # round 5 (owner video): 14/15 unseen, 1/429 false, 18/24 hard video views
SIZE = 640

_RT = None          # ("ort", session, input name) | ("cv2", net)
_LOADED = False
_LOCK = threading.Lock()   # requests run on worker threads: load each model exactly once (Gemini review 2026-11-02)


def _load(path: str):
    """ONNX file -> ("ort", session, input name) | ("cv2", net) | None when the file is missing."""
    if not os.path.exists(path):
        return None
    try:
        import onnxruntime as ort
        o = ort.SessionOptions()
        o.intra_op_num_threads, o.inter_op_num_threads = 2, 1
        s = ort.InferenceSession(path, o, providers=["CPUExecutionProvider"])
        return ("ort", s, s.get_inputs()[0].name)
    except ImportError:
        import cv2
        return ("cv2", cv2.dnn.readNetFromONNX(path))


def _runtime():
    global _RT, _LOADED
    if not _LOADED:
        with _LOCK:
            if not _LOADED:
                _RT = _load(MODEL)
                _LOADED = True               # only after the session exists: a second thread never sees None mid-load
    return _RT


def available() -> bool:
    ok = _runtime() is not None
    extras()                       # load the extra models now, not on the phone's first frame
    return ok


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


def detect(img, lb=None) -> Optional[dict]:
    """img: BGR array -> {"confidence", "box" (0..1 x/y/w/h)} for the best bin above CONF, else None.
    lb: a letterbox(img) already computed for this frame (detect_all shares one between all models)."""
    return _infer(_runtime(), CONF, img, lb)


def _run(rt, x):
    if rt[0] == "ort":
        out = rt[1].run(None, {rt[2]: x})[0]
    else:
        rt[1].setInput(x)
        out = rt[1].forward()
    import numpy as np
    out = np.asarray(out, dtype=np.float32)
    if out.ndim == 3:
        out = out[0]
    if out.ndim == 2 and out.shape[0] > out.shape[1]:          # (N, 4 + C) -> (4 + C, N): anchors outnumber rows
        out = out.T
    return out


def _box(cx, cy, bw, bh, s, px, py, size) -> dict:
    """letterboxed 640-px box -> 0..1 of the frame, clamped so width / height are never negative."""
    h, w = size
    x1 = min(float(w), max(0.0, (cx - bw / 2 - px) / s)); y1 = min(float(h), max(0.0, (cy - bh / 2 - py) / s))
    x2 = min(float(w), max(x1, (cx + bw / 2 - px) / s)); y2 = min(float(h), max(y1, (cy + bh / 2 - py) / s))
    return {"x": round(x1 / w, 4), "y": round(y1 / h, 4), "w": round((x2 - x1) / w, 4), "h": round((y2 - y1) / h, 4)}


def _infer(rt, conf_min: float, img, lb=None) -> Optional[dict]:
    if rt is None:
        return None
    import numpy as np
    x, s, px, py = lb or letterbox(img)
    out = _run(rt, x)
    if out.ndim != 2 or out.shape[0] != 5:                    # (5, N): cx, cy, w, h, score - one class only
        return None
    i = int(np.argmax(out[4]))
    conf = float(out[4, i])
    if conf < conf_min:
        return None
    return {"confidence": round(conf, 3), "box": _box(*(float(v) for v in out[:4, i]), s, px, py, img.shape[:2])}



# ------------------------------------------------------------------ more objects (2026-10-29) ---
# data/models/detectors.json lists further one-object models next to the bin's, same pre/post-processing:
#   [{"file": "switch_detector.onnx", "class": "network_switch", "label": "Network switch", "conf": 0.5, "code": null}]
# code = a registered asset's code, or null for an object not in the registry (answered as "type:<class>").
# 2026-10-30: an entry may instead hold SEVERAL classes from one model, e.g. the combined bin + switch + router model
# trained in tools/vision_train (data/all_r1):
#   [{"file": "all_detector.onnx", "classes": [
#       {"index": 1, "name": "network_switch", "label": "Network switch (TP-Link)", "conf": 0.5, "code": null},
#       {"index": 2, "name": "network_router", "label": "Smart Lab router", "conf": 0.5, "code": null}]}]
# "name" must match the model's own class order; only the classes listed here are reported.
EXTRA = os.path.join(os.path.dirname(MODEL), "detectors.json")
_EXTRA = None


def extras() -> list:
    """[(spec, runtime)] for every listed model whose file exists (loaded once)."""
    global _EXTRA
    if _EXTRA is None:
        with _LOCK:
            if _EXTRA is None:
                loaded = []
                if os.path.exists(EXTRA):
                    import json
                    with open(EXTRA, encoding="utf-8") as f:
                        specs = json.load(f)
                    root = os.path.dirname(EXTRA)
                    loaded = [(s, rt) for s in specs if (rt := _load(os.path.join(root, s["file"]))) is not None]
                _EXTRA = loaded                   # published only when complete (another thread never sees half)
    return _EXTRA


def _parse_multi(out, spec: dict, size, s: float, px: int, py: int) -> list:
    """One model, several classes: out is (4 + N_classes, N) or (N, 4 + N_classes) - rows 4.. are one score per class.
    Pure on purpose (a test feeds it a hand-made array). Returns the best box per listed class above that class's conf."""
    import numpy as np
    out = np.asarray(out, dtype=np.float32)
    if out.ndim == 3:
        out = out[0]
    classes = spec.get("classes") or []
    if not classes:
        return []
    # orientation from the shape itself: anchors (8400) always outnumber the 4 + C rows. The spec may list only some of
    # the model's classes, so the file just needs at least the rows the highest listed index uses (Gemini review)
    if out.ndim != 2:
        return []
    if out.shape[0] > out.shape[1]:
        out = out.T
    need = 4 + max(int(c.get("index", k)) for k, c in enumerate(classes)) + 1
    if out.shape[0] < need:
        return []
    hits = []
    for k, c in enumerate(classes):
        i = int(c.get("index", k))
        if 4 + i >= out.shape[0]:
            continue
        scores = out[4 + i]
        j = int(np.argmax(scores))
        conf = float(scores[j])
        if conf < float(c.get("conf", spec.get("conf", 0.5))):
            continue
        hits.append({"code": c.get("code") or f"type:{c['name']}", "class": c["name"], "label": c.get("label"),
                     "confidence": round(conf, 3), "box": _box(*(float(v) for v in out[:4, j]), s, px, py, size)})
    return hits


def _infer_multi(rt, spec: dict, img, lb=None) -> list:
    if rt is None:
        return []
    x, s, px, py = lb or letterbox(img)
    return _parse_multi(_run(rt, x), spec, img.shape[:2], s, px, py)


def detect_all(img) -> list:
    """The bin model plus every model in detectors.json -> every hit above its threshold, most confident first:
    [{"code", "class", "label", "confidence", "box"}, ...]."""
    hits = []
    lb = letterbox(img)                      # one resize / colour / normalise for every model (all use 640 + grey 114)
    d = detect(img, lb)
    if d:
        hits.append({"code": CODE, "class": None, "label": None, **d})
    for spec, rt in extras():
        if spec.get("classes"):
            hits += _infer_multi(rt, spec, img, lb)
            continue
        e = _infer(rt, float(spec.get("conf", 0.5)), img, lb)
        if e:
            hits.append({"code": spec.get("code") or f"type:{spec['class']}", "class": spec["class"],
                         "label": spec.get("label"), **e})
    return sorted(hits, key=lambda h: -h["confidence"])


def detect_any(img) -> Optional[dict]:
    """The most confident hit of detect_all, or None."""
    hits = detect_all(img)
    return hits[0] if hits else None
