"""
Keep the boxes on their items when the camera's view moves (the MC210 pans
and tilts; it can be bumped or turned in its app).

When the boxes are drawn / changed, the current view is kept as the
REFERENCE (people masked out - only the room counts). Every check, the
current view is matched against it on fixed features of the room (door,
cabinets, wall corners) with ORB + RANSAC:

    * the view did not move                 -> nothing to do
    * it moved and the match is confident   -> every box is mapped to its new
                                               place (names kept); after the
                                               portal saves them this view is
                                               the new reference
    * it moved and the match is NOT confident -> say so, change nothing
                                               (a different corner / a big
                                               turn: the boxes are redrawn)

It never guesses: an unconfident match leaves every box as it was.
Pure logic (numpy + OpenCV), tested in test_realign.py.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

WORK_WIDTH = 640              # matching runs on this width (enough detail, fast)
MIN_INLIERS = 40              # fewer fixed points agreeing = not confident
MIN_INLIER_RATIO = 0.30
MOVED_FRACTION = 0.015        # median shift above 1.5 % of the width = the view moved
MAX_SCALE_CHANGE = 0.35       # a box growing/shrinking more than this = not a pan/tilt


@dataclass
class Reference:
    gray: np.ndarray                      # WORK_WIDTH-wide grayscale
    keypoints: list
    descriptors: Optional[np.ndarray]
    size: tuple[int, int]                 # (w, h) of the frame it came from
    zones_key: str                        # which boxes it belongs to


@dataclass
class Match:
    moved: bool
    confident: bool
    inliers: int
    ratio: float
    shift_fraction: float                 # median movement / frame width
    homography: Optional[np.ndarray]      # maps reference (normalised 0-1) -> current (0-1)

    def summary(self) -> str:
        return (f"{'moved' if self.moved else 'still'}, {'confident' if self.confident else 'NOT confident'}: "
                f"{self.inliers} matching points ({self.ratio:.0%}), shift {self.shift_fraction:.1%} of the width")


_orb = cv2.ORB_create(nfeatures=2500)


# 2026-11-12 (Gemini CAL-2): a lit monitor or a moving robot changes its pixels all the time; ORB points there do not
# belong to the room and weaken the match. PC boxes: the inner part (screen) is masked, the bezel / desk edge kept as
# fixed anchors; robot boxes (alert_on_motion False): masked whole.
PC_SCREEN_INSET = 0.15                 # mask the inner 70 % of a PC box


def dynamic_regions(zones: list[dict]) -> list[tuple]:
    """(x, y, w, h, inset) as fractions of the picture: the parts of the mapped boxes that keep changing."""
    out = []
    for z in zones or []:
        if z.get("alert_on_motion", True) is False:
            out.append((z["x"], z["y"], z["w"], z["h"], 0.0))
        elif str(z.get("name", "")).upper().startswith("PC"):
            out.append((z["x"], z["y"], z["w"], z["h"], PC_SCREEN_INSET))
    return out


def _prepare(frame: np.ndarray, people: list[tuple], dynamic: Optional[list] = None) -> tuple[np.ndarray, np.ndarray, float]:
    h, w = frame.shape[:2]
    s = WORK_WIDTH / w
    gray = cv2.cvtColor(cv2.resize(frame, (WORK_WIDTH, int(round(h * s)))), cv2.COLOR_BGR2GRAY)
    mask = np.full(gray.shape, 255, np.uint8)
    for (x, y, bw, bh) in people:         # people move: never part of the room
        x0, y0 = max(0, int((x - 0.1 * bw) * s)), max(0, int((y - 0.05 * bh) * s))
        mask[y0:int((y + 1.05 * bh) * s), x0:int((x + 1.1 * bw) * s)] = 0
    gh, gw = gray.shape
    for (x, y, bw, bh, inset) in dynamic or []:
        x0, y0 = int((x + inset * bw) * gw), int((y + inset * bh) * gh)
        x1, y1 = int((x + (1 - inset) * bw) * gw), int((y + (1 - inset) * bh) * gh)
        mask[max(0, y0):max(0, min(gh, y1)), max(0, x0):max(0, min(gw, x1))] = 0
    return gray, mask, s


def make_reference(frame: np.ndarray, people: list[tuple], zones_key: str, dynamic: Optional[list] = None) -> Reference:
    gray, mask, _ = _prepare(frame, people, dynamic)
    kp, des = _orb.detectAndCompute(gray, mask)
    return Reference(gray, kp, des, (frame.shape[1], frame.shape[0]), zones_key)


def compare(ref: Reference, frame: np.ndarray, people: list[tuple], dynamic: Optional[list] = None) -> Match:
    gray, mask, _ = _prepare(frame, people, dynamic)
    kp, des = _orb.detectAndCompute(gray, mask)
    none = Match(False, False, 0, 0.0, 0.0, None)
    if ref.descriptors is None or des is None or len(kp) < 8 or len(ref.keypoints) < 8:
        return none
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(ref.descriptors, des, k=2)
    good = [m for m, *rest in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * rest[0].distance]
    if len(good) < 8:
        return none
    src = np.float32([ref.keypoints[m.queryIdx].pt for m in good])
    dst = np.float32([kp[m.trainIdx].pt for m in good])
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None:
        return none
    inl = inl.ravel().astype(bool)
    n = int(inl.sum())
    ratio = n / len(good)
    shift = float(np.median(np.linalg.norm(dst[inl] - src[inl], axis=1))) / gray.shape[1] if n else 0.0
    rh, rw = ref.gray.shape
    ch, cw = gray.shape
    # Homography in normalised coordinates (0-1), independent of picture size.
    A = np.array([[rw, 0, 0], [0, rh, 0], [0, 0, 1]], np.float64)
    B = np.array([[1 / cw, 0, 0], [0, 1 / ch, 0], [0, 0, 1]], np.float64)
    Hn = B @ H @ A
    confident = n >= MIN_INLIERS and ratio >= MIN_INLIER_RATIO
    return Match(shift >= MOVED_FRACTION, confident, n, ratio, shift, Hn)


def move_box(Hn: np.ndarray, box: dict) -> Optional[dict]:
    """A box (x, y, w, h as fractions) where it lands in the new view;
    None if it left the picture or was distorted (not a plain pan/tilt)."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    pts = np.float32([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]).reshape(-1, 1, 2)
    q = cv2.perspectiveTransform(pts, Hn).reshape(-1, 2)
    x0, y0 = q.min(0)
    x1, y1 = q.max(0)
    nw, nh = x1 - x0, y1 - y0
    if nw <= 0 or nh <= 0:
        return None
    if abs(nw / w - 1) > MAX_SCALE_CHANGE or abs(nh / h - 1) > MAX_SCALE_CHANGE:
        return None
    cx0, cy0, cx1, cy1 = max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)
    if (cx1 - cx0) * (cy1 - cy0) < 0.5 * nw * nh:          # mostly outside the picture now
        return None
    return {"x": round(float(cx0), 4), "y": round(float(cy0), 4),
            "w": round(float(cx1 - cx0), 4), "h": round(float(cy1 - cy0), 4)}


