---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/seat_capture.py"
source_hash: "26680241999c82fa85c1199c213ec9851f238478024d2b3253604f56c15ddf78"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/seat_capture.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_test_pc_occupancy.py]] - tests
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs
- [[tools_security_vision_security_vision.py]] - imports

```py
"""
Record where a person SITTING at a PC appears in each camera (2026-10-21 lab: sitting at PC-07 showed
"PC-08 in use" on both cameras - the body covers the next monitor box). Sit at the PC, alone at that desk,
then run it; each camera that has a box with that name keeps the seated person nearest that monitor box
(10 samples, ~5 s) and saves the averaged person box as the PC's seat in anchors/<DEVICE>_seats.json
(local data). The camera services pick the file up within a second - no restart.

    py seat_capture.py PC-07              record (sit at PC-07 first)
    py seat_capture.py PC-07 --remove     forget PC-07's seat (back to its monitor box)
    py seat_capture.py --list
"""
import json
import os
import sys
import time

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from security_vision import device_key  # noqa: E402

CAMERAS = {5100: "SECCAM_LAB01", 5101: "SECCAM_LAB02"}
STANDING_RATIO = 2.2            # as vision.ZoneWatcher: taller than this x its width = standing
MAX_AWAY = 3.0                  # the seated person's centre within this many monitor-box widths
SAMPLES, EVERY_S = 10, 0.5


def path(dev):
    return os.path.join(HERE, "anchors", f"{dev}_seats.json")


def load(dev):
    try:
        return json.load(open(path(dev), encoding="utf-8"))
    except (OSError, ValueError):
        return {"about": "PC seats: where a person sitting at the PC appears in this camera (0-1 boxes). "
                         "seat_capture.py; used for 'in use' and the two-camera PC link.", "seats": {}}


def pick(state, name):
    """The seated person nearest the named PC box in one /state answer, as a 0-1 box; None if none fits."""
    w, h = state.get("frame") or [0, 0]
    z = next((z for z in state["zones"] if z["name"].upper() == name and z.get("box")), None)
    if not z or not w:
        return None, "no such PC box on this camera"
    zx, zy, zw, zh = z["box"]
    zc = (zx + zw / 2, zy + zh / 2)
    best = None
    for t in state["tracks"]:
        x, y, bw, bh = t["box"]
        if bw <= 0 or bh / bw > STANDING_RATIO:
            continue                                  # standing: not sitting at it
        p = (x / w, y / h, bw / w, bh / h)
        d = np.hypot(p[0] + p[2] / 2 - zc[0], p[1] + p[3] / 2 - zc[1])
        if d <= MAX_AWAY * max(zw, zh) and (best is None or d < best[0]):
            best = (d, p)
    return (best[1], "") if best else (None, "nobody seated near that monitor")


def main():
    a = sys.argv[1:]
    if not a or a[0] == "--list":
        for dev in CAMERAS.values():
            print(dev, sorted(load(dev)["seats"]))
        return
    name = a[0].strip().upper()
    if "--remove" in a:
        for dev in CAMERAS.values():
            d = load(dev)
            if d["seats"].pop(name, None) is not None:
                json.dump(d, open(path(dev), "w", encoding="utf-8"), indent=1)
                print(f"{dev}: {name} seat removed")
        return
    key = {"X-Device-Key": device_key()}
    for port, dev in CAMERAS.items():
        boxes, why = [], ""
        for _ in range(SAMPLES):
            try:
                st = requests.get(f"http://127.0.0.1:{port}/state", headers=key, timeout=3).json()
            except (requests.RequestException, ValueError):
                why = "camera not reachable"
                break
            b, why = pick(st, name)
            if b:
                boxes.append(b)
            time.sleep(EVERY_S)
        if len(boxes) < SAMPLES // 2:
            print(f"{dev}: not saved - {why or 'too few samples'} ({len(boxes)}/{SAMPLES})")
            continue
        seat = [round(float(v), 4) for v in np.median(np.array(boxes), axis=0)]
        d = load(dev)
        d["seats"][name] = {"box": seat, "at": time.strftime("%Y-%m-%d %H:%M"), "samples": len(boxes)}
        os.makedirs(os.path.dirname(path(dev)), exist_ok=True)
        json.dump(d, open(path(dev), "w", encoding="utf-8"), indent=1)
        print(f"{dev}: {name} seat saved {seat} ({len(boxes)} samples)")


if __name__ == "__main__":
    main()

```
