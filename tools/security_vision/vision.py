"""
Security camera vision: detection, tracking, name labels, equipment zones.

Pure functions and small classes with no network or camera access, so each
piece can be tested on its own (test_vision.py). security_vision.py wires
them to the camera, the portal and the HTTP endpoints.

    Detector      YOLOX-S (OpenCV model zoo, ONNX) on the CPU through cv2.dnn
    Appearance    what a person looks like: clothing / hair colours, plus a
                  body re-identification model when its file is present
    Tracker       keeps an id on each person from frame to frame (overlap,
                  motion and appearance)
    Labeler       puts a name on a track only when the door data makes it
                  certain, then LOCKS it to that person's look: names follow
                  the person through crossings and short disappearances;
                  otherwise the track stays "Unknown"
    ZoneWatcher   compares each equipment box with how it normally looks
"""
from __future__ import annotations

import itertools
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import os

import cv2
import numpy as np

# COCO class ids the security view cares about (the model knows 80).
PERSON = 0
SHOWN = {0: "person", 62: "monitor", 63: "laptop", 66: "keyboard", 64: "mouse"}


# --------------------------------------------------------------- detector ---
# ONE GPU user at a time. The NVIDIA driver (nvwgf2umx.dll) crashed python with an access violation
# when a second DirectML model was created/run while analysis used the GPU (4 crashes at the lab
# 2026-10-14; reproduced: 2 of 2 runs crash without this lock). Every DirectML session creation and
# run below takes it. Re-entrant; never held while taking another lock.
GPU_LOCK = threading.RLock()


def _gpu_run(sess, feeds):
    with GPU_LOCK:
        return sess.run(None, feeds)[0]


@dataclass
class Detection:
    cls: int
    score: float
    box: tuple  # x, y, w, h in pixels of the analysed frame