def zones_key(zones: list[dict], door: Optional[dict]) -> str:
    """Changes whenever a box is added, removed or redrawn."""
    allz = list(zones) + ([door] if door else [])
    return "|".join(f"{z['id']}:{z.get('ref_version', 0)}:{z['x']:.4f},{z['y']:.4f},{z['w']:.4f},{z['h']:.4f}"
                    for z in sorted(allz, key=lambda z: z["id"]))


# --------------------------------------------------------------- anchor ---
# The view and the boxes as STAFF last drew them. Every re-alignment maps
# from this anchor straight to the current view, so small errors can never
# pile up from one automatic re-alignment to the next.
APPLY_MIN_INLIERS = 80         # stricter than "confident" before boxes are moved
APPLY_MIN_RATIO = 0.40
SETTLED = 0.01                 # two looks must agree on every box corner within 1 % of the picture


def boxes_of(zones: list[dict], door: Optional[dict]) -> dict[int, tuple]:
    return {z["id"]: (z["x"], z["y"], z["w"], z["h"]) for z in list(zones) + ([door] if door else [])}


def same_boxes(a: dict, b: dict, tol: float = 2e-3) -> bool:
    return a.keys() == b.keys() and all(max(abs(p - q) for p, q in zip(a[k], b[k])) <= tol for k in a)


def predict(Hn: np.ndarray, anchor_boxes: dict) -> tuple[dict, list]:
    """Where each anchor box lands in the current view; ids that left the picture."""
    moved, lost = {}, []
    for k, (x, y, w, h) in anchor_boxes.items():
        nb = move_box(Hn, {"x": x, "y": y, "w": w, "h": h})
        if nb is None:
            lost.append(k)
        else:
            moved[k] = (nb["x"], nb["y"], nb["w"], nb["h"])
    return moved, lost


def max_corner_gap(a: dict, b: dict) -> float:
    gaps = [max(abs(a[k][0] - b[k][0]), abs(a[k][1] - b[k][1]),
                abs(a[k][0] + a[k][2] - b[k][0] - b[k][2]), abs(a[k][1] + a[k][3] - b[k][1] - b[k][3]))
            for k in a if k in b]
    return max(gaps) if gaps else 0.0


def move_seats(Hn: Optional[np.ndarray], seats: dict) -> dict:
    """Seat boxes (PC name -> [x, y, w, h], recorded in the anchor's view) where they land in the current view
    (Gemini CAL-1). Always from the recorded seats, never from moved ones: no drift. A seat that would leave the
    picture keeps its recorded place."""
    if Hn is None:
        return seats
    out = {}
    for name, b in seats.items():
        nb = move_box(Hn, {"x": b[0], "y": b[1], "w": b[2], "h": b[3]})
        out[name] = [nb["x"], nb["y"], nb["w"], nb["h"]] if nb else list(b)
    return out


def save_anchor(path: str, ref: Reference, anchor_boxes: dict, applied: dict, Hn: Optional[np.ndarray] = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, gray=ref.gray, size=np.array(ref.size),
                        meta=np.array(json.dumps({"anchor": {str(k): v for k, v in anchor_boxes.items()},
                                                  "applied": {str(k): v for k, v in applied.items()},
                                                  "H": None if Hn is None else np.asarray(Hn).tolist()})))


def load_anchor_H(path: str) -> Optional[np.ndarray]:
    """The anchor -> current-view transform last accepted (None: boxes are where staff drew them)."""
    try:
        h = json.loads(str(np.load(path, allow_pickle=False)["meta"])).get("H")
        return None if h is None else np.asarray(h, np.float64)
    except (OSError, KeyError, ValueError):
        return None


def load_anchor(path: str) -> Optional[tuple[Reference, dict, dict]]:
    try:
        d = np.load(path, allow_pickle=False)
        gray = d["gray"]
        kp, des = _orb.detectAndCompute(gray, None)
        meta = json.loads(str(d["meta"]))
        conv = lambda m: {int(k): tuple(v) for k, v in m.items()}
        return Reference(gray, kp, des, tuple(int(v) for v in d["size"]), ""), conv(meta["anchor"]), conv(meta["applied"])
    except (OSError, KeyError, ValueError):
        return None
