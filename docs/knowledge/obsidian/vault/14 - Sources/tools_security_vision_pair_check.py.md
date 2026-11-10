---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/pair_check.py"
source_hash: "53fded271dcee8d54a4aace3ca5d7b6c7f2ab560cc57d195f4660026dc4e2e70"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/pair_check.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_crosscam.py]] - imports

```py
"""
One two-camera pair from a pair_capture folder: the given box on each camera (picked by its position, as
the owner told us who he is), averaged over all samples it appears in. Prints each camera's raw floor
estimate (even outside the room - crosscam drops those) and the gap between them.

    py pair_check.py <folder> <cam1 x,y> <cam2 x,y>      (a point inside the wanted box on each camera)
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from crosscam import FloorMap  # noqa: E402

folder, p1, p2 = sys.argv[1], tuple(map(float, sys.argv[2].split(","))), tuple(map(float, sys.argv[3].split(",")))
d = json.load(open(os.path.join(folder, "pairs.json")))
W, H = d["frame"]
maps = {c: FloorMap.load(os.path.join(HERE, "anchors"), dev) for c, dev in (("cam1", "SECCAM_LAB01"), ("cam2", "SECCAM_LAB02"))}


def pick(cam, pt):
    feet = []
    for s in d["samples"]:
        for t in s[cam]:
            x, y, w, h = t["box"]
            if x <= pt[0] <= x + w and y <= pt[1] <= y + h:
                feet.append(((x + w / 2) / W, (y + h) / H, w, h))
    return feet


out = {}
for cam, pt in (("cam1", p1), ("cam2", p2)):
    f = pick(cam, pt)
    if not f:
        sys.exit(f"{cam}: no box at {pt}")
    fx, fy = float(np.mean([a[0] for a in f])), float(np.mean([a[1] for a in f]))
    out[cam] = ((fx, fy), maps[cam].project(fx, fy), len(f), float(np.mean([a[3] / a[2] for a in f])))
    print(f"{cam}: {len(f)} samples, feet at picture ({fx:.3f}, {fy:.3f}), height/width {out[cam][3]:.2f}, "
          f"floor estimate ({out[cam][1][0]:.2f}, {out[cam][1][1]:.2f}) m")
g = float(np.hypot(out["cam1"][1][0] - out["cam2"][1][0], out["cam1"][1][1] - out["cam2"][1][1]))
mid = ((out["cam1"][1][0] + out["cam2"][1][0]) / 2, (out["cam1"][1][1] + out["cam2"][1][1]) / 2)
print(f"gap between the cameras: {g:.2f} m; midpoint ({mid[0]:.2f}, {mid[1]:.2f}) m")
print(json.dumps({"px1": out["cam1"][0], "px2": out["cam2"][0], "gap_m": round(g, 2), "mid": mid}))

```
