"""
Live activity lines for the Security page (2026-11-11, owner: "a live bar under the cameras, like the news: the man
in the green shirt is most likely at the UR5e, the one in blue is bending").

Built ONLY from what the camera service already has for every tracked person - no new model, no extra GPU work:
  * who      - the name when the person is named (a look guess keeps its "?"), else "Person <track id>";
  * colour   - the most common colour of the upper-body band of the box (vision.color_signature);
  * posture  - from the box shape and its recent change: standing / seated / bending or crouching / lying,
               plus "moving" when the box travels;
  * near     - the mapped box (robot, PC, door...) the person overlaps or stands closest to, worded "near" or
               "most likely at": a camera box next to a robot is a hint, not proof of what the person does.
Nothing here names anyone: names come only from the Labeler's evidence. No picture leaves the service.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

HUE_NAMES = ["red", "orange", "yellow", "yellow-green", "green", "green", "teal", "blue", "blue", "purple",
             "pink", "red"]               # 12 bins of 15 degrees, shifted by 7 so red falls in one bin (vision.py)
VAL_NAMES = ["black", "dark grey", "grey", "white"]
HUE_BINS, VAL_BINS = 12, 4
NEAR_MAX = 0.12                           # a mapped box this close (share of the frame width) counts as "near"


def top_colour(color: Optional[np.ndarray]) -> Optional[str]:
    """Colour name of the upper-body band (second of the three BODY_PARTS bands)."""
    if color is None:
        return None
    n = HUE_BINS + VAL_BINS
    if len(color) < 2 * n:
        return None
    band = np.asarray(color[n:2 * n], dtype=np.float32)
    hue, val = band[:HUE_BINS], band[HUE_BINS:]
    if float(hue.sum()) >= 0.35:                      # clearly coloured clothes
        return HUE_NAMES[int(np.argmax(hue))]
    return VAL_NAMES[int(np.argmax(val))]


def posture(box, vel=(0.0, 0.0)) -> str:
    """From the box shape (height / width), as tools/security_vision already reads postures."""
    w, h = max(box[2], 1e-6), box[3]
    r = h / w
    if r >= 2.2:
        p = "standing"
    elif r >= 1.4:
        p = "seated or leaning"
    elif r >= 0.8:
        p = "bending or crouching"
    else:
        p = "lying down"
    speed = math.hypot(*vel) / max(h, 1e-6)            # box heights per second
    if speed > 0.35 and r >= 1.4:
        p = "walking" if p == "standing" else p + ", moving"
    return p


def nearest_zone(box, zones: list, fw: int, fh: int) -> Optional[tuple[str, bool]]:
    """(zone name, overlaps) of the mapped box the person touches or is closest to, or None."""
    if not zones or fw <= 0 or fh <= 0:
        return None
    x, y, w, h = box[0] / fw, box[1] / fh, box[2] / fw, box[3] / fh
    cx, cy = x + w / 2, y + h / 2
    best = None
    for z in zones:
        zx, zy, zw, zh = float(z.get("x", 0)), float(z.get("y", 0)), float(z.get("w", 0)), float(z.get("h", 0))
        name = z.get("name")
        if not name or zw <= 0 or zh <= 0:
            continue
        ix = max(0.0, min(x + w, zx + zw) - max(x, zx))
        iy = max(0.0, min(y + h, zy + zh) - max(y, zy))
        overlap = ix * iy > 0.05 * w * h
        dx = max(zx - cx, 0.0, cx - (zx + zw))
        dy = max(zy - cy, 0.0, cy - (zy + zh))
        d = 0.0 if overlap else math.hypot(dx, dy)
        if best is None or d < best[0]:
            best = (d, name, overlap)
    if best is None or best[0] > NEAR_MAX:
        return None
    return best[1], best[2]


def describe(tracks, zones: list, fw: int, fh: int, max_lines: int = 12) -> list[dict]:
    """One entry per tracked person, named people first. `text` is the sentence the portal shows."""
    out = []
    for t in tracks:
        if t.label:
            who = (t.name or t.label) + (" ?" if t.source in ("look", "desk") else "")
        else:
            who = f"Person {t.id}"
        colour = top_colour(t.look.color if getattr(t, "look", None) is not None else None)
        pose = posture(t.box, getattr(t, "vel", (0.0, 0.0)))
        nz = nearest_zone(t.box, zones, fw, fh)
        parts = [who + (f" ({colour} top)" if colour else "")]
        parts.append(pose)
        if nz:
            parts.append(("most likely at " if nz[1] else "near ") + nz[0])
        if getattr(t, "crowded", False):
            parts.append("next to someone")
        out.append({"track_id": t.id, "label": t.label, "who": who, "colour": colour, "posture": pose,
                    "near": nz[0] if nz else None, "named": bool(t.label), "text": " - ".join(parts)})
    out.sort(key=lambda e: (not e["named"], e["track_id"]))
    return out[:max_lines]
