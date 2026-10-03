"""
Security camera vision: detection, tracking, name labels, equipment zones.

Pure functions and small classes with no network or camera access, so each
piece can be tested on its own (test_vision.py). security_vision.py wires
them to the camera, the portal and the HTTP endpoints.

    Detector      YOLOX-S (OpenCV model zoo, ONNX) on the CPU through cv2.dnn
    Tracker       keeps an id on each person from frame to frame (IoU match)
    Labeler       puts a name on a track only when the door data makes it
                  certain; otherwise the track stays "Unknown"
    ZoneWatcher   compares each equipment box with how it normally looks
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# COCO class ids the security view cares about (the model knows 80).
PERSON = 0
SHOWN = {0: "person", 62: "monitor", 63: "laptop", 66: "keyboard", 64: "mouse"}


# --------------------------------------------------------------- detector ---
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

    def center(self):
        return (self.box[0] + self.box[2] / 2, self.box[1] + self.box[3] / 2)


class Tracker:
    """Greedy IoU matching. A track survives short misses (MAX_MISS_S)."""
    MAX_MISS_S = 2.0
    MIN_IOU = 0.25
    CONFIRM_HITS = 3                   # seen in this many frames before it counts

    def __init__(self):
        self.tracks: list[Track] = []
        self._next = 1

    def update(self, boxes: list[tuple], now: float) -> list[Track]:
        pairs = sorted(((iou(t.box, b), ti, bi) for ti, t in enumerate(self.tracks)
                        for bi, b in enumerate(boxes)), reverse=True)
        used_t, used_b = set(), set()
        for score, ti, bi in pairs:
            if score < self.MIN_IOU or ti in used_t or bi in used_b:
                continue
            t = self.tracks[ti]
            t.box, t.last_seen, t.hits = boxes[bi], now, t.hits + 1
            used_t.add(ti)
            used_b.add(bi)
        for bi, b in enumerate(boxes):
            if bi not in used_b:
                self.tracks.append(Track(self._next, b, now, now))
                self._next += 1
        self.tracks = [t for t in self.tracks if now - t.last_seen <= self.MAX_MISS_S]
        return self.confirmed(now)

    def confirmed(self, now: float) -> list[Track]:
        return [t for t in self.tracks if t.hits >= self.CONFIRM_HITS and now - t.last_seen < 0.6]


# ---------------------------------------------------------------- labeler ---
def in_rect(pt, rect) -> bool:
    return rect is not None and rect[0] <= pt[0] <= rect[0] + rect[2] and rect[1] <= pt[1] <= rect[1] + rect[3]


class Labeler:
    """
    Names come from the door, never from guessing:

      * a person who appears in the DOOR AREA soon after a door grant gets
        the name of that entry;
      * when exactly one name inside is still unassigned and exactly one
        visible person is unlabelled, that person must be them;
      * everyone else stays "Unknown" - a wrong name is worse than none.

    occupants: [{"auth_subject", "name", "role", "entered_at" (epoch s)}]
    door_rect: the door area in frame pixels (x, y, w, h) or None.
    """
    ENTRY_MATCH_S = 25.0

    def assign(self, tracks: list[Track], occupants: list[dict], door_rect, now: float):
        inside = {o["auth_subject"]: o for o in occupants}
        # A name whose person left the lab is dropped from its track.
        for t in tracks:
            if t.label and t.label not in inside:
                t.label = t.name = t.role = None
        taken = {t.label for t in tracks if t.label}
        free = [o for o in occupants if o["auth_subject"] not in taken]

        # 1) New track in the door area right after an entry: that entrant.
        for t in sorted(tracks, key=lambda t: t.first_seen):
            if t.label or not free:
                continue
            if not (t.entered_at_door or in_rect(t.center(), door_rect)):
                continue
            t.entered_at_door = True
            recent = [o for o in free if abs(t.first_seen - o["entered_at"]) <= self.ENTRY_MATCH_S]
            if recent:
                o = min(recent, key=lambda o: abs(t.first_seen - o["entered_at"]))
                self._give(t, o)
                free.remove(o)

        # 2) Elimination: one free name, one unlabelled person.
        unlabelled = [t for t in tracks if not t.label]
        if len(free) == 1 and len(unlabelled) == 1:
            self._give(unlabelled[0], free[0])

    @staticmethod
    def _give(t: Track, o: dict):
        t.label, t.name, t.role = o["auth_subject"], o.get("name") or o["auth_subject"], o.get("role")


# ------------------------------------------------------------------ zones ---
@dataclass
class ZoneState:
    id: int
    name: str
    status: str = "LEARNING"           # LEARNING / OK / IN_USE / CHANGED / MOTION
    score: float = 0.0                 # 0 = as normal, 1 = completely different
    since: float = field(default_factory=time.time)
    reported: bool = False


class ZoneWatcher:
    """
    One box per fixed item (PC, robot...). The first clear view (nobody in
    the box) becomes its reference. Then, while nobody is in the box:

      CHANGED  the box no longer looks like the reference for HOLD_S
               (moved, removed, covered) - normalised correlation, so a light
               switched on or off does not count;
      MOTION   pixels in the box keep changing frame to frame (something
               moving there with no person detected, e.g. a robot running).

    A person overlapping the box makes it IN_USE and pauses the comparison.
    """
    CHANGE_AT = 0.45
    MOTION_AT = 12.0                   # mean abs pixel change (0-255) between frames
    HOLD_S = 3.0

    def __init__(self):
        self.refs: dict[int, np.ndarray] = {}
        self.prev: dict[int, np.ndarray] = {}
        self.states: dict[int, ZoneState] = {}
        self._pending: dict[int, tuple[str, float]] = {}

    def reset(self, zone_id: Optional[int] = None):
        for d in (self.refs, self.prev, self.states, self._pending):
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

    def update(self, zones: list[dict], gray: np.ndarray, person_rects_norm: list[tuple],
               now: float) -> list[ZoneState]:
        """zones: [{"id", "name", "x", "y", "w", "h"}] normalised 0-1."""
        out = []
        for z in zones:
            zid, rect = z["id"], (z["x"], z["y"], z["w"], z["h"])
            st = self.states.setdefault(zid, ZoneState(zid, z["name"]))
            st.name = z["name"]
            patch = self._patch(gray, rect)
            if patch is None:
                continue
            occupied = any(iou(rect, p) > 0.02 for p in person_rects_norm)
            prev = self.prev.get(zid)
            self.prev[zid] = patch
            if occupied:
                self._set(st, "IN_USE", now)
                self._pending.pop(zid, None)
                out.append(st)
                continue
            ref = self.refs.get(zid)
            if ref is None or ref.shape != patch.shape:
                self.refs[zid] = patch     # first clear view = how it normally looks
                self._set(st, "OK", now)
                out.append(st)
                continue
            st.score = round(self._difference(ref, patch), 3)
            motion = prev is not None and prev.shape == patch.shape and \
                float(cv2.absdiff(prev, patch).mean()) > self.MOTION_AT
            want = "MOTION" if motion else "CHANGED" if st.score > self.CHANGE_AT else "OK"
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


# --------------------------------------------------------------- drawing ---
COLORS = {"ADMIN": (246, 92, 139), "LAB_STAFF": (250, 165, 96), "STUDENT": (129, 199, 52),
          None: (36, 191, 251)}                          # BGR: violet / blue / green / amber
ROLE_NAMES = {"ADMIN": "Admin", "LAB_STAFF": "Staff", "STUDENT": "Student"}
ZONE_COLORS = {"OK": (160, 160, 160), "IN_USE": (250, 165, 96), "CHANGED": (60, 60, 240),
               "MOTION": (0, 165, 255), "LEARNING": (160, 160, 160)}


def draw(frame, tracks: list[Track], zones: list[dict], states: dict, door_rect_norm=None):
    h, w = frame.shape[:2]
    for z in zones:
        st = states.get(z["id"])
        status = st.status if st else "LEARNING"
        c = ZONE_COLORS.get(status, (160, 160, 160))
        x, y = int(z["x"] * w), int(z["y"] * h)
        cv2.rectangle(frame, (x, y), (int((z["x"] + z["w"]) * w), int((z["y"] + z["h"]) * h)), c, 2)
        # Box labels sit at the bottom so they never hide a person's name tag.
        _tag(frame, f'{z["name"]} {status.lower().replace("_", " ")}', x,
             int((z["y"] + z["h"]) * h) + 18, c)
    if door_rect_norm:
        x, y = int(door_rect_norm[0] * w), int(door_rect_norm[1] * h)
        cv2.rectangle(frame, (x, y), (int((door_rect_norm[0] + door_rect_norm[2]) * w),
                                      int((door_rect_norm[1] + door_rect_norm[3]) * h)), (200, 200, 200), 1)
        _tag(frame, "door", x, y, (200, 200, 200))
    for t in tracks:
        c = COLORS.get(t.role if t.label else None, COLORS[None])
        x, y, bw, bh = (int(v) for v in t.box)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), c, 2)
        if t.label:
            role = ROLE_NAMES.get(t.role, "")
            label = f"{t.name or t.label}{f' ({role})' if role else ''} {t.label}"
        else:
            label = "Unknown"
        _tag(frame, label, x, y, c)
    return frame


def _tag(frame, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y0 = max(th + 6, y)
    cv2.rectangle(frame, (x, y0 - th - 6), (x + tw + 8, y0), color, -1)
    cv2.putText(frame, text, (x + 4, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
