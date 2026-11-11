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
APPEARANCE = os.environ.get("CROSSCAM_APPEARANCE", "on").lower()      # off / observe / on (on since 2026-10-21)
# 2026-10-21, MEASURED from that log (396 observations, named on both cameras, <= 1.5 m, not touching):
# same person median 0.31 (5-95 % 0.14-0.73), different people median 0.79 (0.67-0.83). Good enough to break a
# near-TIE between floor pairings - Ali and Nour 0.6 m apart at the UR5e scored exactly equal both ways, so
# nobody got Nour's name - not to veto or to pair on its own (the ranges overlap). TIE_W x (0.5 - distance)
# is added to an in-gate floor score: +-0.15 at most, so a clearly closer floor match still wins.
TIE_BREAK = os.environ.get("CROSSCAM_TIE_BREAK", "on").lower() == "on"
TIE_W = 0.3
# ON (2026-10-21 lab, Ali seated at the UR5e table next to Nour): camera 1 cannot see feet behind that table -
# its floor put NOUR 0.59 m from camera 2's "USER1" (look 0.69 = a different person) and ALI 1.50 m away (look
# 0.30 = the same person). From the measured distances: a look above APPEAR_VETO (different-people 5 % = 0.67)
# vetoes a pairing even on the same spot; a look at or below APPEAR_MAX that beats every other candidate on
# both sides by APPEAR_MARGIN may pair up to GATE_WIDE_M; such a clear look also lets a name cross while the
# person touches a neighbour (SHARE_TOUCHING_IF_CLEAR) - the neighbour must look clearly different.
GATE_WIDE_M = 2.0
APPEAR_MAX, APPEAR_MARGIN, APPEAR_VETO = 0.40, 0.20, 0.65
SHARE_TOUCHING_IF_CLEAR = True
# 2026-11-03 lab: Ali and Nour in the room, no appearance measured yet - the floor alone moved Nour's name
# (confirmed by face on camera 2) onto Ali on camera 1. With 2+ people in my view a name now crosses only
# when the look was measured and sits on the same-person side (between the medians 0.31 / 0.79).
APPEAR_NAME_MAX = 0.55
ELIM_COOLDOWN_S = 2.5                         # no name by elimination this soon after two people crossed
ELIM_PASSES = 8                               # elimination holds longer than a floor pairing (STABLE_PASSES)
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

