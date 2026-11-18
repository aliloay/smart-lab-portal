"""
Live activity lines for the Security page (2026-11-11, owner: "a live bar under the cameras, like the news: the man
in the green shirt is most likely at the UR5e, the one in blue is bending").

Built ONLY from what the camera service already has for every tracked person - no new model, no extra GPU work:
  * who      - the name when the person is named (a look guess keeps its "?"), else "Person <lab number>" (labmap.py, one number per person on both cameras);
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
EDGE_PX = 3                               # box touching the frame edge within 3 px is clipped by the camera view
FULL_BODY_RATIO = 2.6                     # canonical standing height / width ratio in these cameras

# Canonical anatomical vertical spans (fraction of full standing body height from top of head = 0.0 to ankles = 1.0).
# Used to classify whether body parts are OBSERVED, OCCLUDED, or OUT_OF_FRAME without inventing hidden coordinates.
BODY_KEYPOINTS = (
    ("head", 0.00, 0.18),
    ("shoulders", 0.15, 0.28),
    ("torso", 0.22, 0.52),
    ("elbows", 0.30, 0.48),
    ("wrists", 0.42, 0.58),
    ("hips", 0.48, 0.60),
    ("knees", 0.68, 0.82),
    ("ankles", 0.88, 1.00),
)


def is_bottom_clipped(box, fh: int = 0, partial: bool = False) -> bool:
    """True when the person box is cut off by the bottom of the camera frame (legs/feet out of view)."""
    if partial:
        return True
    x, y, w, h = box
    return fh > 0 and y + h >= fh - EDGE_PX and h < 2.2 * max(w, 1e-6)


def pose_visibility(box, fw: int = 0, fh: int = 0, crowded: bool = False, partial: bool = False) -> dict[str, dict]:
    """Classify each anatomical body part as PREDICTED, OCCLUDED or OUT_OF_FRAME from the person BOX only.

    These cameras run a person-box detector, not a keypoint/pose model, so no joint is ever OBSERVED here:
    a part inside the visible box gets a PREDICTED position (canonical body proportions inside the box,
    basis "box_geometry"), and parts cut off by the frame edge or likely hidden by a neighbour get xy=None.
    (Integration review 2026-11-18: the first version said OBSERVED at 0.85 for these box-proportion guesses.)"""
    x, y, w, h = box
    w_safe = max(float(w), 1e-6)
    full_h = max(float(h), FULL_BODY_RATIO * w_safe)
    bottom_cut = is_bottom_clipped(box, fh=fh, partial=partial)
    top_cut = fh > 0 and y <= EDGE_PX and h < FULL_BODY_RATIO * w_safe
    side_cut = fw > 0 and (x <= EDGE_PX or x + w >= fw - EDGE_PX)
    vis_bottom = (h / full_h) if bottom_cut else 1.0
    vis_top = (1.0 - h / full_h) if (top_cut and not bottom_cut) else 0.0
    out: dict[str, dict] = {}
    for name, y0, y1 in BODY_KEYPOINTS:
        if bottom_cut and y0 >= vis_bottom:
            out[name] = {"state": "OUT_OF_FRAME", "confidence": 0.0, "xy": None, "basis": "box_geometry"}
        elif top_cut and y1 <= vis_top:
            out[name] = {"state": "OUT_OF_FRAME", "confidence": 0.0, "xy": None, "basis": "box_geometry"}
        elif (bottom_cut and y1 > vis_bottom) or (top_cut and y0 < vis_top):
            out[name] = {"state": "OCCLUDED", "confidence": 0.35, "xy": None, "basis": "box_geometry"}
        elif side_cut and name in ("elbows", "wrists"):
            out[name] = {"state": "OCCLUDED", "confidence": 0.40, "xy": None, "basis": "box_geometry"}
        elif crowded and name in ("elbows", "wrists", "hips", "knees", "ankles"):
            out[name] = {"state": "OCCLUDED", "confidence": 0.45, "xy": None, "basis": "box_geometry"}
        else:
            rel_y = ((y0 + y1) * 0.5) / max(vis_bottom, 1e-6) if bottom_cut else (y0 + y1) * 0.5
            cy = round(float(y + min(1.0, max(0.0, rel_y)) * h), 1)
            cx = round(float(x + 0.5 * w), 1)
            # inside the visible box, but where exactly is a proportion guess - never OBSERVED without keypoints
            out[name] = {"state": "PREDICTED", "confidence": 0.5, "xy": [cx, cy], "basis": "box_geometry"}
    return out


def top_colour(color: Optional[np.ndarray]) -> Optional[str]:
    """Colour name of the upper-body band (second of the three BODY_PARTS bands)."""
    return band_colour(color, 1)


def legs_colour(color: Optional[np.ndarray]) -> Optional[str]:
    """2026-11-18 (owner: grey sweatpants vs light-blue jeans): colour name of the legs band (third band)."""
    return band_colour(color, 2)


def band_colour(color: Optional[np.ndarray], i: int) -> Optional[str]:
    """Colour name of BODY_PARTS band i (0 head, 1 upper body, 2 legs)."""
    if color is None:
        return None
    n = HUE_BINS + VAL_BINS
    if len(color) < (i + 1) * n:
        return None
    band = np.asarray(color[i * n:(i + 1) * n], dtype=np.float32)
    hue, val = band[:HUE_BINS], band[HUE_BINS:]
    # 2026-11-17 (lab: "red top" on a person in black): the box middle also holds skin, the orange-brown chairs and
    # wooden desks, all moderately saturated red/orange. A colour is named only when it clearly dominates the band;
    # red/orange/yellow (the skin and wood range) needs even more. Otherwise the brightness name is used.
    mass = float(hue.sum())
    if mass > 0:
        top = int(np.argmax(hue))
        share = float(hue[top]) / mass                   # how much of the coloured part is this one hue
        warm = HUE_NAMES[top] in ("red", "orange", "yellow")
        if mass >= (0.70 if warm else 0.55) and share >= 0.6:
            return HUE_NAMES[top]
    if float(val.sum()) <= 0:
        return None
    return VAL_NAMES[int(np.argmax(val))]


def posture(box, vel=(0.0, 0.0), fh: int = 0, partial: bool = False) -> str:
    """From the box shape (height / width), as tools/security_vision already reads postures.
    When the box is cut off at the bottom of the frame (legs out of view), reports 'upper body in view'
    rather than mistaking the cropped aspect ratio for 'bending or crouching' or 'lying down'."""
    w, h = max(box[2], 1e-6), box[3]
    r = h / w
    clipped = is_bottom_clipped(box, fh=fh, partial=partial)
    if clipped:
        p = "upper body in view"
    elif r >= 2.2:
        p = "standing"
    elif r >= 1.4:
        p = "seated or leaning"
    elif r >= 0.8:
        p = "bending or crouching"
    else:
        p = "lying down"
    speed = math.hypot(*vel) / max(h, 1e-6)            # box heights per second
    if speed > 0.35 and (r >= 1.4 or clipped):
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


SPOT_MATCH = 0.3       # person box vs a recorded spot (seat_capture.py), IoU: this person is AT that place
SPOT_NEAR = 0.08       # ...or its centre this close (0-1 of the picture) to a spot: NEAR that place


def _iou(a, b) -> float:
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u > 0 else 0.0


def place_of(box, zones: list, fw: int, fh: int) -> Optional[tuple[str, bool]]:
    """2026-11-18 (owner: "Nour is clearly near the UR5e, I am near Hemaly's desk"): where the person is, from the
    spots recorded with seat_capture.py (z["seat"]: where a person at that PC / robot appears in this picture) -
    (name, at) - else the old box-to-box guess (nearest_zone)."""
    if fw > 0 and fh > 0:
        p = (box[0] / fw, box[1] / fh, box[2] / fw, box[3] / fh)
        best = None
        for z in zones:
            if not z.get("name"):
                continue
            for s in (z.get("spots") or ([z["seat"]] if z.get("seat") else [])):    # several spots per place
                o = _iou(p, s)
                d = math.hypot(p[0] + p[2] / 2 - (s[0] + s[2] / 2), p[1] + p[3] - (s[1] + s[3]))   # feet to feet
                key = (-o, d)
                if (o >= SPOT_MATCH or d <= SPOT_NEAR) and (best is None or key < best[0]):
                    best = (key, z["name"], o >= SPOT_MATCH)
        if best:
            return best[1], best[2]
    return nearest_zone(box, zones, fw, fh)


def place_words(name: str, at: bool, zones: list, owners: Optional[dict] = None) -> str:
    """"at the UR5e" / "near PC-04 (Eng. Hemaly's desk)" / "most likely at PC-07"."""
    z = next((z for z in zones if z.get("name") == name), {})
    robot = z.get("alert_on_motion", True) is False
    seat = bool(z.get("seat"))
    what = f"the {name}" if robot else name
    if owners and owners.get(name.upper()):
        what += f" ({owners[name.upper()]}'s desk)"
    if at:
        return ("at " if seat or robot else "most likely at ") + what
    return "near " + what


def describe(tracks, zones: list, fw: int, fh: int, max_lines: int = 12,
             owners: Optional[dict] = None) -> list[dict]:
    """One entry per tracked person, named people first. `text` is the sentence the portal shows."""
    out = []
    for t in tracks:
        if t.label:
            who = (t.name or t.label) + (" ?" if t.source in ("look", "desk") else "")
        elif getattr(t, "lab_no", None):
            who = f"Person {t.lab_no}"             # the LAB number, the same on both cameras (labmap.py)
        else:
            who = "New person"                     # numbered within ~1.5 s, once the look is measured
        look_obj = getattr(t, "look", None)
        colour = top_colour(look_obj.color if look_obj is not None else None)
        is_part = bool(getattr(look_obj, "partial", False)) or is_bottom_clipped(t.box, fh=fh)
        crowded = bool(getattr(t, "crowded", False))
        pose = posture(t.box, getattr(t, "vel", (0.0, 0.0)), fh=fh, partial=is_part)
        pv = pose_visibility(t.box, fw=fw, fh=fh, crowded=crowded, partial=is_part)
        nz = place_of(t.box, zones, fw, fh)
        # trousers only when the legs are in view (a cut-off box's lowest band is still the shirt)
        legs = None if is_part else legs_colour(look_obj.color if look_obj is not None else None)
        clothes = ", ".join(x for x in (f"{colour} top" if colour else "", f"{legs} trousers" if legs else "") if x)
        parts = [who + (f" ({clothes})" if clothes else "")]
        parts.append(pose)
        if nz:
            parts.append(place_words(nz[0], nz[1], zones, owners))
        if crowded:
            parts.append("next to someone")
        out.append({"track_id": t.id, "label": t.label, "who": who, "colour": colour, "legs": legs, "posture": pose,
                    "near": nz[0] if nz else None, "named": bool(t.label), "text": " - ".join(parts),
                    # 2026-11-17: the portal merges the two cameras' lines of one person (same name or lab
                    # number) and keeps the closer camera's description (bigger box = nearer, more reliable)
                    "lab_no": getattr(t, "lab_no", None), "at": bool(nz and nz[1]),
                    "hint": getattr(t, "hint", None),      # desk guess ("Eng. Hemaly?") - preselected by Confirm
                    "size": round(t.box[3] / fh, 3) if fh else 0.0,
                    "partial": is_part,
                    "pose_visibility": pv})
    out.sort(key=lambda e: (not e["named"], e["track_id"]))
    return out[:max_lines]
