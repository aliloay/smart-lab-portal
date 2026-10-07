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

    def __init__(self, reid_path: Optional[str] = None):
        self.net = None
        if reid_path:
            try:
                self.net = cv2.dnn.readNet(reid_path)
            except cv2.error as e:     # half-downloaded or damaged file: colours only
                print(f"[vision] re-id model not usable ({e.__class__.__name__}): colours only")

    DEEP_EVERY_S = 1.0                 # body model at least this often (~100 ms a person)...
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
        if now is not None:
            self._last_deep = now
        if self.net is not None and boxes:
            crops, idx = [], []
            H, W = frame.shape[:2]
            for i, (x, y, w, h) in enumerate(boxes):
                x0, y0 = int(max(0, x)), int(max(0, y))
                x1, y1 = int(min(W, x + w)), int(min(H, y + h))
                if x1 - x0 < 8 or y1 - y0 < 16:
                    continue
                img = cv2.resize(frame[y0:y1, x0:x1], self.REID_SIZE)[:, :, ::-1].astype(np.float32) / 255.0
                crops.append((img - self.MEAN) / self.STD)
                idx.append(i)
            if crops:
                self.net.setInput(cv2.dnn.blobFromImages(crops))
                feats = self.net.forward().reshape(len(crops), -1)
                feats /= np.maximum(np.linalg.norm(feats, axis=1, keepdims=True), 1e-6)
                for i, f in zip(idx, feats):
                    out[i].deep = f
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
            if looks[bi] is not None:
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
    REACQUIRE_MAX = 0.30               # this alike to get a name back...
    REACQUIRE_MARGIN = 0.08            # ...and clearly more alike than anyone else
    LEARN_MAX = 0.45                   # a frame this different is not learnt (likely a mix-up)
    FACE_VOTES = 2                     # agreeing face matches before a face names someone
    FACE_WINDOW_S = 10.0               # ...within this long

    def __init__(self):
        self.identities: dict[str, Identity] = {}
        self.votes: dict[int, list[tuple[str, float]]] = {}

    def face_vote(self, track_id: int, label: str, now: float):
        """The face server matched this track's face to `label`."""
        self.votes.setdefault(track_id, []).append((label, now))

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
        for label in list(self.identities):
            if label not in inside and label not in held:
                del self.identities[label]
        self._face(tracks, inside, {k["auth_subject"]: k for k in (known or [])}, now)

        self._fix_after_crossing(tracks, inside, now)

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

        # 2) Someone named before, back in view: by their locked look.
        for t in sorted(tracks, key=lambda t: t.first_seen):
            if t.label or t.crowded or not free:
                continue
            scored = []
            for o in free:
                d = self._distance(t, o["auth_subject"])
                if d is not None:
                    scored.append((d, o["auth_subject"]))
            scored.sort()
            if not scored or scored[0][0] > self.REACQUIRE_MAX:
                continue
            if len(scored) > 1 and scored[1][0] - scored[0][0] < self.REACQUIRE_MARGIN:
                continue
            o = inside[scored[0][1]]
            self._give(t, o)
            free.remove(o)

        # 3) Elimination: one free name, one unlabelled person.
        unlabelled = [t for t in tracks if not t.label]
        if len(free) == 1 and len(unlabelled) == 1:
            self._give(unlabelled[0], free[0])

        self._learn(tracks)
        for t in tracks:
            t.entered = bool(t.label and t.label in inside)
        self._verify(tracks)

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
            self._give(t, who, "face")
            taken.add(label)

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
        labels = [t.label for t in group if t.label and t.label in inside
                  and t.label in self.identities
                  and self.identities[t.label].samples >= self.LOCK_SAMPLES]
        if not labels or len(group) < 2 or len(group) > 6:
            return

        def cost(pairs):
            total = 0.0
            for t, label in pairs:
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
            self._give(t, inside[label])

    def _learn(self, tracks: list[Track]):
        for t in tracks:
            if not t.label or t.crowded or t.look is None:
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
    def _give(t: Track, o: dict, source: str = "door"):
        t.label, t.name, t.role = o["auth_subject"], o.get("name") or o["auth_subject"], o.get("role")
        t.source = source
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
        else:
            label = "Unknown"
        _tag(frame, label, x, y, c)
    return frame


def _tag(frame, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y0 = max(th + 6, y)
    cv2.rectangle(frame, (x, y0 - th - 6), (x + tw + 8, y0), color, -1)
    cv2.putText(frame, text, (x + 4, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
