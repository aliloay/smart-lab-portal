"""
Equipment watch: the detector looks for monitors / laptops in the background
(every scan ~60 s) and compares what it finds with the NAMED boxes. A
detection has no name, so the boxes stay the source of truth; the scans only
keep them honest:

    * a named box whose item is clearly found a little off (same size, only
      one candidate, nobody at it), in two scans that agree -> nudge the box
    * an item found where no box is, in two scans in a row  -> "unnamed
      monitor here" (once per place)
    * a box whose item the detector HAS found before but not for many scans,
      with nobody standing in front of it                  -> "not seen"

A person in front of a monitor hides it from the detector - that is "in use",
never "missing", so any box with a person on it is skipped.
Pure logic, tested in test_equipwatch.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Box = tuple  # (x, y, w, h), fractions 0-1

MATCH_IOU = 0.2          # a detection this close to a box is that box's item
IN_PLACE_IOU = 0.6       # already on it: nothing to nudge
SIZE_TOL = 0.5           # nudged only when the size agrees within +-50 %
AGREE = 0.02             # two scans agree when every corner is within 2 % of the picture
NOT_SEEN_SCANS = 10      # ~10 min at one scan / 60 s
SEEN_BEFORE = 3          # only items the detector has proven it can see
PERSON_COVER = 0.25      # a person covering this much of a box hides it


def iou(a: Box, b: Box) -> float:
    iw = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def covered(box: Box, by: Box) -> float:
    """Share of `box` that `by` covers."""
    iw = max(0.0, min(box[0] + box[2], by[0] + by[2]) - max(box[0], by[0]))
    ih = max(0.0, min(box[1] + box[3], by[1] + by[3]) - max(box[1], by[1]))
    return iw * ih / max(box[2] * box[3], 1e-9)


def gap(a: Box, b: Box) -> float:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]),
               abs(a[0] + a[2] - b[0] - b[2]), abs(a[1] + a[3] - b[1] - b[3]))


@dataclass
class Found:
    kind: str
    score: float
    box: Box


@dataclass
class Result:
    nudge: dict = field(default_factory=dict)        # box id -> new box
    unnamed: list = field(default_factory=list)      # Found, confirmed twice, not reported before
    not_seen: list = field(default_factory=list)     # box ids missing long enough (reported once)
    seen_again: list = field(default_factory=list)   # box ids found again after "not seen"


class EquipmentWatch:
    def __init__(self):
        self.seen_count: dict[int, int] = {}
        self.missed: dict[int, int] = {}
        self.reported_missing: set[int] = set()
        self.pending_nudge: dict[int, Box] = {}
        self.pending_unnamed: list[Box] = []
        self.reported_unnamed: list[Box] = []
        self.last: list[Found] = []

    def forget(self):
        """The boxes were redrawn / the view moved: start over (nothing reported is repeated)."""
        self.seen_count.clear()
        self.missed.clear()
        self.pending_nudge.clear()
        self.pending_unnamed = []

    def update(self, boxes: dict[int, Box], found: list[Found], people: list[Box]) -> Result:
        self.last = list(found)
        res = Result()
        used: set[int] = set()
        for k, b in boxes.items():
            if any(covered(b, p) >= PERSON_COVER for p in people):
                self.missed[k] = 0                       # hidden by someone: in use, not missing
                self.pending_nudge.pop(k, None)
                cands = [i for i, f in enumerate(found) if iou(b, f.box) >= MATCH_IOU]
                used.update(cands)
                continue
            cands = [i for i, f in enumerate(found) if iou(b, f.box) >= MATCH_IOU]
            used.update(cands)
            if not cands:
                self.pending_nudge.pop(k, None)
                self.missed[k] = self.missed.get(k, 0) + 1
                if (self.missed[k] >= NOT_SEEN_SCANS and self.seen_count.get(k, 0) >= SEEN_BEFORE
                        and k not in self.reported_missing):
                    self.reported_missing.add(k)
                    res.not_seen.append(k)
                continue
            self.seen_count[k] = self.seen_count.get(k, 0) + 1
            self.missed[k] = 0
            if k in self.reported_missing:
                self.reported_missing.discard(k)
                res.seen_again.append(k)
            # Nudge only on a clear, single candidate that no other box claims.
            best = found[cands[0]].box if len(cands) == 1 else None
            if best is None or iou(b, best) >= IN_PLACE_IOU:
                self.pending_nudge.pop(k, None)
                continue
            if abs(best[2] / b[2] - 1) > SIZE_TOL or abs(best[3] / b[3] - 1) > SIZE_TOL:
                continue
            if any(j != k and iou(o, best) >= MATCH_IOU for j, o in boxes.items()):
                continue
            prev = self.pending_nudge.get(k)
            if prev is not None and gap(prev, best) <= AGREE:
                res.nudge[k] = best
                self.pending_nudge.pop(k)
            else:
                self.pending_nudge[k] = best
        # Items no box claims. One mostly on a person is skipped: that was a
        # lap or a phone ("Laptop" on someone bending over), not equipment.
        free = [f for i, f in enumerate(found) if i not in used
                and not any(covered(f.box, p) >= 0.5 for p in people)]
        confirmed = []
        for f in free:
            if any(gap(f.box, p) <= AGREE * 2 for p in self.pending_unnamed):
                if not any(iou(f.box, r) >= 0.3 for r in self.reported_unnamed):
                    confirmed.append(f)
                    self.reported_unnamed.append(f.box)
        self.pending_unnamed = [f.box for f in free]
        res.unnamed = confirmed
        return res
