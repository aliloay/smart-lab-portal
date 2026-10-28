"""
Appearance matching for the lab's own 3D-printed enclosures (2026-10-27) - a HINT, never an identification.

Reference photos (owner, several angles per box) live in  data/asset_refs/<marker code with ':' -> '_'>/*.jpg
with  data/asset_refs/manifest.json  {"assets": [{"code": "SLAB:D:BIN_NODE_1", "class": "consumables_node",
"views": ["front", "left", ...]}]}.  Matching is classic and fully local (OpenCV ORB keypoints + ratio test +
RANSAC homography inliers) - no model download, run only on request (not on every frame).

Decision levels (conservative - a wrong box is worse than "unknown"):
  PROBABLE   best asset has >= MIN_INLIERS geometric inliers AND beats the next asset by MARGIN (ratio)
             -> the UI says "looks like <asset> (unverified) - scan its marker"; live data is NOT shown on this alone
  AMBIGUOUS  two assets close (similar boxes) -> ask to scan the marker
  UNKNOWN    too little evidence / no references
VERIFIED identity comes only from the asset's QR marker (scan.py). Appearance never names an asset by itself and
never picks an asset because it is the only one online.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

MIN_INLIERS = 25
MARGIN = 1.6
ROOT = os.environ.get("ASSET_REFS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data", "asset_refs"))


def _cv():
    import cv2
    import numpy as np
    return cv2, np


@dataclass
class RefSet:
    code: str
    cls: str
    views: list = field(default_factory=list)       # [(name, keypoints, descriptors)]


class Matcher:
    def __init__(self, root: str = ROOT, nfeatures: int = 1500):
        self.root, self.nfeatures = os.path.abspath(root), nfeatures
        self.refs: list[RefSet] = []
        self._lock = threading.Lock()
        self._loaded_at = None

    # ------------------------------------------------------------------------------------- references ---
    def manifest(self) -> dict:
        p = os.path.join(self.root, "manifest.json")
        if not os.path.isfile(p):
            return {"assets": []}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _features(self, img):
        cv2, np = _cv()
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h, w = g.shape[:2]
        k = 640 / max(h, w)
        if k < 1:
            g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)       # lighting differences
        orb = cv2.ORB_create(nfeatures=self.nfeatures)
        return orb.detectAndCompute(g, None)

    def load(self) -> "Matcher":
        cv2, _ = _cv()
        refs = []
        for a in self.manifest().get("assets", []):
            d = os.path.join(self.root, a["code"].replace(":", "_"))
            rs = RefSet(a["code"], a.get("class", ""))
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        img = cv2.imread(os.path.join(d, f))
                        if img is None:
                            continue
                        kp, des = self._features(img)
                        if des is not None and len(kp) >= 20:
                            rs.views.append((f, kp, des))
            refs.append(rs)
        with self._lock:
            self.refs = refs
        return self

    def status(self) -> list[dict]:
        return [{"code": r.code, "class": r.cls, "photos": len(r.views)} for r in self.refs]

    # --------------------------------------------------------------------------------------- matching ---
    def _inliers(self, kp1, des1, kp2, des2) -> int:
        cv2, np = _cv()
        if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
            return 0
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        good = []
        for pair in bf.knnMatch(des1, des2, k=2):
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
                good.append(pair[0])
        if len(good) < 8:
            return len(good) // 2
        src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        if mask is None:
            return 0
        self._last_pts = src.reshape(-1, 2)[mask.ravel() == 1]     # where the match sits in the phone frame
        return int(mask.sum())

    _last_pts = None

    def match(self, img, exclude: Optional[tuple[str, str]] = None) -> dict:
        """img: BGR array. exclude=(code, view) leaves one reference out (evaluation)."""
        kp, des = self._features(img)
        scores = []
        for r in self.refs:
            best, pts = 0, None
            for name, rkp, rdes in r.views:
                if exclude and exclude == (r.code, name):
                    continue
                self._last_pts = None
                n = self._inliers(kp, des, rkp, rdes)
                if n > best:
                    best, pts = n, self._last_pts
            scores.append({"code": r.code, "class": r.cls, "inliers": best, "_pts": pts})
        scores.sort(key=lambda s: -s["inliers"])
        if not scores or scores[0]["inliers"] < MIN_INLIERS:
            decision = "UNKNOWN"
        elif len(scores) > 1 and scores[0]["inliers"] < MARGIN * max(1, scores[1]["inliers"]):
            decision = "AMBIGUOUS"
        else:
            decision = "PROBABLE"
        # 2026-10-28 (owner: "the message appeared but there was no frame around the bin"): the frame around the
        # matched points (5th-95th percentile, so stray matches do not stretch it), 0..1 of the frame
        np = _cv()[1]
        h, w = img.shape[:2]
        k = min(1.0, 640 / max(h, w))
        for sc in scores:
            p = sc.pop("_pts")
            if decision == "PROBABLE" and sc is scores[0] and p is not None and len(p) >= 8:
                x1, y1 = np.percentile(p, 5, axis=0); x2, y2 = np.percentile(p, 95, axis=0)
                sc["box"] = {"x": round(float(x1) / (w * k), 4), "y": round(float(y1) / (h * k), 4),
                             "w": round(float(x2 - x1) / (w * k), 4), "h": round(float(y2 - y1) / (h * k), 4)}
        return {"decision": decision, "best": scores[0] if scores and decision == "PROBABLE" else None,
                "candidates": scores[:3], "min_inliers": MIN_INLIERS, "margin": MARGIN,
                "note": "appearance only - verify with the asset's QR marker before trusting its live data"}


_MATCHER: Optional[Matcher] = None


def matcher() -> Matcher:
    global _MATCHER
    if _MATCHER is None:
        _MATCHER = Matcher().load()
    return _MATCHER


def evaluate(m: Matcher) -> dict:
    """Leave-one-view-out over the reference photos: each photo is matched against all the OTHER photos.
    Reports correct PROBABLE, wrong PROBABLE (the number that must be 0), and how often it says unknown/ambiguous."""
    cv2, _ = _cv()
    out = {"views": 0, "correct": 0, "wrong": 0, "unknown": 0, "ambiguous": 0, "wrong_cases": []}
    for r in m.refs:
        d = os.path.join(m.root, r.code.replace(":", "_"))
        for name, _, _ in r.views:
            img = cv2.imread(os.path.join(d, name))
            res = m.match(img, exclude=(r.code, name))
            out["views"] += 1
            if res["decision"] == "PROBABLE":
                if res["best"]["code"] == r.code:
                    out["correct"] += 1
                else:
                    out["wrong"] += 1; out["wrong_cases"].append({"photo": f"{r.code}/{name}", "said": res["best"]["code"]})
            elif res["decision"] == "AMBIGUOUS":
                out["ambiguous"] += 1
            else:
                out["unknown"] += 1
    n = max(1, out["views"])
    p = out["correct"] + out["wrong"]
    out["precision"] = round(out["correct"] / p, 3) if p else None
    out["identified_rate"] = round(out["correct"] / n, 3)
    return out