class Detector:
    """YOLOX-S, 640x640, 80 COCO classes (opencv_zoo object_detection_yolox)."""

    def __init__(self, path: str, conf: float = 0.45, nms: float = 0.45, size: int = 640):
        self.net = cv2.dnn.readNet(path)
        self.conf, self.nms, self.size = conf, nms, size
        grids, strides = [], []
        for s in (8, 16, 32):
            n = size // s
            xv, yv = np.meshgrid(np.arange(n), np.arange(n))
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((n * n, 1), s))
        self.grids = np.concatenate(grids).astype(np.float32)
        self.strides = np.concatenate(strides).astype(np.float32)

    def detect(self, img: np.ndarray) -> list[Detection]:
        h, w = img.shape[:2]
        r = min(self.size / h, self.size / w)
        nw, nh = int(round(w * r)), int(round(h * r))
        pad = np.full((self.size, self.size, 3), 114, np.uint8)
        pad[:nh, :nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        blob = pad.transpose(2, 0, 1)[None].astype(np.float32)   # BGR, 0-255, as YOLOX trains
        self.net.setInput(blob)
        out = self.net.forward()[0]
        xy = (out[:, :2] + self.grids) * self.strides
        wh = np.exp(out[:, 2:4]) * self.strides
        scores = out[:, 4:5] * out[:, 5:]
        cls = scores.argmax(1)
        best = scores[np.arange(len(cls)), cls]
        keep = best > self.conf
        if not keep.any():
            return []
        xy, wh, best, cls = xy[keep], wh[keep], best[keep], cls[keep]
        boxes = np.concatenate([xy - wh / 2, wh], 1) / r
        idx = cv2.dnn.NMSBoxesBatched(boxes.tolist(), best.tolist(), cls.tolist(), self.conf, self.nms)
        dets = []
        for i in np.array(idx).flatten():
            x, y, bw, bh = boxes[i]
            x, y = max(0.0, x), max(0.0, y)
            bw, bh = min(bw, w - x), min(bh, h - y)
            dets.append(Detection(int(cls[i]), float(best[i]), (float(x), float(y), float(bw), float(bh))))
        return dets


class Yolo26Detector:
    """Ultralytics YOLO26 (AGPL-3.0), exported to ONNX, run with ONNX Runtime
    (OpenCV's dnn runs it ~8x slower). Same interface as Detector.
    Output (1, 84, N): cx, cy, w, h on the 640 letterbox + 80 COCO class scores.
    Measured on 30 lab frames (2026-10-12, 8 threads, 640 px, conf 0.45):
    2.97 of 3 people at 147 ms - YOLOX-S needed 510 ms for the same.
    Runs on OpenVINO (CPU) when it is installed: measured 2026-10-13 on 23 lab
    frames, 123 ms vs 160 ms per frame with ONNX Runtime and the SAME people
    found in every frame. OpenVINO's GPU path crashes on this laptop's driver,
    so only its CPU device is used; any OpenVINO failure falls back to ONNX
    Runtime. SMARTLAB_DETECTOR=onnxruntime forces the old engine.
    First choice: the graphics card through DirectML (onnxruntime-directml):
    measured 2026-10-13, NVIDIA GTX 1650 30 ms/frame, same people in all 23
    frames (the Intel iGPU 165 ms - so the fastest DirectML device is picked
    by timing at start-up). SMARTLAB_DETECTOR=openvino skips the GPU."""

    def __init__(self, path: str, conf: float = 0.45, nms: float = 0.45, size: int = 640,
                 threads: int = 8):
        self.conf, self.nms, self.size = conf, nms, size
        self.engine, self._ov, self.sess = "onnxruntime", None, None
        want = os.environ.get("SMARTLAB_DETECTOR", "gpu").lower()
        if want == "gpu":
            self._try_directml(path)
        if self.sess is None and want in ("gpu", "openvino"):
            try:
                import openvino as ov
                cm = ov.Core().compile_model(path, "CPU", {"PERFORMANCE_HINT": "LATENCY",
                                                           "INFERENCE_NUM_THREADS": threads})
                self._ov, self.engine = cm.create_infer_request(), "openvino-cpu"
            except Exception as e:                          # not installed / failed: old engine
                print(f"[detector] OpenVINO unavailable ({e.__class__.__name__}) - using ONNX Runtime")
        if self._ov is None and self.sess is None:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.intra_op_num_threads = threads
            self.sess = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
            self.input = self.sess.get_inputs()[0].name
        print(f"[detector] YOLO26 on {self.engine}")

    def _try_directml(self, path: str) -> None:
        """The fastest DirectML device (graphics card), if it beats the CPU clearly."""
        with GPU_LOCK:
            self._try_directml_locked(path)

    def _try_directml_locked(self, path: str) -> None:
        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" not in ort.get_available_providers():
                return
            x = np.zeros((1, 3, self.size, self.size), np.float32)
            best = None
            for dev in range(int(os.environ.get("SMARTLAB_DML_DEVICES", "2"))):   # this laptop: iGPU 0, GTX 1650 1
                try:
                    so = ort.SessionOptions()           # whole graph on the GPU or not at all (no silent CPU nodes;
                    so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")   # verified 2026-10-14)
                    s = ort.InferenceSession(path, so, providers=[("DmlExecutionProvider", {"device_id": dev})])
                except Exception:
                    break                                   # no more devices
                i = s.get_inputs()[0].name
                s.run(None, {i: x})
                t = time.perf_counter()
                for _ in range(3):
                    s.run(None, {i: x})
                ms = (time.perf_counter() - t) / 3 * 1000
                if best is None or ms < best[0]:
                    best = (ms, dev, s, i)
            # The GPU wakes from its idle power state (P8) slowly: one timing at start-up said
            # >80 ms and the detector ran on the CPU all session (lab 2026-10-14, 23 ms when
            # re-tested). Re-measure the best device a few times before giving up.
            tries = 0
            while best and best[0] >= 80 and tries < 4:
                tries += 1
                time.sleep(1.5)
                xb = np.zeros((1, 3, self.size, self.size), np.float32)
                t = time.perf_counter()
                for _ in range(3):
                    best[2].run(None, {best[3]: xb})
                best = (min(best[0], (time.perf_counter() - t) / 3 * 1000), best[1], best[2], best[3])
            if best and best[0] >= 80:
                print(f"[detector] GPU {best[1]} measured {best[0]:.0f} ms (limit 80) - using the CPU")
            if best and best[0] < 80:                       # a real GPU, not slower than the CPU
                _, dev, self.sess, self.input = best
                self.engine = f"directml-gpu{dev} ({best[0]:.0f} ms)"
        except Exception as e:
            print(f"[detector] DirectML unavailable ({e.__class__.__name__})")

    def _infer(self, blob: np.ndarray) -> np.ndarray:
        if self._ov is not None:
            return self._ov.infer({0: blob})[0]
        with GPU_LOCK:
            return self.sess.run(None, {self.input: blob})[0]

    def detect(self, img: np.ndarray) -> list[Detection]:
        h, w = img.shape[:2]
        r = min(self.size / h, self.size / w)
        nw, nh = int(round(w * r)), int(round(h * r))
        pad = np.full((self.size, self.size, 3), 114, np.uint8)
        pad[:nh, :nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        blob = pad[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0   # RGB, 0-1
        out = self._infer(blob)[0].T                                                 # N x 84
        scores = out[:, 4:]
        cls = scores.argmax(1)
        best = scores[np.arange(len(cls)), cls]
        keep = best > self.conf
        if not keep.any():
            return []
        b, best, cls = out[keep, :4], best[keep], cls[keep]
        boxes = np.concatenate([b[:, :2] - b[:, 2:4] / 2, b[:, 2:4]], 1) / r
        idx = cv2.dnn.NMSBoxesBatched(boxes.tolist(), best.tolist(), cls.tolist(), self.conf, self.nms)
        dets = []
        for i in np.array(idx).flatten():
            x, y, bw, bh = boxes[i]
            x, y = max(0.0, x), max(0.0, y)
            bw, bh = min(bw, w - x), min(bh, h - y)
            dets.append(Detection(int(cls[i]), float(best[i]), (float(x), float(y), float(bw), float(bh))))
        return dets


def make_detector(path: str, conf: float = 0.45, size: int = 640, threads: int = 8):
    """YOLO26 for a yolo26*.onnx file, else the YOLOX detector."""
    if "yolo26" in os.path.basename(path).lower():
        return Yolo26Detector(path, conf=conf, size=size, threads=threads)
    return Detector(path, conf=conf, size=size)


# ------------------------------------------------------------- appearance ---
HUE_BINS, VAL_BINS = 12, 4
BODY_PARTS = ((0.0, 0.18), (0.18, 0.55), (0.55, 1.0))    # head/hair, upper body, legs


EQUIPMENT_CLASSES = {62: "Monitor", 63: "Laptop"}


def find_equipment(det: Detector, img: np.ndarray, *, nx: int = 3, ny: int = 2, overlap: float = 0.25,
                   min_score: float = 0.30, contain: float = 0.7, lock=None) -> list[Detection]:
    """Monitors / laptops for "Find equipment" (on demand, so it can be slow):
    the whole picture plus overlapping tiles, so small far-away screens become
    big enough to recognise. Measured on the lab camera (2026-10-07): live
    settings found 3 monitors, this finds 7 real ones.
      * below min_score is dropped (chair backs, keyboards scored 0.22-0.25);
      * a box that mostly contains another (a cabinet around a monitor, a
        monitor's stand under it) keeps only the more confident of the two.
    `lock` is taken per pass, not for the whole search (~0.6 s each, 7
    passes): the live people detection keeps running in between."""
    import contextlib
    held = lock if lock is not None else contextlib.nullcontext()

    def run(part):
        with held:
            return det.detect(part)
    h, w = img.shape[:2]
    tw, th = int(w / (nx - (nx - 1) * overlap)), int(h / (ny - (ny - 1) * overlap))
    found: list[Detection] = list(run(img))
    for j in range(ny):
        for i in range(nx):
            x0, y0 = int(i * tw * (1 - overlap)), int(j * th * (1 - overlap))
            for d in run(img[y0:min(h, y0 + th), x0:min(w, x0 + tw)]):
                bx, by, bw, bh = d.box
                found.append(Detection(d.cls, d.score, (bx + x0, by + y0, bw, bh)))
    found = [d for d in found if d.cls in EQUIPMENT_CLASSES and d.score >= min_score]
    found.sort(key=lambda d: -d.score)
    kept: list[Detection] = []
    for d in found:
        dx, dy, dw, dh = d.box
        clash = False
        for k in kept:
            kx, ky, kw, kh = k.box
            iw = max(0.0, min(dx + dw, kx + kw) - max(dx, kx))
            ih = max(0.0, min(dy + dh, ky + kh) - max(dy, ky))
            inter = iw * ih
            if inter >= contain * min(dw * dh, kw * kh) or iou(d.box, k.box) > 0.4:
                clash = True
                break
        if not clash:
            kept.append(d)
    return kept


def color_signature(frame: np.ndarray, box) -> Optional[np.ndarray]:
    """
    Colour histograms of the head, upper body and lower body, from the
    middle of the box (less background). Coloured pixels count by hue,
    black / grey / white ones by brightness. Each part sums to 1.
    """
    H, W = frame.shape[:2]
    x, y, w, h = box
    x0, x1 = int(max(0, x + 0.2 * w)), int(min(W, x + 0.8 * w))
    parts = []
    for a, b in BODY_PARTS:
        y0, y1 = int(max(0, y + a * h)), int(min(H, y + b * h))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int32)
        colored = (hsv[:, 1] > 50) & (hsv[:, 2] > 40)
        # Shift so red (hue ~0 and ~179) falls in one bin.
        hue = np.bincount(((hsv[colored, 0] + 7) % 180) * HUE_BINS // 180, minlength=HUE_BINS)
        val = np.bincount(hsv[~colored, 2] * VAL_BINS // 256, minlength=VAL_BINS)
        f = np.concatenate([hue, val]).astype(np.float32)
        parts.append(f / max(float(f.sum()), 1.0))
    return np.concatenate(parts)


@dataclass
class Look:
    color: Optional[np.ndarray] = None
    deep: Optional[np.ndarray] = None   # L2-normalised re-id embedding


def look_distance(a: Optional[Look], b: Optional[Look]) -> Optional[float]:
    """0 = looks the same, 1 = nothing alike. None when either is unknown."""
    if a is None or b is None:
        return None
    parts = []
    if a.color is not None and b.color is not None:
        bc = float(np.sqrt(a.color * b.color).sum()) / len(BODY_PARTS)    # Bhattacharyya, 0-1
        parts.append((0.4, math.sqrt(max(0.0, 1.0 - bc))))
    if a.deep is not None and b.deep is not None:
        parts.append((0.6, float(np.clip((1.0 - float(a.deep @ b.deep)) / 1.2, 0, 1))))
    if not parts:
        return None
    return sum(w * d for w, d in parts) / sum(w for w, _ in parts)


def blend(old: Optional[Look], new: Optional[Look], alpha: float) -> Optional[Look]:
    """Running average of a look (alpha = weight of the new one)."""
    if old is None or new is None:
        return new or old
    color = old.color if new.color is None else new.color if old.color is None \
        else (1 - alpha) * old.color + alpha * new.color
    deep = old.deep if new.deep is None else new.deep if old.deep is None \
        else (1 - alpha) * old.deep + alpha * new.deep
    if deep is not None:
        deep = deep / max(float(np.linalg.norm(deep)), 1e-6)
    return Look(color, deep)


class Appearance:
    """
    Looks for the detected people of a frame. Colours always; the body
    re-identification model (OpenCV zoo, person_reid_youtu_2021nov.onnx,
    CPU) when its file is present - it tells apart people in similar clothes.
    """
    REID_SIZE = (128, 256)
    MEAN = np.array([0.485, 0.456, 0.406], np.float32)
    STD = np.array([0.229, 0.224, 0.225], np.float32)

    # Re-id engine (2026-10-13 audit, docs/benchmarks/REID_GPU_AUDIT_2026-10-13.md):
    # cv2.dnn (OpenCV 4.10) returns CORRECT embeddings only for the first batch
    # size it ever runs - after the number of people changes they are unrelated
    # vectors (cosine ~ -0.1 vs ONNX Runtime). So every engine here runs ONE crop
    # at a time (fixed batch 1), which is also the fastest on the GTX 1650
    # (9 ms a crop vs 32 ms for a batch of 2). Order: DirectML (graphics card,
    # fastest adapter by timing) -> ONNX Runtime CPU -> cv2.dnn. SMARTLAB_REID=
    # cpu / opencv forces the later ones.
    def __init__(self, reid_path: Optional[str] = None):
        self.net = None                      # callable: (1,3,256,128) float32 -> (1, 768)
        self.engine = "colours only"
        if not reid_path:
            return
        want = os.environ.get("SMARTLAB_REID", "gpu").lower()
        try:
            import onnxruntime as ort
            if want == "gpu" and "DmlExecutionProvider" in ort.get_available_providers():
                with GPU_LOCK:   # released even if a device fails
                    x = np.zeros((1, 3, self.REID_SIZE[1], self.REID_SIZE[0]), np.float32)
                    best = None
                    for dev in range(int(os.environ.get("SMARTLAB_DML_DEVICES", "2"))):
                        try:
                            o = ort.SessionOptions()
                            o.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
                            sess = ort.InferenceSession(reid_path, o, providers=[("DmlExecutionProvider", {"device_id": dev})])
                        except Exception:
                            break
                        for _ in range(3):                 # warm-up (first runs compile)
                            sess.run(None, {"input": x})
                        runs = []
                        for _ in range(7):                 # median: one busy moment does not decide
                            t = time.perf_counter()
                            sess.run(None, {"input": x})
                            runs.append((time.perf_counter() - t) * 1000)
                        ms = float(np.median(runs))
                        if best is None or ms < best[0]:
                            best = (ms, dev, sess)
                    # One timing at start-up is fragile: launch.bat starts Docker, Ollama and this at once,
                    # and a busy moment pushed a 10 ms GPU over the limit -> CPU for the whole session
                    # (seen 2026-10-14). Re-measure the best device a few times before giving up.
                    tries = 0
                    while best and best[0] >= 25 and tries < 4:
                        tries += 1
                        time.sleep(1.5)
                        runs = []
                        for _ in range(7):
                            t = time.perf_counter()
                            best[2].run(None, {"input": x})
                            runs.append((time.perf_counter() - t) * 1000)
                        best = (min(best[0], float(np.median(runs))), best[1], best[2])
                    if best and best[0] >= 25:
                        print(f"[vision] re-id: GPU {best[1]} measured {best[0]:.0f} ms/crop (limit 25) - using the CPU")
                if best and best[0] < 25:            # a real GPU (CPU: ~30 ms a crop)
                    self.net = lambda b, s=best[2]: _gpu_run(s, {"input": b})
                    self.engine = f"directml-gpu{best[1]} ({best[0]:.0f} ms/crop)"
            if self.net is None and want in ("gpu", "cpu"):
                o = ort.SessionOptions()
                o.intra_op_num_threads = 4
                sess = ort.InferenceSession(reid_path, o, providers=["CPUExecutionProvider"])
                self.net = lambda b, s=sess: s.run(None, {"input": b})[0]
                self.engine = "onnxruntime-cpu"
        except Exception as e:
            print(f"[vision] re-id: ONNX Runtime unavailable ({e.__class__.__name__}) - trying OpenCV")
        if self.net is None:
            try:
                net = cv2.dnn.readNet(reid_path)
                def run(b, net=net):
                    net.setInput(b)
                    return net.forward()
                self.net, self.engine = run, "opencv-dnn-cpu"
            except cv2.error as e:     # half-downloaded or damaged file: colours only
                print(f"[vision] re-id model not usable ({e.__class__.__name__}): colours only")
        print(f"[vision] re-id on {self.engine}")

    DEEP_EVERY_S = 2.0                 # body model at least this often (~100 ms a person; was 1 s)...
    NEAR_HOLD_S = 2.0                  # ...and every frame while people are close / just apart

    _last_deep = -1e9
    _near_at = -1e9

    def wants_deep(self, boxes: list[tuple], now: float) -> bool:
        if any(_close(a, b) for a, b in itertools.combinations(boxes, 2)):
            self._near_at = now
        return now - self._near_at <= self.NEAR_HOLD_S or now - self._last_deep >= self.DEEP_EVERY_S

    def looks(self, frame: np.ndarray, boxes: list[tuple],
              now: Optional[float] = None) -> list[Optional[Look]]:
        out = [Look(color_signature(frame, b)) for b in boxes]
        if now is not None and not self.wants_deep(boxes, now):
            return out
        only = None
        if now is not None:
            # Speed (lab 2026-10-14, 8 people: re-ID for all of them every pass, 63 ms): while people
            # touch, only THEY need the body model every pass; everyone is refreshed every
            # DEEP_EVERY_S, and right after a separation (nobody touching now) all of them.
            close = {k for (i, a), (j, b) in itertools.combinations(enumerate(boxes), 2)
                     if _close(a, b) for k in (i, j)}
            if close and now - self._last_deep < self.DEEP_EVERY_S:
                only = close
            else:
                self._last_deep = now
        if self.net is not None and boxes:
            crops, idx = [], []
            H, W = frame.shape[:2]
            for i, (x, y, w, h) in enumerate(boxes):
                if only is not None and i not in only:
                    continue
                x0, y0 = int(max(0, x)), int(max(0, y))
                x1, y1 = int(min(W, x + w)), int(min(H, y + h))
                if x1 - x0 < 8 or y1 - y0 < 16:
                    continue
                img = cv2.resize(frame[y0:y1, x0:x1], self.REID_SIZE)[:, :, ::-1].astype(np.float32) / 255.0
                crops.append((img - self.MEAN) / self.STD)
                idx.append(i)
            for i, crop in zip(idx, crops):          # one crop at a time: see __init__
                try:
                    f = np.asarray(self.net(cv2.dnn.blobFromImage(crop))).reshape(-1)
                except Exception as e:               # a failed crop keeps its colours; tracking goes on
                    print(f"[vision] re-id failed on a crop ({e.__class__.__name__})")
                    continue
                out[i].deep = f / max(float(np.linalg.norm(f)), 1e-6)
        return out


# ---------------------------------------------------------------- tracker ---
def iou(a, b) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    box: tuple
    first_seen: float
    last_seen: float
    hits: int = 1
    label: Optional[str] = None        # door identity, e.g. USER2
    name: Optional[str] = None         # display name
    role: Optional[str] = None
    entered_at_door: bool = False      # first seen in the door area
    source: Optional[str] = None       # where the name came from: "door" or "face"
    entered: bool = False              # named AND inside per the door (else: on hold)
    verified: bool = False             # entered, and the face confirms the name
    mismatch: Optional[str] = None     # the face clearly says someone else (card sharing?)
    look: Optional[Look] = None        # this frame's look
    vel: tuple = (0.0, 0.0)            # centre speed, px/s
    crowded: bool = False              # touching someone else right now
    crowded_at: float = -1e9           # last time it was
    separated_at: float = -1e9         # when it last came apart from someone
    named_by: Optional[str] = None     # door / face / look / place / elimination (identity.py evidence)
    identity_state: str = "UNKNOWN"    # set by identity.IdentityLedger
    identity_confidence: float = 0.0

    def center(self):
        return (self.box[0] + self.box[2] / 2, self.box[1] + self.box[3] / 2)


def _center(b):
    return (b[0] + b[2] / 2, b[1] + b[3] / 2)


def _close(a, b) -> bool:
    """Two people boxes touching or nearly: their looks may mix."""
    if iou(a, b) > 0.02:
        return True
    (ax, ay), (bx, by) = _center(a), _center(b)
    return abs(ax - bx) < 0.6 * max(a[2], b[2]) and abs(ay - by) < 0.5 * max(a[3], b[3])


class Tracker:
    """
    Matches each person box to a track by overlap with where the track was
    heading (constant speed) and, when looks are given, by appearance - so
    two people crossing keep their own ids. A track survives short misses
    (MAX_MISS_S).
    """
    MAX_MISS_S = 2.0
    MIN_IOU = 0.25
    APPEAR_W = 0.6                     # weight of appearance against overlap
    APPEAR_GATE = 0.35                 # no overlap, but this alike and near: same person
    CONFIRM_HITS = 3                   # seen in this many frames before it counts

    def __init__(self):
        self.tracks: list[Track] = []
        self._next = 1

    @staticmethod
    def _predicted(t: Track, now: float):
        dt = min(max(now - t.last_seen, 0.0), 1.0)
        return (t.box[0] + t.vel[0] * dt, t.box[1] + t.vel[1] * dt, t.box[2], t.box[3])

    def update(self, boxes: list[tuple], now: float,
               looks: Optional[list[Optional[Look]]] = None) -> list[Track]:
        looks = looks if looks is not None else [None] * len(boxes)
        pairs = []
        for ti, t in enumerate(self.tracks):
            pred = self._predicted(t, now)
            for bi, b in enumerate(boxes):
                ov = iou(pred, b)
                d = look_distance(t.look, looks[bi])
                near = math.dist(_center(pred), _center(b)) < max(b[3], pred[3])
                if ov < self.MIN_IOU and not (d is not None and d < self.APPEAR_GATE and near):
                    continue
                pairs.append((ov + (self.APPEAR_W * (1 - d) if d is not None else 0.0), ti, bi))
        used_t, used_b = set(), set()
        for score, ti, bi in sorted(pairs, reverse=True):
            if ti in used_t or bi in used_b:
                continue
            t = self.tracks[ti]
            dt = now - t.last_seen
            if dt > 1e-3:
                (ox, oy), (nx, ny) = t.center(), _center(boxes[bi])
                t.vel = (0.5 * t.vel[0] + 0.5 * (nx - ox) / dt, 0.5 * t.vel[1] + 0.5 * (ny - oy) / dt)
            t.box, t.last_seen, t.hits = boxes[bi], now, t.hits + 1
            # While people touch, the box may hold parts of the other person:
            # the track keeps its last clean look (2026-10-12 root cause #2).
            touching = any(_close(boxes[bi], b2) for j, b2 in enumerate(boxes) if j != bi)
            if looks[bi] is not None and not touching:
                t.look = looks[bi]
            used_t.add(ti)
            used_b.add(bi)
        for bi, b in enumerate(boxes):
            if bi not in used_b:
                self.tracks.append(Track(self._next, b, now, now, look=looks[bi]))
                self._next += 1
        self.tracks = [t for t in self.tracks if now - t.last_seen <= self.MAX_MISS_S]
        live = [t for t in self.tracks if t.last_seen == now]
        for t in live:
            was = t.crowded
            t.crowded = any(o is not t and _close(t.box, o.box) for o in live)
            if t.crowded:
                t.crowded_at = now
            elif was:
                t.separated_at = now
        return self.confirmed(now)

    def confirmed(self, now: float) -> list[Track]:
        return [t for t in self.tracks if t.hits >= self.CONFIRM_HITS and now - t.last_seen < 0.6]


def predicted(tracks: list[Track], now: float) -> list[Track]:
    """Copies of the tracks moved on to `now` at their measured speed - for
    drawing between detections, so boxes keep up with people. At most
    MAX_AHEAD_S ahead: a long gap is not guessed across."""
    from dataclasses import replace
    out = []
    for t in tracks:
        dt = min(max(now - t.last_seen, 0.0), predicted.MAX_AHEAD_S)
        x, y, w, h = t.box
        out.append(replace(t, box=(x + t.vel[0] * dt, y + t.vel[1] * dt, w, h)))
    return out


predicted.MAX_AHEAD_S = 0.5


# ---------------------------------------------------------------- labeler ---
DOOR_GROW_W, DOOR_GROW_H = 1.5, 0.3     # door zone = door box + 1.5 door-widths each side, +30 % height
DOOR_OVERLAP = 0.15                     # this share of the person's box inside the zone = at the door


def zoom_people(det, frame, regions: list[tuple], existing: list[tuple], pad: float = 0.6,
                max_n: int = 2) -> list[tuple]:
    """People the full-frame pass missed. Two people seated close together come out as ONE box
    (lab 2026-10-14: Ali behind Nour - not detected at all, found at 0.76 in a zoomed crop).
    Re-detect in a crop around each region (where a named person was just lost), and return
    the people there that are not already a box (IoU < 0.3 with every existing box)."""
    h, w = frame.shape[:2]
    found: list[tuple] = []
    for (x, y, bw, bh) in regions[:max_n]:
        x0, y0 = max(0, int(x - pad * bw)), max(0, int(y - pad * bh))
        x1, y1 = min(w, int(x + bw * (1 + pad))), min(h, int(y + bh * (1 + pad)))
        if x1 - x0 < 16 or y1 - y0 < 16:
            continue
        for d in det.detect(frame[y0:y1, x0:x1]):
            if d.cls != PERSON:
                continue
            b = (d.box[0] + x0, d.box[1] + y0, d.box[2], d.box[3])
            def inside(a, e):                   # share of a lying inside e
                ix = max(0.0, min(a[0] + a[2], e[0] + e[2]) - max(a[0], e[0]))
                iy = max(0.0, min(a[1] + a[3], e[1] + e[3]) - max(a[1], e[1]))
                return ix * iy / max(a[2] * a[3], 1.0)
            # A sliver of a person already boxed is not a new person (lab frame: a 25 px wide
            # strip inside the next person's box); someone half behind another (Ali, 55 %) is.
            if all(iou(b, e) < 0.3 and inside(b, e) < 0.7 for e in existing + found):
                found.append(b)
    return found


def at_door(box, door_rect) -> bool:
    """A person coming through the door. The drawn door box is narrow and the detector sees a
    person only once most of the body is in view - by then the centre has left the box (lab
    2026-10-14: entry recorded, nobody named). So: the person's box overlaps the widened door zone."""
    if door_rect is None:
        return False
    dx, dy, dw, dh = door_rect
    zx, zy = dx - DOOR_GROW_W * dw, dy - DOOR_GROW_H / 2 * dh
    zw, zh = dw * (1 + 2 * DOOR_GROW_W), dh * (1 + DOOR_GROW_H)
    x, y, w, h = box
    ix = max(0.0, min(x + w, zx + zw) - max(x, zx))
    iy = max(0.0, min(y + h, zy + zh) - max(y, zy))
    return w * h > 0 and ix * iy / (w * h) >= DOOR_OVERLAP


def in_rect(pt, rect) -> bool:
    return rect is not None and rect[0] <= pt[0] <= rect[0] + rect[2] and rect[1] <= pt[1] <= rect[1] + rect[3]


@dataclass
class Identity:
    """A named person's locked look, learnt only while they stand alone."""
    look: Look
    samples: int = 1


class Labeler:
    """
    Names come from the door, never from guessing:

      * a person who appears in the DOOR AREA soon after a door grant gets
        the name of that entry;
      * when exactly one name inside is still unassigned and exactly one
        visible person is unlabelled, that person must be them;
      * everyone else stays "Unknown" - a wrong name is worse than none.

    A face can name a person too (face_vote, from the face server's
    templates): only after FACE_VOTES agreeing matches within FACE_WINDOW_S.
    Such a person keeps the name while in view, but is ON HOLD (entered =
    False) until the door records their entry - the camera says who, only
    the door says they came in properly. A door name is never overridden.

    Once named, the name is LOCKED to the person's look (clothes, hair,
    body), learnt only from frames where they stand clear of everyone:

      * after two or more people touch and come apart, the names go back
        to the looks they belong to (swapped if the tracker mixed them up);
      * someone who vanished for a moment (behind a robot, out of view)
        gets their name back when they reappear - only on a clear match,
        else they stay Unknown until the door or elimination says.

    occupants: [{"auth_subject", "name", "role", "entered_at" (epoch s)}]
    door_rect: the door area in frame pixels (x, y, w, h) or None.
    """
    ENTRY_MATCH_S = 25.0
    LOCK_SAMPLES = 3                   # alone-frames before a look can move a name
    SETTLE_S = 0.6                     # apart this long before names are re-checked
    SWAP_MARGIN = 0.05                 # a swap must fit this much better
    HANDBACK_SMALL_S = 3.0             # a tiny (unjudgeable) box gets a name back by place only this soon
    REACQUIRE_MAX = 0.18               # this alike to get a name back (was 0.30, then 0.25: Nour got Ali's name when Ali was not detected)...
    REACQUIRE_MARGIN = 0.10            # ...and this much more alike than every other person in view (was 0.08)
    LEARN_MAX = 0.45                   # a frame this different is not learnt (likely a mix-up)
    FACE_VOTES = 2                     # agreeing face matches before a face names someone
    FACE_WINDOW_S = 10.0               # ...within this long
    FACE_KEEP_S = 15 * 60.0            # a face-named look is remembered this long out of view
    FACE_REACQUIRE_MAX = 0.22          # stricter than a door name: no door entry backs it up
    MIN_LOOK_H = 80                    # px: a smaller (far / half-hidden) person's look is not judged

    def __init__(self):
        from identity import IdentityLedger
        self.identities: dict[str, Identity] = {}
        self.votes: dict[int, list[tuple[str, float]]] = {}
        self.ledger = IdentityLedger()          # evidence, state, confidence per track
        self.events: list = []                  # identity events of the last assign()
        # Named by face (not entered at the door): who, and when last seen -
        # so they get their name back by their look after the track was lost.
        self.face_named: dict[str, tuple[dict, float]] = {}

    def save(self, path: str) -> None:
        """Locked looks and face names to disk, so a restart does not forget who is who."""
        arrays, meta = {}, {"identities": {}, "face_named": {}}
        for label, ident in self.identities.items():
            meta["identities"][label] = ident.samples
            if ident.look.color is not None:
                arrays[f"c_{label}"] = ident.look.color
            if ident.look.deep is not None:
                arrays[f"d_{label}"] = ident.look.deep
        for label, (who, seen) in self.face_named.items():
            meta["face_named"][label] = {"who": who, "seen": seen}
        import json
        arrays["meta"] = np.frombuffer(json.dumps(meta).encode(), np.uint8)
        np.savez(path, **arrays)

    def load(self, path: str, now: float) -> int:
        """Back from disk: face names seen within FACE_KEEP_S, and their looks."""
        import json
        d = np.load(path, allow_pickle=False)
        meta = json.loads(bytes(d["meta"]).decode())
        for label, samples in meta["identities"].items():
            look = Look(d[f"c_{label}"] if f"c_{label}" in d.files else None,
                        d[f"d_{label}"] if f"d_{label}" in d.files else None)
            self.identities[label] = Identity(look, samples)
        # Face names are NOT restored: after a restart a name by look alone went to
        # the wrong person (2026-10-12, 3 people, 2 saved names). A face name comes
        # back only from the face again; the looks then keep it through crossings.
        return len(self.identities)

    def face_vote(self, track_id: int, label: str, now: float, score: Optional[float] = None):
        """The face server matched this track's face to `label`."""
        self.votes.setdefault(track_id, []).append((label, now))
        self.ledger.face_observation(track_id, label, score, now)

    def assign(self, tracks: list[Track], occupants: list[dict], door_rect, now: float,
               known: Optional[list[dict]] = None):
        inside = {o["auth_subject"]: o for o in occupants}
        # A door name whose person left the lab is dropped from its track (a
        # face name stays: the face, not the door, said who it is).
        for t in tracks:
            if t.label and t.label not in inside and t.source != "face":
                t.label = t.name = t.role = t.source = t.mismatch = None
                t.verified = False
        held = {t.label for t in tracks if t.label}
        for t in tracks:
            if t.label and t.source == "face" and t.label in self.face_named:
                self.face_named[t.label] = (self.face_named[t.label][0], now)
        for label in list(self.face_named):
            if label in inside or now - self.face_named[label][1] > self.FACE_KEEP_S:
                del self.face_named[label]     # entered at the door (named by it now), or long gone
        for label in list(self.identities):
            if label not in inside and label not in held and label not in self.face_named:
                del self.identities[label]
        self._face(tracks, inside, {k["auth_subject"]: k for k in (known or [])}, now)

        self._fix_after_crossing(tracks, inside, now)
        self._hand_back(tracks, inside, now)

        taken = {t.label for t in tracks if t.label}
        free = [o for o in occupants if o["auth_subject"] not in taken]

        # 1) New track in the door area right after an entry: that entrant.
        for t in sorted(tracks, key=lambda t: t.first_seen):
            if t.label or not free:
                continue
            if not (t.entered_at_door or at_door(t.box, door_rect)):
                continue
            first_time = not t.entered_at_door
            t.entered_at_door = True
            recent = [o for o in free if abs(t.first_seen - o["entered_at"]) <= self.ENTRY_MATCH_S]
            if first_time or recent:
                self._note("DOOR_NEW_PERSON", t.id, None, "entries waiting: "
                           + (", ".join(f"{o['auth_subject']} {t.first_seen - o['entered_at']:+.0f} s" for o in free) or "none")
                           + ("" if recent else f" - none within {self.ENTRY_MATCH_S:.0f} s, not named"))
            if recent:
                o = min(recent, key=lambda o: abs(t.first_seen - o["entered_at"]))
                self._give(t, o, how="door")
                free.remove(o)

        # 2) Someone named before, back in view: by their locked look (door
        #    names, and face names not entered yet - those stay on hold).
        #    A face name (nobody entered: no door to back it up) is given back
        #    only to a person seen big enough to judge their look, who fits it
        #    clearly better than every other unnamed person in view - else it
        #    could land on a small, half-hidden stranger.
        faced = {k: v[0] for k, v in self.face_named.items() if k not in taken}
        for label, who in faced.items():
            # Also needs at least one face match of THIS person to that label: by
            # look alone the name went to someone else after the person left
            # (2026-10-12, Hemaly's name on the person at the FANUC).
            cands = sorted((d, t.id, t) for t in tracks
                           if not t.label and not t.crowded and t.box[3] >= self.MIN_LOOK_H
                           and any(l == label for l, _ in self.votes.get(t.id, []))
                           and (d := self._distance(t, label)) is not None)
            others = [d for t in tracks if not t.label and t.box[3] < self.MIN_LOOK_H
                      and (d := self._distance(t, label)) is not None]
            if not cands or cands[0][0] > self.FACE_REACQUIRE_MAX:
                continue
            rivals = [c[0] for c in cands[1:]] + others
            if rivals and min(rivals) - cands[0][0] < self.REACQUIRE_MARGIN:
                continue
            self._give(cands[0][2], who, "face", how="look")
        # Each free door name goes to the unnamed person who looks MOST like it,
        # and only if they beat every other unnamed person in view clearly - not
        # to the first one close enough (2026-10-12: Ali's name went to Nour and
        # to another man that way). The body model must be known too (it tells
        # apart people whose colours are alike).
        for o in list(free):
            label = o["auth_subject"]
            cands = sorted((d, t.id, t) for t in tracks
                           if not t.label and not t.crowded and t.box[3] >= self.MIN_LOOK_H
                           and t.look is not None
                           # Owner's rule (2026-10-12): a lost name comes back only to a
                           # person whose OWN face matched it - never by clothes alone.
                           and any(l == label for l, _ in self.votes.get(t.id, []))
                           and (d := self._distance(t, label)) is not None)
            if not cands or cands[0][0] > self.REACQUIRE_MAX:
                continue
            rivals = [c[0] for c in cands[1:]] + [
                d for t in tracks if not t.label and t.box[3] < self.MIN_LOOK_H
                and (d := self._distance(t, label)) is not None]
            if rivals and min(rivals) - cands[0][0] < self.REACQUIRE_MARGIN:
                continue
            self._give(cands[0][2], o, how="look")
            free.remove(o)

        # 3) Elimination: one free name, one unlabelled person.
        unlabelled = [t for t in tracks if not t.label]
        if len(free) == 1 and len(unlabelled) == 1:
            self._give(unlabelled[0], free[0], how="elimination")

        self._one_name_one_person(tracks)
        self._veto(tracks)             # before learning: never learn a wrong look into a name
        self._learn(tracks)
        for t in tracks:
            t.entered = bool(t.label and t.label in inside)
        self._verify(tracks)
        self.events = self.ledger.update(tracks, now, self._distance, self._agreed)

    def _face(self, tracks: list[Track], inside: dict, known: dict, now: float):
        live = {t.id for t in tracks}
        for tid in list(self.votes):
            recent = [v for v in self.votes[tid] if now - v[1] <= self.FACE_WINDOW_S]
            if tid not in live or not recent:
                del self.votes[tid]
            else:
                self.votes[tid] = recent
        taken = {t.label for t in tracks if t.label}
        for t in tracks:
            label = self._agreed(t)
            if t.label or label is None:
                continue
            who = inside.get(label) or known.get(label)
            if who is None or label in taken:
                continue
            self._give(t, who, "face", how="face")
            taken.add(label)
            if label not in inside:
                self.face_named[label] = (who, now)

    HANDBACK_S = 20.0                  # a lost named track's name waits this long at its place

    def _hand_back(self, tracks: list[Track], inside: dict, now: float):
        """Same place, moments later: a person sitting behind monitors keeps
        dropping out of detection and comes back as a NEW track. The name of a
        track lost here goes to the one new unnamed track that appears where
        it was (any size - by place, not by look). Never when two could fit."""
        if not hasattr(self, "lost"):
            self.lost: dict[int, tuple] = {}         # track id -> (box, who, source, lost at)
            self.last_named: dict[int, tuple] = {}
        live = {t.id: t for t in tracks}
        if not hasattr(self, "lost_why"):
            self.lost_why: dict[int, str] = {}       # why the name is not handed back yet (log)
        for tid, rec in list(self.last_named.items()):
            if tid not in live:
                self.lost[tid] = (*rec, now)
                del self.last_named[tid]
                self._note("NAME_LOST", tid, rec[1]["auth_subject"],
                           f"track ended - waiting up to {self.HANDBACK_S:.0f} s to hand the name back")
        for tid in [k for k, v in self.lost.items() if now - v[3] > self.HANDBACK_S]:
            self._note("NAME_NOT_HANDED_BACK", tid, self.lost[tid][1]["auth_subject"],
                       f"{self.lost_why.pop(tid, 'no new person appeared there')} - the face must name them again")
            del self.lost[tid]
        held = {t.label for t in tracks if t.label}
        claims: dict[int, list] = {}
        for tid, (box, who, source, at) in self.lost.items():
            label = who["auth_subject"]
            if label in held or (source == "door" and label not in inside):
                continue
            cx, cy = _center(box)
            reach = 0.6 * max(box[2], box[3])
            placed = [t for t in tracks if not t.label and t.first_seen >= at - 1.0
                      and math.hypot(t.center()[0] - cx, t.center()[1] - cy) <= reach
                      and 0.5 <= (t.box[2] * t.box[3]) / max(box[2] * box[3], 1.0) <= 2.0]
            near = apart = [t for t in placed if not t.crowded]
            # Big enough to judge the look: the look must agree too (someone
            # else walking through that place is not them).
            # The look must always agree - a person sitting in the same place is
            # not them (2026-10-12 root cause #4: small / seated boxes skipped this).
            # Too small to judge (a head behind a monitor): by place only within
            # HANDBACK_SMALL_S; anything bigger needs the look too.
            near = [t for t in near if
                    (t.box[3] < self.MIN_LOOK_H and now - at <= self.HANDBACK_SMALL_S) or
                    ((d := self._distance(t, label)) is not None and d <= self.REACQUIRE_MAX)]
            # Sitting side by side touches the neighbour the whole time, so the person never
            # became "apart" and the name expired (lab 2026-10-14: Ali next to Nour). If the ONLY
            # new person at that place touches someone, the look alone (not the place) may still
            # hand it back. The neighbour is no candidate: their track is older than the loss.
            if not apart and len(placed) == 1:
                t1 = placed[0]
                if (d := self._distance(t1, label)) is not None and d <= self.REACQUIRE_MAX:
                    near = [t1]
            if len(near) == 1:
                claims.setdefault(near[0].id, []).append((tid, who, source))
            else:
                self.lost_why[tid] = ("no new person at that place" if not placed else
                                      "the new person there is still touching someone" if not apart else
                                      "the look did not match" if not near else
                                      f"{len(near)} people fit (too close to tell)")
        for t_id, cl in claims.items():
            if len(cl) != 1:
                continue                            # two lost names fit this one: nobody
            tid, who, source = cl[0]
            self._give(live[t_id], who, source, how="place")
            held.add(who["auth_subject"])
            del self.lost[tid]
        for t in tracks:
            if t.label:
                self.last_named[t.id] = (t.box, {"auth_subject": t.label, "name": t.name, "role": t.role},
                                         t.source)
            else:
                self.last_named.pop(t.id, None)

    def home_desk(self, tracks: list[Track], desks: dict, zones_px: dict, occupants: list[dict],
                  known: dict, now: float, standing_ratio: float = 2.2):
        """Owner's rule (2026-10-14): a person's own desk names them - but ONLY when the system
        already knows they are in the lab (door entry, or their face recognised), and only if
        exactly one unnamed, seated person is at that desk. desks: {"USER5": ["PC-09", "PC-10"]};
        zones_px: zone name -> (x, y, w, h) in frame pixels."""
        taken = {t.label for t in tracks if t.label}
        inside = {o["auth_subject"]: o for o in occupants}
        for label, names in desks.items():
            if label in taken:
                continue
            who = inside.get(label) or (self.face_named.get(label) or (None,))[0]
            if who is None:
                continue                                  # not known to be in the lab: no naming by desk
            rects = [zones_px[n] for n in names if n in zones_px]
            def at_desk(b, r):
                # Not mere 2D overlap: a person in FRONT overlaps a desk further back (lab 2026-10-14:
                # the man at PC-08 took Hemaly's name). The centre must be at the desk (within one
                # desk size) and the person no bigger than someone sitting at that distance.
                cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
                near = abs(cx - (r[0] + r[2] / 2)) <= r[2] and abs(cy - (r[1] + r[3] / 2)) <= 1.5 * r[3]
                return near and b[2] * b[3] <= 6 * r[2] * r[3]
            at = [t for t in tracks if not t.label and t.box[2] > 0
                  and t.box[3] / t.box[2] <= standing_ratio                      # seated
                  and any(at_desk(t.box, r) for r in rects)]
            if len(at) == 1:
                self._give(at[0], who, "door" if label in inside else "face", how="desk")
                taken.add(label)
                self._note("NAMED_BY_DESK", at[0].id, label, f"seated at {', '.join(names)}; in the lab per "
                           + ("the door" if label in inside else "the face"))

    def _note(self, kind: str, track_id, label, detail: str):
        """A decision worth reading later: printed, and kept for /identity (service drains notes)."""
        if not hasattr(self, "notes"):
            self.notes: list[dict] = []
        print(f"[identity] {kind} track {track_id} {label or ''}: {detail}")
        self.notes.append({"kind": kind, "track_id": track_id, "label": label, "detail": detail})

    def _agreed(self, t: Track) -> Optional[str]:
        """The one person FACE_VOTES recent face matches agree on, else None."""
        v = self.votes.get(t.id, [])
        return v[0][0] if len(v) >= self.FACE_VOTES and len({l for l, _ in v}) == 1 else None

    def _verify(self, tracks: list[Track]):
        """Door and face together: VERIFIED when they agree; a door name the face
        clearly contradicts is a MISMATCH (someone used another person's card)."""
        for t in tracks:
            if not t.label:
                continue
            face = self._agreed(t)
            if face == t.label or (t.source == "face" and face is None and t.verified):
                t.mismatch = None
            elif face is not None and t.source != "face":
                t.mismatch, t.verified = face, False
            t.verified = t.entered and t.mismatch is None and (face == t.label or t.source == "face" or t.verified)

    def _distance(self, t: Track, label: str) -> Optional[float]:
        ident = self.identities.get(label)
        if ident is None or ident.samples < self.LOCK_SAMPLES:
            return None
        return look_distance(t.look, ident.look)

    def _fix_after_crossing(self, tracks: list[Track], inside: dict, now: float):
        """People who touched and are now apart: give each name back to the look it belongs to."""
        group = [t for t in tracks if not t.crowded and t.separated_at > -1e9
                 and now - t.separated_at >= self.SETTLE_S]
        for t in group:
            t.separated_at = -1e9      # checked once per separation
        # Door names AND face names: a face-named person (not entered yet) must
        # keep their name through a crossing just the same.
        who = {**{k: v[0] for k, v in self.face_named.items()}, **inside}
        # The face outranks the body look: a track whose current face votes agree on its
        # name keeps it, and nobody takes a name their own face votes contradict.
        # (Lab 2026-10-14: face confirmed Nour on track 22, then the look-only re-deal moved
        # her name to the seated woman beside her - "by crossing", wrong.)
        anchored = {t.id for t in group if t.label and self._agreed(t) == t.label}
        group = [t for t in group if t.id not in anchored]
        labels = [t.label for t in group if t.label and t.label in who
                  and t.label in self.identities
                  and self.identities[t.label].samples >= self.LOCK_SAMPLES]
        if not labels or len(group) < 2 or len(group) > 6:
            return

        def cost(pairs):
            total = 0.0
            for t, label in pairs:
                said = self._agreed(t)
                if said is not None and said != label:
                    return None                  # their own face says someone else
                d = look_distance(t.look, self.identities[label].look)
                if d is None:
                    return None
                total += d
            return total

        current = cost([(t, t.label) for t in group if t.label in labels])
        if current is None:
            return
        best, best_cost = None, current - self.SWAP_MARGIN
        for chosen in itertools.permutations(group, len(labels)):
            c = cost(list(zip(chosen, labels)))
            if c is not None and c < best_cost:
                best, best_cost = chosen, c
        if best is None:
            return
        for t in group:
            if t.label in labels:
                t.label = t.name = t.role = None
        for t, label in zip(best, labels):
            self._give(t, who[label], source="door" if label in inside else "face", how="crossing")

    VETO_AT = 0.65                     # this unlike the locked look ...
    VETO_CHECKS = 12                   # ... this many checks in a row (~3 s) = not them: name dropped
    VETO_MIN_H = 160                   # px: only a clear, full-body view can veto (a seated,
                                       # half-hidden person looks different and keeps the name)

    def _one_name_one_person(self, tracks: list[Track]):
        """A name is on ONE person: when two boxes carry it, the one that looks
        most like the locked look keeps it (the older box when the looks cannot
        tell), the others become Unknown."""
        by: dict[str, list[Track]] = {}
        for t in tracks:
            if t.label:
                by.setdefault(t.label, []).append(t)
        for label, ts in by.items():
            if len(ts) < 2:
                continue
            def rank(t):
                d = self._distance(t, label)
                return (d if d is not None else 9.0, t.first_seen)
            keep = min(ts, key=rank)
            for t in ts:
                if t is not keep:
                    print(f"[identity] {t.name} was on two people - kept on track {keep.id}, "
                          f"track {t.id} is Unknown")
                    t.label = t.name = t.role = None

    def _veto(self, tracks: list[Track]):
        """A wrong name is worse than none: a clear, alone view that does not
        look like the person the name is locked to drops the name (Unknown)."""
        if not hasattr(self, "_unlike"):
            self._unlike: dict[int, int] = {}
        for t in tracks:
            if not t.label or t.crowded or t.look is None or t.box[3] < self.VETO_MIN_H:
                continue
            d = self._distance(t, t.label)
            if d is None or d <= self.VETO_AT:
                self._unlike.pop(t.id, None)
                continue
            n = self._unlike.get(t.id, 0) + 1
            self._unlike[t.id] = n
            if n >= self.VETO_CHECKS:
                print(f"[identity] track {t.id}: does not look like {t.name} any more "
                      f"(distance {d:.2f}) - name dropped")
                t.label = t.name = t.role = None
                self._unlike.pop(t.id, None)

    def _learn(self, tracks: list[Track]):
        for t in tracks:
            if not t.label or t.crowded or t.look is None or t.box[3] < self.MIN_LOOK_H:
                continue                   # a tiny / half-hidden view would blur the locked look
            # Clearly alone (2026-10-12 root cause #7): nobody within a body width,
            # and not touching anyone in the last second.
            if t.last_seen - getattr(t, "crowded_at", -1e9) < 1.0 or any(
                    o is not t and abs(o.center()[0] - t.center()[0]) < 1.5 * max(o.box[2], t.box[2])
                    and abs(o.center()[1] - t.center()[1]) < max(o.box[3], t.box[3]) for o in tracks):
                continue
            ident = self.identities.get(t.label)
            if ident is None:
                self.identities[t.label] = Identity(t.look)
                continue
            d = look_distance(t.look, ident.look)
            if d is not None and d > self.LEARN_MAX and ident.samples >= self.LOCK_SAMPLES:
                continue               # not like them at all: a mix-up, do not learn it
            ident.look = blend(ident.look, t.look, max(0.1, 1.0 / (ident.samples + 1)))
            ident.samples += 1

    @staticmethod
    def _give(t: Track, o: dict, source: str = "door", how: Optional[str] = None):
        t.label, t.name, t.role = o["auth_subject"], o.get("name") or o["auth_subject"], o.get("role")
        t.source = source
        t.named_by = how or source
        t.verified, t.mismatch = False, None


# ------------------------------------------------------------------ zones ---
@dataclass
class ZoneState:
    id: int
    name: str
    status: str = "LEARNING"           # LEARNING / OK / IN_USE / CHANGED / MOTION
    score: float = 0.0                 # 0 = as normal, 1 = completely different
    since: float = field(default_factory=time.time)
    reported: bool = False
    new_pose: bool = False             # a robot stopped in a new pose (logged, not an alert)
    home: str = "NOT_SET"              # robots: AT_HOME / AWAY / NOT_SET / RESAVE (box moved since)
    home_score: float = 0.0            # 0 = exactly the HOME look, 1 = completely different


class ZoneWatcher:
    """
    One box per fixed item (PC, robot...). The first clear view (nobody in
    the box) becomes its reference. Then, while nobody is in the box:

      CHANGED  the box no longer looks like the reference for HOLD_S
               (moved, removed, covered) - normalised correlation, so a light
               switched on or off does not count;
      MOTION   part of the box changes frame to frame (something moving there
               with no person detected, e.g. a robot running): shown after two
               moving frames, kept until the box has been still MOTION_LINGER_S
               - an arm that pauses between moves stays "moving".

    A robot (a box with alert_on_motion off - it runs programs on its own) that
    stops in a new pose is not "changed": once still for SETTLE_S the new pose
    becomes its normal look. A PC that looks different stays CHANGED.

    A person overlapping the box makes it IN_USE and pauses the comparison.
    """
    CHANGE_AT = 0.45
    MOTION_AT = 12.0                   # mean abs pixel change (0-255) between frames, or
    PIXEL_AT = 25                      # a pixel changing by this much ...
    MOVING_SHARE = 0.03                # ... in this share of the box (an arm in a big box)
    HOLD_S = 3.0
    MOTION_LINGER_S = 4.0
    SETTLE_S = 5.0
    POSE_AT = 0.15                     # a robot this different from its last pose moved (logged)

    HOME_AT = 0.15                     # closer than this to the HOME look = at HOME (VERIFY)
    MOTION_GAP_S = 0.4                 # frame-to-frame motion is measured over this gap
    MIN_MOVING_PX = 40                 # tiny boxes: at least this many changed pixels (compression noise)
    GLOBAL_SHARE = 0.4                 # this share of the empty boxes "moving" at once = the whole
                                       # picture changed (light, compression), not an item
    PC_RUN = 3                         # PCs: moving checks in a row before MOTION (screens flicker)
    IN_USE_AFTER_S = 5.0               # a person must stay at a box this long to be USING it
                                       # (walking past in front of it is not use)
    NEAR_MARGIN = 0.3                  # a person this close (share of their size) hides / shakes the box
    NEAR_GRACE_S = 1.5                 # ... and for this long after they left (the detector lags)
    ROBOT_WORK_AREA = 1.0              # robots: a person within the box grown by this (each side, share
                                       # of the box) is working at the robot - the arm box sits high, people below
    ROBOT_RUN = 2                      # robots: faster

    def __init__(self):
        # HOME looks of robot boxes (saved by staff with the robot at HOME):
        # zone id -> (patch, rect it was taken in). Kept across restarts.
        self.home: dict[int, tuple[np.ndarray, tuple]] = {}
        self.refs: dict[int, np.ndarray] = {}
        self.prev: dict[int, np.ndarray] = {}
        self._prev_at: dict[int, float] = {}
        self._occupied_since: dict[int, float] = {}
        self._near_at: dict[int, float] = {}
        self.states: dict[int, ZoneState] = {}
        self._pending: dict[int, tuple[str, float]] = {}
        self._moving: dict[int, tuple[int, float]] = {}    # consecutive moving frames, last moving time

    def reset(self, zone_id: Optional[int] = None):
        for d in (self.refs, self.prev, self._prev_at, self.states, self._pending, self._moving,
                  self._occupied_since, self._near_at):
            if zone_id is None:
                d.clear()
            else:
                d.pop(zone_id, None)

    @staticmethod
    def _patch(gray, rect):
        h, w = gray.shape[:2]
        x, y = int(rect[0] * w), int(rect[1] * h)
        x2, y2 = int((rect[0] + rect[2]) * w), int((rect[1] + rect[3]) * h)
        if x2 - x < 8 or y2 - y < 8:
            return None
        return cv2.GaussianBlur(gray[y:y2, x:x2], (5, 5), 0)

    @staticmethod
    def _difference(a, b) -> float:
        a, b = a.astype(np.float32), b.astype(np.float32)
        a, b = a - a.mean(), b - b.mean()
        den = float(np.sqrt((a * a).sum() * (b * b).sum()))
        if den < 1e-3:                 # flat patch (e.g. lights off): compare brightness
            return min(1.0, abs(float(a.mean() - b.mean())) / 64)
        return float(np.clip(1 - (a * b).sum() / den, 0, 1))

    @classmethod
    def _near(cls, rect, person_rects_norm) -> bool:
        m = cls.NEAR_MARGIN
        return any(iou(rect, (p[0] - m * p[2], p[1] - m * p[3], p[2] * (1 + 2 * m), p[3] * (1 + 2 * m))) > 0
                   for p in person_rects_norm)

    def _moving_now(self, zones, gray, person_rects_norm) -> dict:
        """Which empty boxes see motion in this check (before the whole-picture test)."""
        out = {}
        for z in zones:
            zid, rect = z["id"], (z["x"], z["y"], z["w"], z["h"])
            patch = self._patch(gray, rect)
            prev = self.prev.get(zid)
            if patch is None or prev is None or prev.shape != patch.shape:
                continue
            if self._near(rect, person_rects_norm):
                continue                       # a person at / passing the box: not the item moving
            # Brightness evened out first: a light switched on/off is not movement.
            gain = float(patch.mean()) / max(float(prev.mean()), 1.0)
            d = np.abs(prev.astype(np.float32) * gain - patch.astype(np.float32))
            big = d > self.PIXEL_AT
            out[zid] = bool((float(d.mean()) > self.MOTION_AT or float(big.mean()) >= self.MOVING_SHARE)
                            and int(big.sum()) >= self.MIN_MOVING_PX)
        return out

    STANDING_RATIO = 2.2               # person box height / width above this = standing (lab 2026-10-14:
                                       # seated 1.7-1.8, standing 2.4-2.9) - PCs only; VERIFY on more people

    def _standing(self, p: tuple, fw: int, fh: int) -> bool:
        """p = (x, y, w, h) normalised; ratio measured in pixels."""
        return p[2] > 0 and (p[3] * fh) / (p[2] * fw) > self.STANDING_RATIO

    def update(self, zones: list[dict], gray: np.ndarray, person_rects_norm: list[tuple],
               now: float) -> list[ZoneState]:
        """zones: [{"id", "name", "x", "y", "w", "h"}] normalised 0-1."""
        out = []
        moving_now = self._moving_now(zones, gray, person_rects_norm)
        # Many empty boxes moving at the same instant = the whole picture changed.
        whole_picture = len(moving_now) >= 3 and \
            sum(moving_now.values()) >= max(3, self.GLOBAL_SHARE * len(moving_now))
        for z in zones:
            zid, rect = z["id"], (z["x"], z["y"], z["w"], z["h"])
            st = self.states.setdefault(zid, ZoneState(zid, z["name"]))
            st.name = z["name"]
            patch = self._patch(gray, rect)
            if patch is None:
                continue
            if z.get("alert_on_motion", True) is False:
                st.home, st.home_score = self.home_state(z, patch)
            if z.get("alert_on_motion", True) is False:   # a robot: its working area around it
                g = self.ROBOT_WORK_AREA
                area = (rect[0] - g * rect[2], rect[1] - g * rect[3], rect[2] * (1 + 2 * g), rect[3] * (1 + 2 * g))
                occupied = any(iou(area, p) > 0.02 for p in person_rects_norm)
            else:
                # A PC is used by someone SITTING at it. Standing in front of it (talking,
                # passing, waiting) overlaps the box in the picture too, but is not use
                # (2026-10-14 lab: a man standing at PC-11 made it "in use").
                fh, fw = gray.shape[:2]
                occupied = any(iou(rect, p) > 0.02 and not self._standing(p, fw, fh) for p in person_rects_norm)
            # Motion compares with the picture from MOTION_GAP_S ago (the thresholds
            # were set for that gap), however often update() is called.
            prev = self.prev.get(zid)
            if prev is None or now - self._prev_at.get(zid, -1e9) >= self.MOTION_GAP_S:
                self.prev[zid], self._prev_at[zid] = patch, now
            # In use = a person STAYS at the box (sitting at the PC, working at
            # the robot); someone walking past only pauses the checks.
            if occupied:
                self._occupied_since.setdefault(zid, now)
            else:
                self._occupied_since.pop(zid, None)
            near = self._near(rect, person_rects_norm)
            if near:
                self._near_at[zid] = now
            if occupied and now - self._occupied_since[zid] >= self.IN_USE_AFTER_S:
                self._set(st, "IN_USE", now)
                self._pending.pop(zid, None)
                out.append(st)
                continue
            if near or now - self._near_at.get(zid, -1e9) < self.NEAR_GRACE_S:
                # Passing by: no motion / change judged; a box already IN_USE stays so
                # until the person has really gone, anything else shows OK.
                if st.status not in ("IN_USE", "OK"):
                    self._set(st, "OK", now)
                self._pending.pop(zid, None)
                self._moving[zid] = (0, self._moving.get(zid, (0, -1e9))[1])
                out.append(st)
                continue
            ref = self.refs.get(zid)
            if ref is None or ref.shape != patch.shape:
                self.refs[zid] = patch     # first clear view = how it normally looks
                self._set(st, "OK", now)
                out.append(st)
                continue
            st.score = round(self._difference(ref, patch), 3)
            moving = moving_now.get(zid, False) and not whole_picture
            run, last = self._moving.get(zid, (0, -1e9))
            run, last = (run + 1, now) if moving else (0, last)
            self._moving[zid] = (run, last)
            need = self.ROBOT_RUN if z.get("alert_on_motion", True) is False else self.PC_RUN
            if run >= need or (st.status == "MOTION" and now - last < self.MOTION_LINGER_S):
                self._pending.pop(zid, None)
                self._set(st, "MOTION", now)
                out.append(st)
                continue
            if moving:                         # a single moving frame: wait for the next one
                out.append(st)
                continue
            if z.get("alert_on_motion", True) is False and st.score > self.POSE_AT \
                    and now - last >= self.SETTLE_S:
                self.refs[zid] = patch         # a robot parked in a new pose: that is normal now
                st.score = 0.0
                st.new_pose = True
            want = "CHANGED" if st.score > self.CHANGE_AT else "OK"
            if want == "OK":
                self._pending.pop(zid, None)
                self._set(st, "OK", now)
            else:
                first = self._pending.setdefault(zid, (want, now))
                if first[0] != want:
                    self._pending[zid] = (want, now)
                elif now - first[1] >= self.HOLD_S:
                    self._set(st, want, now)
            out.append(st)
        return out

    def save_home(self, zones: list[dict], gray: np.ndarray) -> list[str]:
        """The robot boxes' look NOW becomes their HOME look (robots at HOME)."""
        saved = []
        for z in zones:
            if z.get("alert_on_motion", True) is not False:
                continue                       # PCs have no HOME
            rect = (z["x"], z["y"], z["w"], z["h"])
            patch = self._patch(gray, rect)
            if patch is not None:
                self.home[z["id"]] = (patch, tuple(round(v, 4) for v in rect))
                saved.append(z["name"])
        return saved

    def home_state(self, z: dict, patch) -> tuple[str, float]:
        got = self.home.get(z["id"])
        if got is None:
            return "NOT_SET", 0.0
        ref, rect = got
        now_rect = tuple(round(v, 4) for v in (z["x"], z["y"], z["w"], z["h"]))
        if now_rect != rect or patch is None or ref.shape != patch.shape:
            return "RESAVE", 0.0               # the box moved or was redrawn: HOME must be saved again
        score = round(self._difference(ref, patch), 3)
        return ("AT_HOME" if score <= self.HOME_AT else "AWAY"), score

    def accept(self, zone_id: int):
        """Staff confirm the new look is fine (e.g. a PC deliberately moved)."""
        if zone_id in self.prev:
            self.refs[zone_id] = self.prev[zone_id]
        st = self.states.get(zone_id)
        if st:
            self._set(st, "OK", time.time())

    @staticmethod
    def _set(st: ZoneState, status: str, now: float):
        if st.status != status:
            st.status, st.since, st.reported = status, now, False


def head_crop(frame: np.ndarray, box) -> Optional[np.ndarray]:
    """The head and shoulders of a person box, for face identification
    (YuNet then finds the face inside it). Small crops are enlarged."""
    H, W = frame.shape[:2]
    x, y, w, h = box
    x0, x1 = int(max(0, x - 0.1 * w)), int(min(W, x + 1.1 * w))
    y0, y1 = int(max(0, y - 0.05 * h)), int(min(H, y + 0.5 * h))
    if x1 - x0 < 24 or y1 - y0 < 24:
        return None
    crop = frame[y0:y1, x0:x1]
    if crop.shape[1] < 240:
        f = 240 / crop.shape[1]
        crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    return crop


# --------------------------------------------------------------- drawing ---
COLORS = {"ADMIN": (246, 92, 139), "LAB_STAFF": (250, 165, 96), "STUDENT": (129, 199, 52),
          None: (36, 191, 251)}                          # BGR: violet / blue / green / amber
ROLE_NAMES = {"ADMIN": "Admin", "LAB_STAFF": "Staff", "STUDENT": "Student"}
ON_HOLD = (0, 140, 255)                                  # BGR orange: named by face, not entered yet
MISMATCH = (60, 60, 240)                                 # BGR red: the face contradicts the door's name
ZONE_COLORS = {"OK": (160, 160, 160), "IN_USE": (250, 165, 96), "CHANGED": (60, 60, 240),
               "MOTION": (0, 165, 255), "LEARNING": (160, 160, 160)}
ZONE_WORDS = {"MOTION": "moving", "IN_USE": "in use"}


def red_share(frame: np.ndarray, rect_norm) -> Optional[float]:
    """Share of strongly red pixels in a box (0-1): the lab's red door leaf is
    seen only while the door is open."""
    h, w = frame.shape[:2]
    x0, y0 = int(rect_norm[0] * w), int(rect_norm[1] * h)
    x1, y1 = int((rect_norm[0] + rect_norm[2]) * w), int((rect_norm[1] + rect_norm[3]) * h)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    red = ((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 110) & (hsv[..., 2] > 60)
    return float(red.mean())


class DoorWatcher:
    """Open / closed from the red door leaf in the door box. The share of red
    when open is learnt (the reddest clear look); open above 60 % of it,
    closed below 25 % of it - in between keeps the last state (no flicker).
    A person in the doorway hides the red: that never counts as closed."""
    MIN_OPEN = 0.15                    # less red than this is never taken as "open"

    def __init__(self):
        self.open_share: Optional[float] = None
        self.is_open: Optional[bool] = None

    def update(self, share: Optional[float], occupied: bool = False) -> Optional[bool]:
        if share is None:
            return self.is_open
        if share >= self.MIN_OPEN and not occupied:
            self.open_share = max(self.open_share or 0.0, share)
        full = self.open_share
        if full is None:                               # never seen open yet
            if share < 0.05 and not occupied:
                self.is_open = False
            return self.is_open
        if share >= 0.6 * full:
            self.is_open = True
        elif share <= 0.25 * full and not occupied:
            self.is_open = False
        return self.is_open


def draw(frame, tracks: list[Track], zones: list[dict], states: dict, door_rect_norm=None,
         door_open: Optional[bool] = None):
    h, w = frame.shape[:2]
    for z in zones:
        st = states.get(z["id"])
        status = st.status if st else "LEARNING"
        c = ZONE_COLORS.get(status, (160, 160, 160))
        x, y = int(z["x"] * w), int(z["y"] * h)
        cv2.rectangle(frame, (x, y), (int((z["x"] + z["w"]) * w), int((z["y"] + z["h"]) * h)), c, 2)
        # Box labels sit at the bottom so they never hide a person's name tag.
        word = ZONE_WORDS.get(status, status.lower())
        if st is not None and st.home in ("AT_HOME", "AWAY") and status in ("OK", "MOTION"):
            word += " - home" if st.home == "AT_HOME" else " - away from home"
        _tag(frame, f'{z["name"]} {word}', x,
             int((z["y"] + z["h"]) * h) + 18, c)
    if door_rect_norm:
        x, y = int(door_rect_norm[0] * w), int(door_rect_norm[1] * h)
        cv2.rectangle(frame, (x, y), (int((door_rect_norm[0] + door_rect_norm[2]) * w),
                                      int((door_rect_norm[1] + door_rect_norm[3]) * h)), (200, 200, 200), 1)
        word = {True: "door OPEN", False: "door closed"}.get(door_open, "door")
        _tag(frame, word, x, y, (0, 165, 255) if door_open else (200, 200, 200))
    # Name tags never cover each other: people sitting side by side had the neighbour's
    # "Unknown" drawn over a name (lab 2026-10-14). Named people are drawn last (on top) and
    # each tag moves up (or below the box) until it is clear of the tags already placed.
    placed: list[tuple] = []
    for t in sorted(tracks, key=lambda t: bool(t.label)):
        c = MISMATCH if t.mismatch else ON_HOLD if t.label and not t.entered \
            else COLORS.get(t.role if t.label else None, COLORS[None])
        x, y, bw, bh = (int(v) for v in t.box)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), c, 2)
        if t.label:
            role = ROLE_NAMES.get(t.role, "")
            label = f"{t.name or t.label}{f' ({role})' if role else ''} {t.label}"
            if t.mismatch:
                label += f" - face says {t.mismatch}"
            elif not t.entered:
                label += " - not entered"
            elif t.verified:
                label += " - verified"
            # How sure (identity.py): shown, never hidden for a cleaner picture.
            st = t.identity_state
            if st == "IDENTITY_CONFLICT":
                label += " - IDENTITY CONFLICT"
            elif st == "IDENTITY_UNCERTAIN":
                label += f" ? {t.identity_confidence:.0%}"
            elif t.identity_confidence:
                label += f" {t.identity_confidence:.0%}"
        else:
            label = "Unknown"
        _tag_clear(frame, label, x, y, y + bh, MISMATCH if t.identity_state == "IDENTITY_CONFLICT" else c, placed)
    return frame


def _tag_clear(frame, text, x, y_top, y_bottom, color, placed: list) -> tuple:
    """A person's tag above the box, kept inside the picture and off the tags in `placed`."""
    h, w = frame.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    rw, rh = tw + 8, th + 6
    x = max(0, min(x, w - rw))                                     # long names stay in the picture
    hit = lambda y0: any(x < px + pw and px < x + rw and y0 - rh < py and py - ph < y0 for px, py, pw, ph in placed)
    y0 = max(rh, y_top)
    while hit(y0) and y0 - rh > 0:                                 # move up over the tags below
        y0 -= rh + 2
    if hit(y0) or y0 - rh < 0:                                     # no room above: under the box
        y0 = min(h, y_bottom + rh)
        while hit(y0) and y0 < h:
            y0 += rh + 2
    _tag(frame, text, x, y0, color)
    placed.append((x, y0, rw, rh))
    return x, y0


def _tag(frame, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y0 = max(th + 6, y)
    cv2.rectangle(frame, (x, y0 - th - 6), (x + tw + 8, y0), color, -1)
    cv2.putText(frame, text, (x + 4, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
