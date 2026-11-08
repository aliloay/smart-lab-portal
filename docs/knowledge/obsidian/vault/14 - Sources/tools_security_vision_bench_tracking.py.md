---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/bench_tracking.py"
source_hash: "033d5d9eb40288b9d38341475bd9b1c1bfec8e5f610d3b448261cb93d1404e67"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/bench_tracking.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[docs_camera-identity_OVERHAUL_2026-10-14.md]] - mentioned by docs
- [[tools_security_vision_vision.py]] - imports

```py
"""
Offline tracking benchmark on a local recording - no live service, no GPU (CPU detector), no images
kept: only person boxes and colour looks are cached (in the scratch path you give), never committed.

    py bench_tracking.py detect <recording.mp4> <cache.pkl> [start_s] [seconds]
    py bench_tracking.py compare <cache.pkl>

detect : samples the video at the live analysis rate (7/s) and size (960 px wide), runs the
         YOLO26 detector (OpenVINO CPU, 4 threads) and stores boxes + colour looks per frame.
compare: replays the SAME detections through the tracker before/after the 2026-10-14 changes and
         reports duplicates (slivers), tracks started, and fragmentation = a confirmed track that
         starts within 6 s of another confirmed track ending at the same place (one person broken
         into two tracks). No ground-truth labels exist: these are proxies, not precision/recall.
"""
from __future__ import annotations

import math
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def detect(video: str, cache: str, start_s: float = 120.0, seconds: float = 180.0, fps: float = 7.0):
    os.environ["SMARTLAB_DETECTOR"] = "openvino"
    import cv2
    import vision
    det = vision.make_detector(os.path.join(HERE, "models", "yolo26s.onnx"), size=640, threads=4)
    cap = cv2.VideoCapture(video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * src_fps))
    frames, step, n, t0 = [], src_fps / fps, 0, time.time()
    next_take = 0.0
    while n < seconds * src_fps:
        ok = cap.grab()
        if not ok:
            break
        if n >= next_take:
            ok, f = cap.retrieve()
            if not ok:
                break
            h, w = f.shape[:2]
            f = cv2.resize(f, (960, int(h * 960 / w)))
            people = [d.box for d in det.detect(f) if d.cls == vision.PERSON]
            frames.append({"t": n / src_fps, "boxes": people,
                           "looks": [vision.Look(vision.color_signature(f, b)) for b in people]})
            next_take += step
        n += 1
    with open(cache, "wb") as fh:
        pickle.dump(frames, fh)
    print(f"{len(frames)} frames, {sum(len(x['boxes']) for x in frames) / max(len(frames), 1):.2f} people/frame, "
          f"{time.time() - t0:.0f} s")


def replay(frames, old: bool) -> dict:
    import vision
    tr = vision.Tracker()
    if old:                                      # the tracker as it was before 2026-10-14 16:xx
        tr.MAX_MISS_STILL_S = tr.MAX_MISS_S
        tr.REACQ_UNLIKE = 9.0
    seen: dict[int, dict] = {}
    slivers = 0
    for fr in frames:
        boxes = vision.drop_slivers(fr["boxes"]) if not old else fr["boxes"]
        if not old:
            slivers += len(fr["boxes"]) - len(boxes)
        looks = [fr["looks"][fr["boxes"].index(b)] for b in boxes]
        tr.update(boxes, fr["t"], looks)
        for t in tr.tracks:
            if t.last_seen == fr["t"]:
                r = seen.setdefault(t.id, {"start": fr["t"], "first": t.box, "end": fr["t"], "last": t.box, "hits": 0})
                r["end"], r["last"], r["hits"] = fr["t"], t.box, t.hits
    conf = {k: v for k, v in seen.items() if v["hits"] >= vision.Tracker.CONFIRM_HITS}
    c = lambda b: (b[0] + b[2] / 2, b[1] + b[3] / 2)
    frag = 0
    for kb, b in conf.items():
        if any(a is not b and 0 < b["start"] - a["end"] <= 6.0
               and math.dist(c(a["last"]), c(b["first"])) < max(a["last"][3], b["first"][3])
               for a in conf.values()):
            frag += 1
    life = sorted(v["end"] - v["start"] for v in conf.values())
    return {"tracks_started": len(seen), "confirmed_tracks": len(conf), "fragmentations": frag,
            "median_track_life_s": round(life[len(life) // 2], 1) if life else None, "slivers_dropped": slivers}


def compare(cache: str):
    with open(cache, "rb") as fh:
        frames = pickle.load(fh)
    dur = frames[-1]["t"] - frames[0]["t"]
    print(f"{len(frames)} frames over {dur:.0f} s, {sum(len(x['boxes']) for x in frames) / len(frames):.2f} people/frame")
    for name, old in (("before", True), ("after", False)):
        print(name.ljust(7), replay(frames, old))


if __name__ == "__main__":
    if sys.argv[1:2] == ["detect"]:
        detect(sys.argv[2], sys.argv[3], *(float(x) for x in sys.argv[4:6]))
    elif sys.argv[1:2] == ["compare"]:
        compare(sys.argv[2])
    else:
        sys.exit(__doc__)

```
