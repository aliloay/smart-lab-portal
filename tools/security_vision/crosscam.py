"""
Two cameras, one person, one name (2026-10-15).

Each camera service still tracks on its own (its own process, stream, ids). This module lets a
service borrow a CONFIRMED name from the other camera for the SAME person - so when someone is
hidden or turned away in this view, the other view (opposite corner) keeps the name on them.

How "the same person" is decided - evidence, never order or proximity alone:
  1. FLOOR: each camera has a floor map (anchors/<DEVICE>_floor.json: >= 4 points clicked in its
     picture with their room position in metres). A person's feet (box bottom-centre) map to a
     room position; the two cameras must agree within GATE_M.
  2. TIME: the other camera's observation is at most MAX_AGE_S old.
  3. ONE-TO-ONE: an optimal matching (vision.assign_max) - never "whoever is nearest" alone.
  4. STABILITY: the pairing must hold for STABLE_PASSES passes in a row before a name moves.
  5. NO CONFLICT: a name never moves onto a person who is crowded, already named, whose own face
     votes say someone else, or whose name is already on another person in this view. If the two
     cameras name the same person differently, nothing changes and the conflict is logged.
Without a floor map (not calibrated yet) nothing is shared: each camera stays as it is.

Peer data comes from the other service's /peer endpoint (X-Device-Key, this laptop only).
SIMULATION-TESTED (test_crosscam.py); real accuracy needs both cameras mounted and calibrated.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from typing import Optional

import numpy as np

GATE_M = 0.7            # feet of the same person seen by both cameras land this close (metres)
MAX_AGE_S = 0.6         # the other camera's observation is at most this old
STABLE_PASSES = 4       # the pairing holds this many passes in a row before a name moves
# Only a confirmed name is shared - the states identity.IdentityLedger really produces. (Fixed
# 2026-10-18: this set held "CONFIRMED"/"VERIFIED", which the ledger never sets, so no name ever
# crossed - the simulated scenario bench found it; the unit tests had used the made-up state.)
# Not shared: UNKNOWN, TENTATIVE, OCCLUDED, IDENTITY_UNCERTAIN, IDENTITY_CONFLICT.
SHARE_STATES = {"DOOR_CONFIRMED", "FACE_CONFIRMED", "FUSED_CONFIRMED", "REID_CONFIRMED", "CONFIRMED", "VERIFIED"}
SHARE_SOURCES = {"door", "face", "peer"}      # ...given by door or face (or carried over already)

# 2026-10-19 (lab, both cameras live):
# * A person whose box touches the bottom of the picture (feet cut off - right in front of camera 1)
#   got a wrong floor position (seen: -45 m, 148 m). Such a track has NO position now: nothing is
#   shared on a guess of where they stand. Positions outside the room are dropped the same way.
EDGE_PX = 3                                   # box bottom this close to the frame bottom = feet not seen
ROOM_M = (-1.0, 8.0, -1.0, 13.5)              # x0, x1, y0, y1: the lab floor (~6.1 x 11.6 m) with margin
# * Appearance (re-id embedding) between the two views. OBSERVE (default): logged with the position gap
#   and both cameras' names (both CONFIRMED and equal = same person, different = different people), never
#   used for a decision. ON: only once that log shows same- and different-person distances clearly apart:
#   then a pairing up to GATE_WIDE_M is allowed when the looks agree and nobody else in view comes close,
#   and clearly different looks veto a pairing even on the same spot. Never by clothes alone: the floor
#   must still roughly agree. APPEAR_* are NOT measured yet - do not set CROSSCAM_APPEARANCE=on before.
APPEARANCE = os.environ.get("CROSSCAM_APPEARANCE", "observe").lower()      # off / observe / on
GATE_WIDE_M = 1.3
APPEAR_MAX, APPEAR_MARGIN, APPEAR_VETO = 0.25, 0.10, 0.45
OBS_EVERY = 7                                 # log observations about once a second
# 2026-10-21: SAME DESK. Seated at a desk the feet are hidden (no floor position), so the floor never
# paired people there. anchors/desk_map.json (deskmap.py, owner-verified: PC boxes named by the real lab
# numbers on both cameras) links the PCs both cameras see. One person seated at PC-08 here and one
# seated at PC-08 there = a pairing candidate. Only when that desk has exactly one seated person in EACH
# view, never against the floor (both positions known and further apart than DESK_VETO_M) or a clear
# appearance veto, and through the same stability / confirmed-name / conflict rules as the floor.
DESK_SCORE = 0.5                              # below a close floor match, above nothing
DESK_VETO_M = 2.0
DESK_OVERLAP = 0.02                           # person box vs PC box, as vision.ZoneWatcher (in use)


def feet_floor(floor, box, w: int, h: int):
    """Room position of a person's feet, or None when the feet are not in the picture / off the floor."""
    if floor is None or box[1] + box[3] >= h - EDGE_PX:
        return None
    x, y = floor.feet(box, w, h)
    if not (ROOM_M[0] <= x <= ROOM_M[1] and ROOM_M[2] <= y <= ROOM_M[3]):
        return None
    return (x, y)


