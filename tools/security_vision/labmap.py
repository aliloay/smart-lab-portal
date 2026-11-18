"""One lab, one number per person, on both cameras (2026-11-17, owner at the lab).

Before: each camera service numbered the people it saw itself ("Person 65" on camera 1, "Person 88" on camera 2 for
the same man), a person who walked out and came back got a new number, and the Security page listed everyone once
per camera. Now both services on this laptop share ONE register (a small JSON file, locked while it is read and
written), and every unnamed person gets a LAB number that both cameras use:

  1. SAME PERSON NOW ON THE OTHER CAMERA: crosscam.py pairs the two views (same floor spot or the same desk, look
     agreeing, held STABLE_PASSES passes - its existing, lab-tested rules). A paired person takes the lower of the
     two lab numbers on both sides, so the two cameras converge on one number.
  2. CAME BACK: a new person whose look (re-id embedding) clearly matches someone who LEFT less than GALLERY_S ago
     gets that person's old number back - never a number that is on someone in view right now (either camera).
     "Clearly" = the limits crosscam measured in the lab (2026-10-21, 396 observations): distance at most
     MATCH_MAX (same person median 0.31, different people 5 % = 0.67) and every other remembered person at least
     MATCH_MARGIN further. Otherwise a new number. Clothes colour or skin tone are NOT used: the embedding already
     carries body shape and clothing, and skin tone is not a trait this system tracks.
  3. OTHERWISE a new number: the lowest one free in the shared register (so the two cameras never hand out the same one).

A name (door / face / confirmed hand-over) always wins over a number; named people keep their name.
The look is averaged over the person's time in view (EMA) so one bad frame does not move them.
UNIT-TESTED (test_labmap.py) and run on both live cameras; how often a return is recognised depends on how alike
the person looks on the way back (turned away, coat on) - measured at the lab, not claimed.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import numpy as np

GALLERY_S = 30 * 60          # a person who left is remembered this long (seconds)
MATCH_MAX = 0.40             # look distance to take a remembered number back (crosscam APPEAR_MAX, measured)
MATCH_MARGIN = 0.20          # ... and every other candidate at least this much further (crosscam APPEAR_MARGIN)
PRESENT_S = 3.0              # a number seen this recently (either camera) is "in view": never handed to someone else
EMA = 0.15                   # look averaging per update
WRITE_EVERY_S = 1.0          # register updates at most once a second per camera
LOOK_WAIT_S = 1.5            # a new person without a look yet waits this long before a new number is given
LOCK_STALE_S = 5.0           # a lock file older than this was left by a crashed process
# A number crosses between cameras only on a SOLID pairing (lab 2026-11-17, first live run: short-lived pairings
# around the busy UR5e table spread "Person 1" to everyone, and the lower number never went back):
LINK_PASSES = 12             # paired this many passes in a row (~2 s; crosscam names need STABLE_PASSES = 4)
LINK_LOOK_MAX = 0.55
# Names that survive a track break (bending down, passing behind someone): door, face, staff-confirmed, carried over
KEEP_NAME_SOURCES = {"door", "face", "operator", "peer"}
# Second tier for a CONFIRMED name only (lab 17 Nov: Ali and Nour came back turned / from another angle and the
# strict MATCH_MAX refused): when exactly ONE confirmed person left in the last NAME_BACK_S, a new person whose look
# is at most NAME_BACK_MAX (between the measured medians 0.31 same / 0.79 different) gets that name back.
NAME_BACK_S = 120.0
NAME_BACK_MAX = 0.55         # looks agree (crosscam APPEAR_NAME_MAX, between the measured medians 0.31 / 0.79)
LATE_PASSES = 2              # an already-numbered unnamed person: this many register checks (~1 s apart) in a row


def _dist(a, b) -> Optional[float]:
    """Same scale as crosscam.deep_distance: 0 = alike, 1 = nothing alike."""
    if a is None or b is None:
        return None
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if a.shape != b.shape:
        return None
    return float(np.clip((1.0 - float(a @ b)) / 1.2, 0.0, 1.0))


def _norm(v):
    v = np.asarray(v, np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class Register:
    """The shared file: {"next": int, "people": {no: {"deep": [...], "seen": t, "cam": dev, "first": t}}}."""

    def __init__(self, path: str):
        self.path = path
        self.lock_path = path + ".lock"

    def _lock(self) -> bool:
        for _ in range(50):                                  # up to ~0.5 s
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return True
            except (FileExistsError, PermissionError):
                # PermissionError: Windows refuses to create a file the other camera process is deleting right now
                # ("delete pending") - the lock is being released, so wait and retry like a held lock (2026-11-18).
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > LOCK_STALE_S:
                        os.remove(self.lock_path)            # left behind by a crashed process
                        continue
                except OSError:
                    pass
                time.sleep(0.01)
        return False

    def _unlock(self):
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("people"), dict):
                return d
        except (OSError, ValueError):
            pass
        return {"next": 1, "people": {}}

    def update(self, fn):
        """Read-modify-write under the lock; fn(data) changes data in place and returns a result."""
        locked = self._lock()
        try:
            d = self.read()
            out = fn(d)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f)
            os.replace(tmp, self.path)
            return out
        finally:
            if locked:
                self._unlock()


class LabNumbers:
    """Per camera service: gives every unnamed track a lab number (t.lab_no) using the shared Register."""

    def __init__(self, path: str, device: str):
        self.reg = Register(path)
        self.device = device
        self.last_write = 0.0
        self.looks: dict[int, np.ndarray] = {}               # track id -> averaged look (this camera)
        self.born: dict[int, float] = {}                     # track id -> first time without a number
        self.notes: list[dict] = []
        self.late: dict[int, tuple] = {}                     # unnamed numbered track -> (number it looks like, checks)
        self.lstreak: dict[tuple[int, int], int] = {}        # (my track, their lab number) -> passes the look was clear

    def _look(self, t) -> Optional[np.ndarray]:
        look = getattr(t, "look", None)
        deep = getattr(look, "deep", None) if look is not None else None
        if deep is None:
            return self.looks.get(t.id)
        v = _norm(deep)
        old = self.looks.get(t.id)
        self.looks[t.id] = v if old is None else _norm((1 - EMA) * old + EMA * v)
        return self.looks[t.id]

    def assign(self, tracks, links: dict, now: Optional[float] = None, peer_tracks=None) -> list[dict]:
        """links: my track id -> the other camera's paired track (dict with "lab_no"), from crosscam.
        peer_tracks: the other camera's current tracks (crosscam's last /peer answer, only when fresh)."""
        now = time.time() if now is None else now
        self.notes = []
        self.restore = []                                    # (track, confirmed name) to give back - applied by the caller
        alive = {t.id for t in tracks}
        self.looks = {k: v for k, v in self.looks.items() if k in alive}
        self.born = {k: v for k, v in self.born.items() if k in alive}
        looks = {t.id: self._look(t) for t in tracks}
        # 0) one number per person in this view: a duplicate (never wanted) is cleared and renumbered below
        seen_no: dict[int, object] = {}
        for t in sorted(tracks, key=lambda x: x.id):
            if t.lab_no is None:
                continue
            if t.lab_no in seen_no:
                self._note("LAB_NUMBER_DUPLICATE", t, f"Person {t.lab_no} is already on track {seen_no[t.lab_no].id} here - renumbered")
                t.lab_no = None
            else:
                seen_no[t.lab_no] = t
        # 1) solidly paired with the other camera: both take the lower number (never one held by someone else here,
        # and never across two tracks that already carry different confirmed names)
        for t in tracks:
            p = links.get(t.id)
            theirs = p.get("lab_no") if p else None
            same_or_unnamed = not (t.label and p and p.get("label") and t.label != p.get("label"))
            solid = (bool(p) and same_or_unnamed and p.get("_passes", LINK_PASSES) >= LINK_PASSES
                     and not p.get("_crowded") and not getattr(t, "crowded", False)
                     and (p.get("_look") is None or p["_look"] <= LINK_LOOK_MAX))
            held = {o.lab_no for o in tracks if o is not t and o.lab_no is not None}
            if solid and theirs and theirs not in held and (t.lab_no is None or theirs < t.lab_no):
                if t.lab_no is not None:
                    self._note("LAB_NUMBER_MERGED", t, f"Person {t.lab_no} is Person {theirs} on the other camera")
                t.lab_no = theirs
        # 1b) same person by LOOK alone (seated: feet hidden, and a desk only one camera sees - lab 2026-11-17, the
        # owner at PC-01 was Person 17 on camera 1 and Person 13 on camera 2). Only a CLEAR look, the rule crosscam
        # uses for names (at most MATCH_MAX, every other person on BOTH cameras at least MATCH_MARGIN further),
        # held LINK_PASSES passes in a row, never while touching someone, never onto a number held here.
        keep: dict[tuple[int, int], int] = {}
        theirs_all = [p for p in (peer_tracks or []) if p.get("lab_no") and p.get("deep") is not None]
        for t in tracks:
            lk = looks.get(t.id)
            if lk is None or getattr(t, "crowded", False) or not theirs_all:
                continue
            d = [(_dist(lk, p["deep"]), p) for p in theirs_all]
            d = [(x, p) for x, p in d if x is not None]
            if not d:
                continue
            a, best = min(d, key=lambda z: z[0])
            if a > MATCH_MAX or best.get("crowded") or best["lab_no"] == t.lab_no:
                continue
            if t.label and best.get("label") and t.label != best.get("label"):
                continue                                     # known different people: never merge numbers
            if any(x - a < MATCH_MARGIN for x, p in d if p is not best):
                continue                                     # someone else there looks about as close
            rivals = [_dist(looks.get(o.id), best["deep"]) for o in tracks if o is not t]
            if any(x is None or x - a < MATCH_MARGIN for x in rivals):
                continue                                     # someone else here could be that person
            k = (t.id, best["lab_no"])
            keep[k] = self.lstreak.get(k, 0) + 1
            held = {o.lab_no for o in tracks if o is not t and o.lab_no is not None}
            if keep[k] >= LINK_PASSES and best["lab_no"] not in held and (t.lab_no is None or best["lab_no"] < t.lab_no):
                if t.lab_no is not None:
                    self._note("LAB_NUMBER_MERGED", t, f"Person {t.lab_no} is Person {best['lab_no']} on the other "
                                                       f"camera (clear look {a:.2f}, {LINK_PASSES}+ passes)")
                t.lab_no = best["lab_no"]
        self.lstreak = keep
        # Named people get a number too (lab 2026-11-17: Nour named on camera 2, "Unknown" on camera 1 - the
        # number links the two boxes; the NAME is still what is shown). Only the look gallery skips named people.
        need = [t for t in tracks if t.lab_no is None]
        if not need and now - self.last_write < WRITE_EVERY_S:
            return self.notes
        for t in need:
            self.born.setdefault(t.id, now)
        mine_now = {t.lab_no for t in tracks if t.lab_no is not None}

        def work(d):
            people = d["people"]
            for k in [k for k, v in people.items() if now - v.get("seen", 0) > GALLERY_S]:
                del people[k]                                # forgotten after GALLERY_S
            # numbers in view right now on either camera: never handed to a new unnamed person
            busy = {int(k) for k, v in people.items() if now - v.get("seen", 0) <= PRESENT_S} | mine_now
            # 2026-11-18 lab (Nour walked to Hemaly's desk and back: "Unknown" ~95 s): a name came back only to a NEW
            # track. An unnamed person who already has a number is re-checked too - same strict rule as a new one
            # (exactly one confirmed person missing, look within NAME_BACK_MAX), held LATE_PASSES checks in a row.
            held_labels = {o.label for o in tracks if o.label}
            late = {}
            for t in tracks:
                lk = looks.get(t.id)
                if t.label or t.lab_no is None or lk is None or getattr(t, "crowded", False):
                    continue
                if (people.get(str(t.lab_no)) or {}).get("who"):
                    continue                                 # its own number carries a name: handled below
                k = self._confirmed_back(people, busy - {t.lab_no}, lk, now, held_labels)
                if k is None:
                    continue
                late[t.id] = (k, self.late.get(t.id, (None, 0))[1] + 1 if self.late.get(t.id, (None,))[0] == k else 1)
                if late[t.id][1] >= LATE_PASSES and int(k) not in mine_now:
                    w = people[str(k)]["who"]
                    self._note("LAB_NUMBER_BACK", t, f"Person {t.lab_no} is Person {k} again (same look, "
                                                     f"{LATE_PASSES}+ checks) - confirmed name given back")
                    self.restore.append((t, w))
                    t.lab_no = int(k)
                    busy.add(int(k))
                    mine_now.add(int(k))
                    held_labels.add(w["auth_subject"])
                    late.pop(t.id, None)
            self.late = late
            for t in need:
                lk = looks[t.id]
                # If this track already has a confirmed identity stored in the register, reuse its lab number first
                no = None
                if t.label and getattr(t, "source", None) in KEEP_NAME_SOURCES:
                    for k, v in people.items():
                        if int(k) not in mine_now and (v.get("who") or {}).get("auth_subject") == t.label:
                            no = int(k)
                            break
                if no is None and lk is None and now - self.born[t.id] < LOOK_WAIT_S:
                    continue                                 # no look yet: wait a moment before a new number
                if no is None and lk is not None:
                    no = self._returning(people, busy, lk)
                if no is None and lk is not None and not t.label:
                    no = self._confirmed_back(people, busy, lk, now, {o.label for o in tracks if o.label})
                if no is not None and not t.label and people[str(no)].get("who"):
                    w = people[str(no)]["who"]
                    held = {o.label for o in tracks if o.label}
                    if w["auth_subject"] not in held:
                        self.restore.append((t, w))
                if no is not None:
                    self._note("LAB_NUMBER_BACK", t, f"came back: same look as Person {no} "
                                                     f"(left {now - people[str(no)]['seen']:.0f} s ago)")
                else:
                    # 2026-11-18 (lab: "Person 724"): the lowest number nobody holds - not in the register (people
                    # stay there GALLERY_S after leaving, so a number is never reused while it may come back) and
                    # not in view - instead of a counter that climbs across restarts.
                    no = 1
                    while str(no) in people or no in busy:
                        no += 1
                    d["next"] = max(int(d.get("next", 1)), no + 1)
                t.lab_no = no
                busy.add(no)
            for t in tracks:                                 # refresh everyone with a number: look, last seen
                if t.lab_no is None:
                    continue
                e = people.setdefault(str(t.lab_no), {"first": now})
                if t.label and getattr(t, "source", None) in KEEP_NAME_SOURCES:
                    e["who"] = {"auth_subject": t.label, "name": t.name, "role": t.role, "source": t.source}
                who = (e.get("who") or {}).get("auth_subject")
                if who and t.label != who:
                    # 2026-11-18 lab: the owner sat at Hemaly's desk and was shown as Hemaly (desk guess); his track
                    # kept Hemaly's number, so the number's stored look slowly became HIS look and Hemaly's
                    # confirmed name later "came back" to him at PC-13. A number that carries a confirmed name learns
                    # its look (and stays "seen") only from that same named person.
                    continue
                lk = looks[t.id]
                if lk is not None:
                    old = e.get("deep")
                    e["deep"] = [round(float(x), 4) for x in
                                 (lk if old is None or len(old) != len(lk) else _norm((1 - EMA) * np.asarray(old) + EMA * lk))]
                e["seen"], e["cam"] = now, self.device
            # a track whose number (from the other camera / a merge) already carries a confirmed name gets it
            held = {o.label for o in tracks if o.label}
            queued = {w["auth_subject"] for _, w in self.restore}
            for t in tracks:
                if t.label or t.lab_no is None or any(t is x for x, _ in self.restore):
                    continue
                w = (people.get(str(t.lab_no)) or {}).get("who")
                if w and w["auth_subject"] not in held and w["auth_subject"] not in queued:
                    self.restore.append((t, w))
                    queued.add(w["auth_subject"])
            return None

        self.reg.update(work)
        self.last_write = now
        return self.notes

    @staticmethod
    def _confirmed_back(people: dict, busy: set, look, now: float, held: set) -> Optional[int]:
        gone = {int(k): v for k, v in people.items() if int(k) not in busy and v.get("who")
                and v["who"]["auth_subject"] not in held and now - v.get("seen", 0) <= NAME_BACK_S}
        if len(gone) != 1:
            return None                                      # none, or two confirmed people left: no guess
        k, v = next(iter(gone.items()))
        d = _dist(look, v.get("deep"))
        return k if d is not None and d <= NAME_BACK_MAX else None

    @staticmethod
    def _returning(people: dict, busy: set, look) -> Optional[int]:
        cands = {int(k): _dist(look, v.get("deep")) for k, v in people.items() if int(k) not in busy}
        cands = {k: v for k, v in cands.items() if v is not None}
        if not cands:
            return None
        best = min(cands, key=cands.get)
        if cands[best] > MATCH_MAX:
            return None
        if any(v - cands[best] < MATCH_MARGIN for k, v in cands.items() if k != best):
            return None                                      # two remembered people look about as close: new number
        return best

    def _note(self, kind, t, detail):
        print(f"[labmap] {kind} track {t.id}: {detail}")
        self.notes.append({"kind": kind, "track_id": t.id, "label": f"Person {t.lab_no}", "detail": detail})