# 2026-11-10: HANDOFF. Everything above needs the other camera to see the person NOW and to place them
# (feet on the floor map, or the same desk). So a name did not cross when the feet were hidden in either view
# (standing behind a table, bending, upper body only), nor when the person had already left the other view:
# camera 1 confirmed USER1, USER1 walked on, camera 2 showed "Unknown". The handoff remembers every confirmed
# person of the other camera for HANDOFF_S (look, last floor position, time) and lets that name cross on the
# LOOK when it is clear: at most APPEAR_MAX, every rival on both sides at least APPEAR_MARGIN further (the
# measured same- / different-person distances above), held for HANDOFF_PASSES passes in a row. Never against
# the floor: with both positions known, the person must have been able to walk there in the time since.
# Same refusals as a floor pairing: touching a neighbour, a name already on someone here, an own face vote
# for someone else. off / observe (log only) / on. SIMULATION-TESTED only: measure in the lab before trusting.
HANDOFF = os.environ.get("CROSSCAM_HANDOFF", "on").lower()
HANDOFF_S = 90.0                              # a confirmed person of the other camera is remembered this long
HANDOFF_PASSES = 12                           # the look must stay clear this many passes in a row (~2 s)
WALK_MPS = 1.8                                # brisk walk: how far a person can have moved since last seen


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
        self.seen: dict[str, dict] = {}           # other camera's confirmed people, by name (handoff memory)
        self.hstreak: dict[tuple[int, str], int] = {}   # (my track, name) -> passes in a row the look was clear
        self.hsaid: set[tuple[int, str]] = set()  # handoffs already logged in observe mode

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
        self._share_live(tracks, w, h, now, labeler)
        if HANDOFF in ("on", "observe"):
            self._handoff(tracks, w, h, now, labeler)
        return self.notes

    def _handoff(self, tracks, w: int, h: int, now: float, labeler) -> None:
        """Names that the floor / desk pairing cannot carry (see HANDOFF): feet hidden, or the person has
        left the other camera's view. Runs after the live pairing and only ever names an unnamed track."""
        peer = self.peer
        if not peer or not -1.0 <= now - float(peer.get("t", 0)) <= MAX_AGE_S:
            self.hstreak.clear()                   # other camera silent: its memory is not used blind
            return
        live = set()
        for p in peer.get("tracks", []):
            if (p.get("label") and p.get("state") in SHARE_STATES and p.get("source") in SHARE_SOURCES
                    and not p.get("crowded")):
                live.add(p["label"])
                if p.get("deep") is not None:
                    old = self.seen.get(p["label"], {})
                    self.seen[p["label"]] = {"deep": p["deep"], "floor": p.get("floor") or old.get("floor"),
                                             "t": float(peer["t"]), "name": p.get("name"), "role": p.get("role")}
        self.seen = {k: v for k, v in self.seen.items() if now - v["t"] <= HANDOFF_S}
        held = {t.label for t in tracks if t.label}
        looks = {t.id: deep_of(t) for t in tracks}
        keep: dict[tuple[int, str], int] = {}
        for t in tracks:
            if t.label or t.crowded or looks[t.id] is None or not self.seen:
                continue
            d = {k: deep_distance(looks[t.id], v["deep"]) for k, v in self.seen.items()}
            d = {k: x for k, x in d.items() if x is not None}
            if not d:
                continue
            name = min(d, key=d.get)
            a, c = d[name], self.seen[name]
            if a > APPEAR_MAX or name in held:
                continue
            if any(x - a < APPEAR_MARGIN for k, x in d.items() if k != name):
                continue                           # another remembered person looks about as close
            rivals = [deep_distance(looks[o.id], c["deep"]) if looks[o.id] is not None else None
                      for o in tracks if o is not t]
            if any(x is None or x - a < APPEAR_MARGIN for x in rivals):
                continue                           # someone else here could be that person (or has no look yet)
            pos = feet_floor(self.floor, t.box, w, h) if self.floor is not None else None
            if pos is not None and c["floor"] is not None:
                reach = GATE_WIDE_M + WALK_MPS * max(0.0, now - c["t"])
                if math.dist(pos, c["floor"]) > reach:
                    continue                       # too far to have walked there since the other camera saw them
            said = labeler._agreed(t)
            if said is not None and said != name:
                continue                           # this person's own face says someone else
            keep[(t.id, name)] = self.hstreak.get((t.id, name), 0) + 1
        self.hstreak = keep
        for (tid, name), n in keep.items():
            if n < HANDOFF_PASSES:
                continue
            t, c = next(x for x in tracks if x.id == tid), self.seen[name]
            where = "seen there now" if name in live else f"last seen there {now - c['t']:.0f} s ago"
            detail = (f"clear look ({deep_distance(looks[tid], c['deep']):.2f}) of the other camera's {name}, "
                      f"{where}, for {HANDOFF_PASSES}+ passes")
            if HANDOFF != "on":
                if (tid, name) not in self.hsaid:
                    self.hsaid.add((tid, name))
                    self._note("CROSSCAM_HANDOFF_OBSERVED", tid, name, detail + " - observe mode, nothing changed")
                continue
            if t.label or name in {x.label for x in tracks if x.label}:
                continue
            labeler._give(t, {"auth_subject": name, "name": c.get("name"), "role": c.get("role")},
                          "peer", how="other camera")
            self._note("CROSSCAM_HANDOFF", tid, name, detail)

    def _share_live(self, tracks, w: int, h: int, now: float, labeler) -> list[dict]:
        """Live pairing: the other camera sees the person now, on the same floor spot or at the same desk."""
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
        clear = [[self._clear(ad, i, j) for j in range(len(theirs))] for i in range(len(mine))]
        score = []
        for i in range(len(mine)):
            row = []
            for j in range(len(theirs)):
                s = self._score(dist[i][j], ad[i], j, clear[i][j])
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
                if (t.source in ("desk", "look") and p.get("state") in SHARE_STATES and p.get("source") in SHARE_SOURCES
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
            if (t.label and t.label == p.get("label") and t.source == "look" and p.get("state") in SHARE_STATES
                    and p.get("source") in SHARE_SOURCES and not t.crowded and not p.get("crowded")
                    and labeler._agreed(t) in (None, t.label)):
                # my guess from the stored look, and the other camera CONFIRMED the same name on the same spot
                labeler._give(t, {"auth_subject": p["label"], "name": p.get("name"), "role": p.get("role")},
                              "peer", how="other camera")
                self._note("CROSSCAM_CONFIRMS_LOOK_GUESS", t.id, p["label"],
                           f"guess confirmed: the other camera's track {p['id']} holds the same name on this spot")
                continue
            if t.label or not p.get("label"):
                continue
            if p.get("state") not in SHARE_STATES or p.get("source") not in SHARE_SOURCES:
                continue                           # only a confirmed door / face name travels
            if (t.crowded or p.get("crowded")) and not (SHARE_TOUCHING_IF_CLEAR and clear[i][j]):
                continue                           # touching someone in either view: not now (unless the look is clear)
            if len(mine) > 1 and (ad[i][j] is None or ad[i][j] > APPEAR_NAME_MAX):
                continue                           # several people here: the floor alone does not name anyone
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
        self._by_elimination(mine, peer["tracks"], held, labeler, theirs, dist, ad, now)   # everyone there
        return self.notes

    def _by_elimination(self, mine, theirs, held: set, labeler, placed=(), dist=(), ad=(), now: float = 0.0) -> None:
        """Owner 2026-11-03 (lab, Ali + Nour): Ali sat at camera 2's bottom edge (feet cut = no floor position)
        and stayed Unknown on camera 1 although everyone else was named. Same head count on both cameras,
        exactly one person unnamed here, exactly one CONFIRMED name there that nobody here holds: that name is
        this person's - once it held for STABLE_PASSES passes in a row, and never against their own face."""
        free = [t for t in mine if not t.label]
        names = {p["label"] for p in theirs if p.get("label") and p.get("state") in SHARE_STATES
                 and p.get("source") in SHARE_SOURCES} - held
        streak = getattr(self, "elim_streak", {})
        # 2+ people: the others' names already prove the two views hold the same people (one person per view
        # can be two different people in two corners); crowded = not now, as for the floor.
        if not (len(mine) == len(theirs) >= 2 and len(free) == 1 and len(names) == 1 and not free[0].crowded):
            self.elim_streak = {}
            return
        t, name = free[0], next(iter(names))
        said = labeler._agreed(t)
        if said is not None and said != name:
            self.elim_streak = {}
            return
        # Gemini ACT-06 (2026-11-03, verified): equal head counts can be DIFFERENT people in each camera's blind
        # spot. So: the names held here must be exactly the other names there; a measured look must not say
        # "different person"; two known floor positions must not be far apart; not right after a crossing.
        others_there = {p["label"] for p in theirs if p.get("label")} - {name}
        if {x.label for x in mine if x.label} != others_there:
            self.elim_streak = {}
            return
        i = mine.index(t)
        j = next((k for k, p in enumerate(placed) if p.get("label") == name), None)
        d = dist[i][j] if j is not None and i < len(dist) and j < len(dist[i]) else None
        # 2026-11-11 (closure audit P1-A): the head count is not evidence. With no measured look this rule named
        # the last unnamed person from the count alone - a visitor in one camera's blind spot would have taken
        # the name. The look is now measured against the named person there directly (they need no floor
        # position for that) and must be at most APPEAR_NAME_MAX; without a look on both sides nobody is named.
        there = next((p for p in theirs if p.get("label") == name), None)
        a = deep_distance(deep_of(t), there.get("deep")) if there is not None else None
        if a is None:
            self.elim_streak = {}
            said_before = getattr(self, "elim_said", set())
            if (t.id, name) not in said_before:
                self.elim_said = said_before | {(t.id, name)}
                self._note("CROSSCAM_AMBIGUOUS", t.id, None,
                           f"one unnamed person here and one free name there ({name}), but no measured look - not named")
            return
        if a > APPEAR_NAME_MAX or (d is not None and d > GATE_WIDE_M) \
                or now - getattr(t, "separated_at", -1e9) < ELIM_COOLDOWN_S:
            self.elim_streak = {}
            return
        n = streak.get((t.id, name), 0) + 1
        self.elim_streak = {(t.id, name): n}
        if n < ELIM_PASSES:
            return
        p = there
        labeler._give(t, {"auth_subject": name, "name": p.get("name"), "role": p.get("role")}, "peer", how="other camera")
        held.add(name)
        self._note("CROSSCAM_NAME", t.id, name, f"the only unnamed person here, the only name there not on anyone here, "
                                                f"and the look agrees ({a:.2f}); {len(mine)} people on both cameras, "
                                                f"for {ELIM_PASSES}+ passes")

    @staticmethod
    def _clear(ad: list, i: int, j: int) -> bool:
        """My track i and their track j look clearly alike: at most APPEAR_MAX, and every other candidate on
        BOTH sides (my other tracks vs j, their other tracks vs i) at least APPEAR_MARGIN further."""
        a = ad[i][j]
        if APPEARANCE != "on" or a is None or a > APPEAR_MAX:
            return False
        rivals = [x for k, x in enumerate(ad[i]) if k != j] + [ad[l][j] for l in range(len(ad)) if l != i]
        return all(x is None or x - a >= APPEAR_MARGIN for x in rivals)

    def _score(self, d, ads: list, j: int, clear: bool = False):
        """Pairing score of my track with the other camera's track j; None = cannot be the same person."""
        if d is None:
            return None                            # feet not seen: no position, no pairing
        a = ads[j]
        if APPEARANCE == "on" and a is not None and a > APPEAR_VETO:
            return None                            # clearly different people, whatever the floor says
        if d <= GATE_M:
            s = 1.0 - d / GATE_M
            if TIE_BREAK and a is not None:
                s = max(0.01, s + TIE_W * (0.5 - a))      # looks alike: a little more likely the same person
            return s
        if clear and d <= GATE_WIDE_M:
            return 0.05 * (1.0 - a)                # below every in-gate pairing: never steals one
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