def desk_of(box, w: int, h: int, desks: Optional[dict]) -> Optional[str]:
    """The mapped PC (name -> 0-1 rect) this person SITS at, or None. Standing in front of a PC is not
    sitting at it (same rule as vision.ZoneWatcher: box taller than STANDING_RATIO x its width)."""
    if not desks or box[2] <= 0:
        return None
    from vision import ZoneWatcher, iou
    if box[3] / box[2] > ZoneWatcher.STANDING_RATIO:
        return None
    p = (box[0] / w, box[1] / h, box[2] / w, box[3] / h)
    best, name = DESK_OVERLAP, None
    for n, r in desks.items():
        o = iou(tuple(r), p)
        if o > best:
            best, name = o, n
    return name


def deep_of(t):
    look = getattr(t, "look", None)
    return getattr(look, "deep", None) if look is not None else None


def deep_distance(a, b) -> Optional[float]:
    """Same scale as vision.look_distance's re-id part: 0 = alike, 1 = nothing alike."""
    if a is None or b is None:
        return None
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if a.shape != b.shape:
        return None
    return float(np.clip((1.0 - float(a @ b)) / 1.2, 0.0, 1.0))


class FloorMap:
    """Picture (0-1 x, y) -> room floor (metres), from >= 4 calibrated points."""

    def __init__(self, points: list[dict]):
        import cv2
        if len(points) < 4:
            raise ValueError("a floor map needs at least 4 points")
        src = np.array([p["px"] for p in points], np.float32)
        dst = np.array([p["floor"] for p in points], np.float32)
        H, _ = cv2.findHomography(src, dst, 0)
        if H is None:
            raise ValueError("the floor points do not define a plane (three or more on one line?)")
        self.H = H

    def project(self, x: float, y: float) -> tuple[float, float]:
        v = self.H @ np.array([x, y, 1.0])
        return float(v[0] / v[2]), float(v[1] / v[2])

    def feet(self, box: tuple, w: int, h: int) -> tuple[float, float]:
        """A person box in frame pixels -> where they stand (box bottom-centre)."""
        return self.project((box[0] + box[2] / 2) / w, (box[1] + box[3]) / h)

    @classmethod
    def load(cls, folder: str, device: str) -> Optional["FloorMap"]:
        path = os.path.join(folder, f"{device}_floor.json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f)["points"])


def peer_view(tracks, floor: Optional[FloorMap], w: int, h: int, now: float, desks: Optional[dict] = None) -> dict:
    """What this camera tells the other one (served at /peer). desk = this camera's PC name."""
    out = []
    for t in tracks:
        d = deep_of(t)
        out.append({"id": t.id, "floor": feet_floor(floor, t.box, w, h), "desk": desk_of(t.box, w, h, desks),
                    "label": t.label, "name": t.name, "role": t.role, "source": t.source,
                    "state": t.identity_state, "crowded": bool(t.crowded),
                    "deep": [round(float(v), 4) for v in d] if d is not None else None})
    return {"t": now, "calibrated": floor is not None, "tracks": out}


class CrossCam:
    def __init__(self, peer_url: Optional[str], key: str, floor: Optional[FloorMap], http=None,
                 obs_path: Optional[str] = None):
        self.peer_url = peer_url.rstrip("/") if peer_url else None
        self.key = key
        self.floor = floor
        self.http = http
        self.peer: Optional[dict] = None          # last /peer answer of the other camera
        self.peer_at = 0.0
        self.streak: dict[tuple[int, int], int] = {}   # (my track, peer track) -> passes in a row
        self.notes: list[dict] = []
        self._stop = False
        self.obs_path = obs_path                  # appearance observations (jsonl) to measure APPEAR_*
        self.passes = 0
        self.desk_link: dict[str, str] = {}       # other camera's PC name -> this camera's (desk_map.json)
        self.desks: dict[str, tuple] = {}         # this camera's linked PC boxes (0-1), set every pass
        self.by_desk: set[tuple[int, int]] = set()   # this pass's pairings that came from the desk

    # ------------------------------------------------------------ polling ---
    def start(self, period_s: float = 0.25):
        if not self.peer_url:
            return
        import requests
        self.http = self.http or requests.Session()

        def loop():
            while not self._stop:
                try:
                    r = self.http.get(f"{self.peer_url}/peer", headers={"X-Device-Key": self.key}, timeout=0.5)
                    if r.status_code == 200:
                        self.peer, self.peer_at = r.json(), time.time()
                except Exception:
                    pass                           # the other camera down: this one carries on alone
                time.sleep(period_s)
        threading.Thread(target=loop, daemon=True, name="crosscam").start()

    # -------------------------------------------------------------- share ---
    def share(self, tracks, w: int, h: int, now: float, labeler) -> list[dict]:
        """Carry confirmed names over from the other camera. Returns the decisions (for /identity)."""
        from vision import assign_max
        self.notes = []
        peer = self.peer
        floor_ok = self.floor is not None and bool(peer and peer.get("calibrated"))
        desk_ok = bool(self.desk_link and self.desks)
        if (not peer or not (floor_ok or desk_ok)
                or not -1.0 <= now - float(peer.get("t", 0)) <= MAX_AGE_S):   # stale, or stamped ahead (clock step)
            self.streak.clear()
            return []
        theirs = [p for p in peer["tracks"]
                  if (floor_ok and p.get("floor")) or (desk_ok and self.desk_link.get(p.get("desk") or ""))]
        mine = list(tracks)
        if not mine or not theirs:
            self.streak.clear()
            return []
        pos = [feet_floor(self.floor, t.box, w, h) if floor_ok else None for t in mine]
        self.passes += 1
        ad = [[deep_distance(deep_of(t), p.get("deep")) for p in theirs] for t in mine]
        dist = [[math.dist(pos[i], p["floor"]) if pos[i] is not None and p.get("floor") else None for p in theirs]
                for i in range(len(mine))]
        self._observe(mine, theirs, dist, ad, now)
        # Same desk (see DESK_SCORE): my PC per track, theirs translated to my PC names; a desk counts
        # only when exactly one person sits at it in each view.
        my_desk = [desk_of(t.box, w, h, self.desks) if desk_ok else None for t in mine]
        their_desk = [self.desk_link.get(p.get("desk") or "") if desk_ok else None for p in theirs]
        alone = {d for d in set(my_desk) if d and my_desk.count(d) == 1 and their_desk.count(d) == 1}
        self.by_desk = set()
        score = []
        for i in range(len(mine)):
            row = []
            for j in range(len(theirs)):
                s = self._score(dist[i][j], ad[i], j)
                if (my_desk[i] in alone and their_desk[j] == my_desk[i]
                        and not (dist[i][j] is not None and dist[i][j] > DESK_VETO_M)
                        and not (APPEARANCE == "on" and ad[i][j] is not None and ad[i][j] > APPEAR_VETO)
                        and (s is None or s < DESK_SCORE)):
                    s = DESK_SCORE
                    self.by_desk.add((mine[i].id, theirs[j]["id"]))
                row.append(s)
            score.append(row)
        pairs = assign_max(score)
        keep = {(mine[i].id, theirs[j]["id"]) for i, j in pairs}
        self.streak = {k: self.streak.get(k, 0) + 1 for k in keep}
        held = {t.label for t in mine if t.label}
        for i, j in pairs:
            t, p = mine[i], theirs[j]
            if self.streak[(t.id, p["id"])] < STABLE_PASSES:
                continue
            if t.label and p.get("label") and t.label != p["label"]:
                # A desk GUESS here, a CONFIRMED name there (lab 2026-10-19: Ali sitting at Eng. Hemaly's
                # desk was "Eng. Hemaly ? (desk)" on camera 1 while camera 2's face said Ali, verified 97 %):
                # the confirmed name wins. Every other disagreement stays a logged conflict.
                if (t.source == "desk" and p.get("state") in SHARE_STATES and p.get("source") in SHARE_SOURCES
                        and not t.crowded and not p.get("crowded") and p["label"] not in held - {t.label}
                        and labeler._agreed(t) in (None, p["label"])):
                    old = t.label
                    labeler._give(t, {"auth_subject": p["label"], "name": p.get("name"), "role": p.get("role")},
                                  "peer", how="other camera")
                    held.discard(old)
                    held.add(p["label"])
                    self._note("CROSSCAM_OVERRIDES_DESK_GUESS", t.id, p["label"],
                               f"desk guess {old} replaced: the other camera confirmed {p['label']} on this person")
                    continue
                self._note("CROSSCAM_CONFLICT", t.id, t.label,
                           f"other camera calls this person {p['label']} - nothing changed")
                continue
            if t.label or not p.get("label"):
                continue
            if p.get("state") not in SHARE_STATES or p.get("source") not in SHARE_SOURCES:
                continue                           # only a confirmed door / face name travels
            if t.crowded or p.get("crowded"):
                continue                           # touching someone in either view: not now
            if p["label"] in held:
                continue                           # that name is on someone else here
            said = labeler._agreed(t)
            if said is not None and said != p["label"]:
                continue                           # this person's own face says someone else
            labeler._give(t, {"auth_subject": p["label"], "name": p.get("name"), "role": p.get("role")},
                          "peer", how="other camera")
            held.add(p["label"])
            how = (f"seated alone at {desk_of(t.box, w, h, self.desks)} on both cameras (other camera's track"
                   if (t.id, p["id"]) in self.by_desk else "same floor spot as the other camera's track (")
            self._note("CROSSCAM_NAME", t.id, p["label"], f"{how} {p['id']}) for {STABLE_PASSES}+ passes")
        return self.notes

    def _score(self, d, ads: list, j: int):
        """Pairing score of my track with the other camera's track j; None = cannot be the same person."""
        if d is None:
            return None                            # feet not seen: no position, no pairing
        a = ads[j]
        if APPEARANCE == "on" and a is not None and a > APPEAR_VETO:
            return None                            # clearly different people, whatever the floor says
        if d <= GATE_M:
            return 1.0 - d / GATE_M
        if APPEARANCE == "on" and d <= GATE_WIDE_M and a is not None and a <= APPEAR_MAX:
            rivals = [x for k, x in enumerate(ads) if k != j and x is not None]
            if not rivals or min(rivals) - a >= APPEAR_MARGIN:
                return 0.05 * (1.0 - a)            # below every in-gate pairing: never steals one
        return None

    def _observe(self, mine, theirs, dist, ad, now: float):
        """Log (position gap, appearance distance, both names) for pairs within 2 m - the measurement
        APPEAR_* must come from. Only names both cameras CONFIRMED count as ground truth."""
        if APPEARANCE == "off" or not self.obs_path or self.passes % OBS_EVERY:
            return
        rows = []
        for i, t in enumerate(mine):
            for j, p in enumerate(theirs):
                if dist[i][j] is None or dist[i][j] > 2.0 or ad[i][j] is None:
                    continue
                rows.append({"t": round(now, 2), "gap_m": round(dist[i][j], 3), "appear": round(ad[i][j], 4),
                             "mine": t.label, "mine_state": t.identity_state, "theirs": p.get("label"),
                             "theirs_state": p.get("state"), "crowded": bool(t.crowded or p.get("crowded"))})
        if rows:
            try:
                with open(self.obs_path, "a", encoding="utf-8") as f:
                    f.write("".join(json.dumps(r) + "\n" for r in rows))
            except OSError:
                pass

    def _note(self, kind, track_id, label, detail):
        print(f"[crosscam] {kind} track {track_id} {label or ''}: {detail}")
        self.notes.append({"kind": kind, "track_id": track_id, "label": label, "detail": detail})
