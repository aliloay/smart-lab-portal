"""
Identity regression scenarios - SIMULATED, never physical evidence (2026-10-18).

People are generated with ground truth (boxes, looks, door entries, face matches) and run through
the SAME Tracker / Labeler / CrossCam the camera service uses; the result is scored. It shows what the
rules do in the defined situations - not how well the detector or the re-ID model see real people.

    py scenario_bench.py            -> table, recordings/scenario_bench_<stamp>.json + .md
                                       (numbers only: no frames, no names of real people)

Metrics per scenario (MOT-style, on ground truth):
  id_switches     a person's track id changes between matched frames
  false_names     matched frames where a track shows a name that is NOT that person's   (must be 0)
  name_switches   a person's shown name changes from one name to another               (must be 0)
  false_merges    tracks that covered two different people
  fragments       extra track ids per person (track splits)
  idf1            identity F1: optimal one-to-one person <-> track over the whole run
  named_share     share of a named person's matched frames that show their correct name
                  (the cost of staying Unknown when unsure)
  review          PERSON_IDENTITY_REVIEW / _CONFLICT events raised
Synthetic looks: same person cosine ~0.75-0.9 (body model), colours with noise; different people
cosine ~0 (or ~0.5 for "similar clothes"). Detection misses at random (default 4 %).
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field

import numpy as np

from crosscam import CrossCam, FloorMap, peer_view
from vision import Labeler, Look, Tracker, assign_max, iou, upright

FPS = 7.0
DT = 1.0 / FPS
W, H = 960, 540
DOOR = (40, 150, 60, 230)                       # door box (left wall) in the 960x540 frame
DIM = 64


def _hist(rng, conc=1.0):
    return np.concatenate([rng.dirichlet(np.full(16, conc)) for _ in range(3)]).astype(np.float32)


def _unit(v):
    return (v / np.linalg.norm(v)).astype(np.float32)


@dataclass
class Person:
    pid: int
    label: str | None                            # auth_subject if they badge in, None for a stranger
    seed: int
    similar_to: "Person | None" = None
    color: np.ndarray = None
    color_low: np.ndarray = None                 # how the colours look crouching / lying
    deep: np.ndarray = None

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        if self.similar_to is not None:          # similar clothes: same colours, related body
            self.color = self.similar_to.color.copy()
            self.deep = _unit(0.5 * self.similar_to.deep + 0.87 * _unit(rng.normal(size=DIM)))
        else:
            self.color, self.deep = _hist(rng), _unit(rng.normal(size=DIM))
        self.color_low = _hist(rng)

    def look(self, rng, box, light=1.0, deep_noise=0.10):
        c = self.color if upright(box) else self.color_low
        c = 0.85 * c + 0.15 * _hist(rng, 2.0)
        if light != 1.0:                         # lighting: colours wash towards grey / dark bins
            grey = np.tile(np.r_[np.zeros(12), [0.6, 0.3, 0.1, 0.0]], 3).astype(np.float32)
            c = light * c + (1 - light) * grey
        d = self.deep + rng.normal(0, deep_noise, DIM).astype(np.float32)
        if not upright(box):
            d = d + rng.normal(0, deep_noise * 1.5, DIM).astype(np.float32)
        return Look(c.astype(np.float32), _unit(d))


@dataclass
class Frame:
    t: float
    people: dict                                 # pid -> box (visible to the camera)
    hidden: set = field(default_factory=set)     # pids in the scene but occluded / out of view


def box_at(x, y_feet, h=250.0, ratio=0.4):
    w = h * ratio
    return (x - w / 2, y_feet - h, w, h)


def walk(p0, p1, t0, t1, t, h=250.0, ratio=0.4):
    a = min(1.0, max(0.0, (t - t0) / max(t1 - t0, 1e-6)))
    return box_at(p0[0] + a * (p1[0] - p0[0]), p0[1] + a * (p1[1] - p0[1]), h, ratio)


# ------------------------------------------------------------------ scenarios ---
# Each returns (frames, people, entries, faces) - faces: {pid: (from_t, every_s)} = the face server
# would match that person from then on (a clear frontal view), entries: door grants (auth_subject, t).
def sc_one_entry():
    a = Person(1, "U1", 11)
    fr = [Frame(t, {1: walk((90, 380), (500, 420), 2.0, 8.0, t)} if t >= 2.0 else {}) for t in _ts(20)]
    return fr, [a], [("U1", 1.0)], {}


def sc_two_enter_together_one_badge():
    a, b = Person(1, "U1", 11), Person(2, None, 22)
    fr = [Frame(t, {**({1: walk((90, 380), (520, 430), 2.0, 8.0, t)} if t >= 2.0 else {}),
                    **({2: walk((80, 375), (300, 470), 2.6, 8.0, t)} if t >= 2.6 else {})}) for t in _ts(20)]
    return fr, [a, b], [("U1", 1.0)], {}


def sc_two_enter_together_two_badges_then_faces():
    a, b = Person(1, "U1", 11), Person(2, "U2", 22)
    fr = [Frame(t, {**({1: walk((90, 380), (520, 430), 2.0, 8.0, t)} if t >= 2.0 else {}),
                    **({2: walk((80, 375), (300, 470), 2.6, 8.0, t)} if t >= 2.6 else {})}) for t in _ts(30)]
    return fr, [a, b], [("U1", 1.0), ("U2", 1.4)], {1: (12.0, 1.5), 2: (14.0, 1.5)}


def _named_pair(seconds, motion, similar=False, light_at=None):
    a = Person(1, "U1", 11)
    b = Person(2, "U2", 22, similar_to=a if similar else None)
    pre = 12.0                                   # each enters alone first and is named by the door
    def at(t):
        if t < pre:
            ppl = {}
            if t >= 1.0:
                ppl[1] = walk((90, 380), (300, 420), 1.0, 5.0, t)
            if t >= 6.5:
                ppl[2] = walk((90, 380), (650, 420), 6.5, 11.0, t)
            return ppl
        return motion(t - pre)
    fr = [Frame(t, at(t)) for t in _ts(pre + seconds)]
    return fr, [a, b], [("U1", 0.5), ("U2", 6.0)], {}


def sc_side_by_side():
    return _named_pair(60, lambda s: {1: box_at(440 + 3 * math.sin(s), 420), 2: box_at(545 + 3 * math.cos(s), 422)})


def sc_crossing():
    def m(s):
        k = (s % 8.0) / 8.0                     # 4 crossings: they swap sides and back
        x1 = 300 + 350 * (0.5 - 0.5 * math.cos(2 * math.pi * k))
        x2 = 650 - 350 * (0.5 - 0.5 * math.cos(2 * math.pi * k))
        return {1: box_at(x1, 420), 2: box_at(x2, 426)}
    return _named_pair(32, m)


def sc_crossing_similar_clothes():
    fr, ppl, ent, faces = sc_crossing()
    a = ppl[0]
    return fr, [a, Person(2, "U2", 22, similar_to=a)], ent, faces


def sc_posture():
    a = Person(1, "U1", 11)
    def at(t):
        if t < 1.0:
            return {}
        if t < 5.0:
            return {1: walk((90, 380), (450, 420), 1.0, 5.0, t)}
        s = t - 5.0                              # stand, sit, bend, crouch, lie, stand up - in place
        seq = [(4, 250, 0.4), (4, 175, 0.6), (3, 190, 0.75), (3, 150, 0.9), (5, 100, 2.4), (3, 150, 0.9), (6, 250, 0.4)]
        acc = 0.0
        for dur, h, r in seq:
            if s < acc + dur:
                return {1: box_at(450, 420, h, r)}
            acc += dur
        return {1: box_at(450, 420)}
    return [Frame(t, at(t)) for t in _ts(35)], [a], [("U1", 0.5)], {}


def sc_occlusion():
    fr, ppl, ent, faces = _named_pair(30, lambda s: {
        1: box_at(250 + 18 * s if s < 20 else 610, 420), 2: box_at(700, 425)})
    for f in fr:                                  # U1 walks behind a robot / pillar for 1.5 s
        s = f.t - 12.0
        if 6.0 <= s < 7.5 and 1 in f.people:
            del f.people[1]
            f.hidden.add(1)
    return fr, ppl, ent, faces


def sc_long_occlusion():
    fr, ppl, ent, faces = sc_occlusion()
    for f in fr:
        s = f.t - 12.0
        if 7.5 <= s < 10.0 and 1 in f.people:     # 4 s hidden in total: the track ends
            del f.people[1]
            f.hidden.add(1)
    return fr, ppl, ent, faces


def _hide(fr, pid, s0, s1, pre=12.0):
    for f in fr:
        if s0 <= f.t - pre < s1 and pid in f.people:
            del f.people[pid]
            f.hidden.add(pid)
    return fr


def sc_dead_zone_25s():
    """2026-11-11 (owner: "keep my label when I stand in a dead zone"): U1 stands behind the pillar 25 s, then
    steps out at the same place; U2 stays in view the whole time."""
    fr, ppl, ent, faces = _named_pair(50, lambda s: {1: box_at(250 + 18 * s if s < 10 else 430, 420),
                                                     2: box_at(760, 425)})
    return _hide(fr, 1, 10.0, 35.0), ppl, ent, faces


def sc_dead_zone_25s_lookalike():
    """Same, but U2 wears similar clothes and walks to the spot where U1 vanished while U1 is hidden: U2 must
    never be shown as U1 (a wrong name is worse than none)."""
    def m(s):
        b2 = box_at(760, 425) if s < 14 else walk((760, 425), (470, 420), 14, 20, s) if s < 30 else \
            walk((470, 420), (780, 425), 30, 34, s)
        return {1: box_at(250 + 18 * s if s < 10 else 430, 420), 2: b2}
    fr, ppl, ent, faces = _named_pair(50, m, similar=True)
    return _hide(fr, 1, 10.0, 35.0), ppl, ent, faces


def sc_leave_and_return():
    """U1 leaves the view (still inside the lab by the door records) for 3 minutes and comes back."""
    fr, ppl, ent, faces = _named_pair(220, lambda s: {1: box_at(250 + 18 * s if s < 12 else 470, 420),
                                                      2: box_at(760, 425)})
    return _hide(fr, 1, 12.0, 192.0), ppl, ent, faces


def sc_rapid():
    def m(s):                                    # running, sharp turns every 1.2 s
        seg = int(s / 1.2)
        k = (s % 1.2) / 1.2
        xs = [250, 700, 300, 680, 260, 720, 320, 650]
        x0, x1 = xs[seg % len(xs)], xs[(seg + 1) % len(xs)]
        return {1: box_at(x0 + k * (x1 - x0), 420 + 25 * math.sin(3 * s)), 2: box_at(820, 430)}
    return _named_pair(20, m)


def sc_disconnect():
    fr, ppl, ent, faces = _named_pair(30, lambda s: {1: box_at(420, 420), 2: box_at(620, 425)})
    return [f for f in fr if not (20.0 <= f.t < 30.0)], ppl, ent, faces    # camera off for 10 s


def sc_lighting():
    return _named_pair(30, lambda s: {1: box_at(420 + 40 * math.sin(s / 3), 420), 2: box_at(640, 425)}) + ("light",)


SCENARIOS = {
    "01 one person enters": sc_one_entry,
    "02 two enter together, one badge": sc_two_enter_together_one_badge,
    "02b two enter together, two badges, faces later": sc_two_enter_together_two_badges_then_faces,
    "03 two side by side 60 s": sc_side_by_side,
    "04 two cross 4x": sc_crossing,
    "04b two cross 4x, similar clothes": sc_crossing_similar_clothes,
    "06 sit / bend / crouch / lie / stand": sc_posture,
    "07 hidden 1.5 s, reappears": sc_occlusion,
    "07b hidden 4 s, reappears": sc_long_occlusion,
    "07c dead zone 25 s": sc_dead_zone_25s,
    "07d dead zone 25 s, look-alike walks there": sc_dead_zone_25s_lookalike,
    "11 leaves view 3 min, returns": sc_leave_and_return,
    "08 running, sharp turns": sc_rapid,
    "09 camera off 10 s": sc_disconnect,
    "10 lighting drops to 55 %": sc_lighting,
}


def _ts(seconds):
    return [round(i * DT, 4) for i in range(int(seconds * FPS))]


# --------------------------------------------------------------------- runner ---
def run(name, fn, seed=5, miss=0.04, deep_noise=0.10):
    rng = np.random.default_rng(seed)
    out = fn()
    light = len(out) == 5 and out[4] == "light"
    frames, people, entries, faces = out[:4]
    by_pid = {p.pid: p for p in people}
    tr, lab = Tracker(), Labeler()
    occ_all = [{"auth_subject": s, "name": s, "role": "STUDENT", "entered_at": t} for s, t in entries]
    last_face = {}
    mapping: dict = {}
    rows = []                                    # per frame: [(pid, track id or None, name)]
    review = 0
    for f in frames:
        lt = 0.55 if (light and f.t >= 22.0) else 1.0
        dets, gt = [], []
        for pid, b in f.people.items():
            if rng.random() < miss:
                continue
            nb = (b[0] + rng.normal(0, 2), b[1] + rng.normal(0, 2), b[2] * (1 + rng.normal(0, 0.02)),
                  b[3] * (1 + rng.normal(0, 0.02)))
            dets.append((nb, by_pid[pid].look(rng, nb, lt, deep_noise)))
        tracks = tr.update([d[0] for d in dets], f.t, [d[1] for d in dets])
        occ = [o for o in occ_all if o["entered_at"] <= f.t]
        # face server: a person whose clear face is visible gets a vote on the track holding them
        for pid, (t_from, every) in faces.items():
            if f.t < t_from or pid not in f.people or f.t - last_face.get(pid, -1e9) < every:
                continue
            tb = _match_one(f.people[pid], tracks)
            if tb is not None and not tb.crowded and by_pid[pid].label:
                lab.face_vote(tb.id, by_pid[pid].label, f.t, 0.62)
                last_face[pid] = f.t
        lab.assign(tracks, occ, DOOR, f.t)
        review += sum(1 for e in lab.events if e.kind in ("PERSON_IDENTITY_REVIEW", "PERSON_IDENTITY_CONFLICT"))
        rows.append(_match_frame(f, tracks, mapping))
    return score(name, rows, by_pid, review)


def _match_one(box, tracks):
    best = max(tracks, key=lambda t: iou(box, t.box), default=None)
    return best if best is not None and iou(box, best.box) >= 0.5 else None


def _match_frame(f, tracks, prev=None):
    """CLEAR-MOT matching: last frame's person <-> track pairs are KEPT while still valid (IoU >= 0.5),
    the rest by an optimal assignment. Without this, two people whose boxes coincide for a frame
    (one right behind the other) were "switched" by the scorer, not by the tracker."""
    prev = prev if prev is not None else {}
    by_id = {t.id: t for t in tracks}
    keep = {p: tid for p, tid in prev.items()
            if p in f.people and tid in by_id and iou(f.people[p], by_id[tid].box) >= 0.5}
    if len(set(keep.values())) != len(keep):
        keep = {}
    pids = [p for p in f.people if p not in keep]
    rest = [t for t in tracks if t.id not in keep.values()]
    sc = [[(v if (v := iou(f.people[p], t.box)) >= 0.5 else None) for t in rest] for p in pids]
    pairs = dict(assign_max(sc)) if pids and rest else {}
    out = {p: by_id[tid] for p, tid in keep.items()}
    out.update({p: rest[pairs[i]] for i, p in enumerate(pids) if i in pairs})
    rows = [(p, out[p].id if p in out else None, out[p].label if p in out else None) for p in f.people]
    if prev is not None:
        prev.clear()
        prev.update({p: t.id for p, t in out.items()})
    return rows


def score(name, rows, by_pid, review):
    id_sw = false_names = name_sw = 0
    last_tid, last_name = {}, {}
    tids_of: dict[int, set] = {}
    pids_of: dict[int, set] = {}
    matched = {p: 0 for p in by_pid}
    named_ok = {p: 0 for p in by_pid}
    co: dict[tuple, int] = {}
    total_gt = sum(len(r) for r in rows)
    total_tr = 0
    for r in rows:
        for pid, tid, nm in r:
            if tid is None:
                continue
            total_tr += 1
            matched[pid] += 1
            co[(pid, tid)] = co.get((pid, tid), 0) + 1
            tids_of.setdefault(pid, set()).add(tid)
            pids_of.setdefault(tid, set()).add(pid)
            if pid in last_tid and last_tid[pid] != tid:
                id_sw += 1
            last_tid[pid] = tid
            truth = by_pid[pid].label
            if nm is not None and nm != truth:
                false_names += 1
            if nm is not None and nm == truth:
                named_ok[pid] += 1
            if nm is not None:
                if pid in last_name and last_name[pid] != nm:
                    name_sw += 1
                last_name[pid] = nm
    pl, tl = sorted(tids_of), sorted(pids_of)
    m = [[co.get((p, t), 0) for t in tl] for p in pl]
    idtp = sum(m[i][j] for i, j in assign_max(m)) if pl and tl else 0
    idf1 = 2 * idtp / max(total_gt + total_tr, 1)
    badge = [p for p, x in by_pid.items() if x.label]
    named_share = (sum(named_ok[p] for p in badge) / max(sum(matched[p] for p in badge), 1)) if badge else None
    return {"scenario": name, "frames": len(rows), "id_switches": id_sw, "false_names": false_names,
            "name_switches": name_sw, "false_merges": sum(1 for s in pids_of.values() if len(s) > 1),
            "fragments": sum(len(s) - 1 for s in tids_of.values()), "idf1": round(idf1, 3),
            "named_share": None if named_share is None else round(named_share, 3), "review": review}


# ---------------------------------------------------------------- two cameras ---
def run_two_cameras(seed=7):
    """Room 6 x 8 m; camera 1 sees y 0-5 m (door), camera 2 (diagonally opposite) y 3-8 m: overlap 3-5 m.
    U1 enters at camera 1's door and walks into camera 2's area; a stranger (no badge) walks close by."""
    rng = np.random.default_rng(seed)
    def cam1(x, y):                              # floor (m) -> feet pixel, box height
        return 120 + x * 120, 520 - y * 60, 300 - y * 30
    def cam2(x, y):
        return 840 - x * 120, 520 - (8 - y) * 60, 300 - (8 - y) * 30
    pts = [(0.5, 0.5), (5.5, 0.5), (0.5, 7.5), (5.5, 7.5), (3.0, 4.0), (1.5, 2.5)]
    fm1 = FloorMap([{"px": [cam1(x, y)[0] / W, cam1(x, y)[1] / H], "floor": [x, y]} for x, y in pts])
    fm2 = FloorMap([{"px": [cam2(x, y)[0] / W, cam2(x, y)[1] / H], "floor": [x, y]} for x, y in pts])
    a, s = Person(1, "U1", 11), Person(2, None, 33)
    def pos(pid, t):
        if pid == 1:
            if t < 2.0:
                return None
            return (0.6 + min(1.0, (t - 2.0) / 18.0) * 3.4, 0.4 + min(1.0, (t - 2.0) / 18.0) * 6.6)   # door -> far corner
        return (2.6 + 0.6 * math.sin(t / 3.0), 4.6 + 0.4 * math.cos(t / 2.0)) if t >= 8.0 else None
    door1 = (cam1(0.6, 0.4)[0] - 40, 120, 80, 420)
    stacks = []
    for fm, cam, door in ((fm1, cam1, door1), (fm2, cam2, None)):
        stacks.append({"tr": Tracker(), "lab": Labeler(), "cc": CrossCam(None, "", fm), "cam": cam, "door": door,
                       "rows": [], "people": {}, "map": {}})
    occ = [{"auth_subject": "U1", "name": "U1", "role": "STUDENT", "entered_at": 1.5}]
    by_pid = {1: a, 2: s}
    for t in _ts(26):
        for st in stacks:
            ppl = {}
            for pid in (1, 2):
                p = pos(pid, t)
                if p is None:
                    continue
                visible = p[1] <= 5.0 if st["cam"] is cam1 else p[1] >= 3.0
                if not visible:
                    continue
                u, v, h = st["cam"](*p)
                ppl[pid] = box_at(u, v, h)
            dets = [(b, by_pid[pid].look(rng, b)) for pid, b in ppl.items() if rng.random() >= 0.04]
            tracks = st["tr"].update([d[0] for d in dets], t, [d[1] for d in dets])
            st["lab"].assign(tracks, [o for o in occ if o["entered_at"] <= t], st["door"], t)
            st["tracks"], st["frame"] = tracks, Frame(t, ppl)
        for i, st in enumerate(stacks):           # each reads the other's /peer of this pass
            other = stacks[1 - i]
            st["cc"].peer = peer_view(other["tracks"], other["cc"].floor, W, H, t)   # the OTHER camera's view
            st["cc"].share(st["tracks"], W, H, t, st["lab"])
            st["rows"].append(_match_frame(st["frame"], st["tracks"], st["map"]))
    return [score(f"05 two cameras - camera {i + 1}", st["rows"], by_pid, 0) for i, st in enumerate(stacks)]


def main():
    t0 = time.time()
    results = [run(n, fn) for n, fn in SCENARIOS.items()] + run_two_cameras()
    hdr = ["scenario", "id_switches", "false_names", "name_switches", "false_merges", "fragments", "idf1",
           "named_share", "review"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for r in results:
        lines.append("| " + " | ".join(str(r[k]) for k in hdr) + " |")
    table = "\n".join(lines)
    print(table)
    ok = all(r["false_names"] == 0 and r["name_switches"] == 0 for r in results)
    print(f"\nSIMULATED - {len(results)} scenarios in {time.time() - t0:.1f} s; "
          f"false names / name switches: {'NONE' if ok else 'FOUND'}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
    os.makedirs(out, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(out, f"scenario_bench_{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": "SIMULATED", "results": results}, f, indent=1)
    with open(os.path.join(out, f"scenario_bench_{stamp}.md"), "w", encoding="utf-8") as f:
        f.write(f"# Identity scenario bench {stamp} - SIMULATED (not physical evidence)\n\n{table}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
