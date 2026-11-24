"""
Visual robot motion inside a robot's box (the camera's own, independent
evidence - compared with the robot's telemetry in the portal).

Per robot box, every analysed frame:

  * dense optical flow (Farneback) on the box, shrunk to <= 160 px wide;
  * the box split into an 8 x 8 grid: a cell "moves" when its median flow is
    above MIN_FLOW_PX (in the shrunk image); MIN_CELLS moving cells = the
    robot moves (a thin arm covers few cells) - the share of moving cells and
    the mean flow direction / magnitude of the moving cells are reported;
  * brightness is evened out first (a light switched on is not movement) and
    many cells moving the SAME way (coherent flow over >= SHAKE_SHARE of the
    box) is camera shake, not robot motion - a turning arm gives vectors that
    differ in direction and size;
  * a person covering more than OCCLUDED_AT of the box makes the result
    OCCLUDED - never "not moving";
  * temporal filter: "moving" only after PERSIST frames in a row; it stays
    moving for LINGER_S after the last moving frame.

Output (dict, posted with the camera's state): state MOVING / STILL /
OCCLUDED / UNKNOWN, moving_share, flow_dx / flow_dy (px per frame in the
full picture), magnitude, last_motion_at (epoch s), occlusion share.
Thresholds are NOT tuned on the lab robots yet.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

WORK_W = 160
GRID = 8
MIN_FLOW_PX = 0.6            # median flow in a cell (shrunk px / frame) that counts as movement
MIN_CELLS = 2                # this many moving cells = the robot moves
SHAKE_SHARE = 0.3            # coherent flow over at least this share of the box ...
SHAKE_COHERENCE = 0.9        # ... with nearly identical vectors = camera shake
OCCLUDED_AT = 0.35
# Lab 24 Nov 2026: people walking in front of a still robot gave 5.7 % / 3.1 % VISUAL_ANOMALY. Flow cells under a person's
# box (grown by PERSON_MARGIN: the box is up to one analysis pass old; kept PERSON_HOLD_S after they moved on) are not robot
# evidence. The other cells still decide, so a moving arm beside a person is seen. Not yet run on live cameras.
PERSON_MARGIN = 0.25
PERSON_HOLD_S = 0.8
PARTLY_HIDDEN = 0.15         # this much masked and no motion seen: OCCLUDED ("cannot say"), not STILL
PERSIST = 2
LINGER_S = 3.0


@dataclass
class _State:
    prev: Optional[np.ndarray] = None
    run: int = 0
    last_motion_at: Optional[float] = None
    masked: dict = field(default_factory=dict)         # (gy, gx) -> last time a person was there
    out: dict = field(default_factory=lambda: {"state": "UNKNOWN"})


def _covered(box, people) -> float:
    x, y, w, h = box
    tot = 0.0
    for (px, py, pw, ph) in people:
        iw = max(0.0, min(x + w, px + pw) - max(x, px))
        ih = max(0.0, min(y + h, py + ph) - max(y, py))
        tot += iw * ih
    return min(1.0, tot / max(w * h, 1e-9))


class RobotVisualMotion:
    def __init__(self):
        self.s: dict[int, _State] = {}

    def update(self, zones: list[dict], gray: np.ndarray, people_norm: list[tuple],
               now: Optional[float] = None) -> dict[int, dict]:
        """zones: the robot boxes ({id, x, y, w, h} as fractions). Returns {zone id: result}."""
        now = now or time.time()
        H, W = gray.shape[:2]
        out = {}
        for z in zones:
            st = self.s.setdefault(z["id"], _State())
            box = (z["x"], z["y"], z["w"], z["h"])
            x0, y0 = int(z["x"] * W), int(z["y"] * H)
            x1, y1 = int((z["x"] + z["w"]) * W), int((z["y"] + z["h"]) * H)
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            k = min(1.0, WORK_W / (x1 - x0))
            roi = cv2.resize(gray[y0:y1, x0:x1], None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            roi = cv2.GaussianBlur(roi, (3, 3), 0)
            prev, st.prev = st.prev, roi
            occ = _covered(box, people_norm)
            if prev is None or prev.shape != roi.shape:
                st.out = {"state": "UNKNOWN", "occlusion": round(occ, 2)}
                out[z["id"]] = st.out
                continue
            if occ >= OCCLUDED_AT:
                st.run = 0
                st.out = {"state": "OCCLUDED", "occlusion": round(occ, 2),
                          "last_motion_at": st.last_motion_at}
                out[z["id"]] = st.out
                continue
            gain = float(roi.mean()) / max(float(prev.mean()), 1.0)
            prev_n = np.clip(prev.astype(np.float32) * gain, 0, 255).astype(np.uint8)
            flow = cv2.calcOpticalFlowFarneback(prev_n, roi, None, 0.5, 2, 9, 2, 5, 1.1, 0)
            mag = np.linalg.norm(flow, axis=2)
            h, w = mag.shape
            moving, vecs, hidden = 0, [], 0
            grown = [(p[0] - p[2] * PERSON_MARGIN, p[1] - p[3] * PERSON_MARGIN / 2,
                      p[2] * (1 + 2 * PERSON_MARGIN), p[3] * (1 + PERSON_MARGIN)) for p in people_norm]
            for gy in range(GRID):
                for gx in range(GRID):
                    cx0, cy0 = z["x"] + z["w"] * gx / GRID, z["y"] + z["h"] * gy / GRID
                    if any(cx0 < b[0] + b[2] and cx0 + z["w"] / GRID > b[0] and cy0 < b[1] + b[3] and cy0 + z["h"] / GRID > b[1]
                           for b in grown):
                        st.masked[(gy, gx)] = now
                    if now - st.masked.get((gy, gx), -1e9) <= PERSON_HOLD_S:
                        hidden += 1
                        continue
                    cell = (slice(gy * h // GRID, (gy + 1) * h // GRID), slice(gx * w // GRID, (gx + 1) * w // GRID))
                    m = float(np.median(mag[cell]))
                    if m >= MIN_FLOW_PX:
                        moving += 1
                        vecs.append(np.median(flow[cell].reshape(-1, 2), axis=0))
            share = moving / (GRID * GRID)
            hid = hidden / (GRID * GRID)
            shake = False
            if vecs and share >= SHAKE_SHARE:
                v = np.array(vecs)
                mean = v.mean(axis=0)
                coh = float(np.linalg.norm(mean) / max(np.linalg.norm(v, axis=1).mean(), 1e-6))
                shake = coh >= SHAKE_COHERENCE
            is_moving = moving >= MIN_CELLS and not shake
            st.run = st.run + 1 if is_moving else 0
            if st.run >= PERSIST:
                st.last_motion_at = now
            active = st.last_motion_at is not None and now - st.last_motion_at <= LINGER_S
            d = np.array(vecs).mean(axis=0) / k if vecs else np.zeros(2)
            st.out = {"state": "MOVING" if active else "OCCLUDED" if hid >= PARTLY_HIDDEN else "STILL", "person_masked": round(hid, 2), "moving_share": round(share, 2),
                      "flow_dx": round(float(d[0]), 2), "flow_dy": round(float(d[1]), 2),
                      "magnitude": round(float(np.linalg.norm(d)), 2), "camera_shake": shake,
                      "occlusion": round(occ, 2), "last_motion_at": st.last_motion_at}
            out[z["id"]] = st.out
        return out
