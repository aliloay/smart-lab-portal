---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/floor_refit.py"
source_hash: "70339daf97190ceeaac95e22f51cb3c2bf3d9d6f8306540da1aa68f97f16f1ab"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/floor_refit.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_crosscam.py]] - imports

```py
"""
Add two-camera pairs to both floor maps and refit (2026-10-21). A pair = the same person's feet in camera 1's
and camera 2's picture (pair_check.py); its floor position = the midpoint of the two cameras' current
estimates (as the 2026-10-19 refit). Prints, before and after: each camera's error on the tape marks (true
positions, counted in floor tiles) and the gap between the cameras on every pair. Saves only with --save,
after backing up both files (anchors/<DEVICE>_floor.<time>.bak.json). Restart both camera services to use it.

    py floor_refit.py pairs.json [--save]      pairs.json: [{"name": "...", "px1": [x, y], "px2": [x, y]}, ...]
"""
import json
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from crosscam import FloorMap  # noqa: E402

DEV = {"cam1": "SECCAM_LAB01", "cam2": "SECCAM_LAB02"}
path = {c: os.path.join(HERE, "anchors", f"{d}_floor.json") for c, d in DEV.items()}
data = {c: json.load(open(p, encoding="utf-8")) for c, p in path.items()}
new = json.load(open(sys.argv[1], encoding="utf-8"))


def is_mark(p):                      # tape / tile marks: true positions (numbers in the files)
    return isinstance(p["mark"], int)


def report(pts, title):
    fm = {c: FloorMap(pts[c]) for c in pts}
    marks = {c: [float(np.hypot(*np.subtract(fm[c].project(*p["px"]), p["floor"]))) for p in pts[c] if is_mark(p)] for c in pts}
    by = {c: {p["mark"]: p for p in pts[c] if not is_mark(p)} for c in pts}
    shared = sorted(set(by["cam1"]) & set(by["cam2"]), key=str)
    gaps = {m: float(np.hypot(*np.subtract(fm["cam1"].project(*by["cam1"][m]["px"]), fm["cam2"].project(*by["cam2"][m]["px"]))))
            for m in shared}
    newg = {n["name"]: float(np.hypot(*np.subtract(fm["cam1"].project(*n["px1"]), fm["cam2"].project(*n["px2"])))) for n in new}
    print(f"{title}: tape marks max error cam1 {max(marks['cam1']):.2f} m, cam2 {max(marks['cam2']):.2f} m | "
          f"old pairs mean gap {np.mean(list(gaps.values())):.2f} m (max {max(gaps.values()):.2f}) | "
          + ", ".join(f"{k} {v:.2f} m" for k, v in newg.items()))
    return fm


before = {c: data[c]["points"] for c in data}
fm = report(before, "BEFORE")
after = {c: list(before[c]) for c in before}
n0 = sum(1 for p in before["cam1"] if str(p["mark"]).startswith("pair"))
for i, n in enumerate(new, 1):
    mid = list(np.mean([fm["cam1"].project(*n["px1"]), fm["cam2"].project(*n["px2"])], axis=0))
    mark = f"pair{n0 + i}"
    after["cam1"].append({"mark": mark, "px": n["px1"], "floor": [round(float(v), 3) for v in mid], "note": n["name"]})
    after["cam2"].append({"mark": mark, "px": n["px2"], "floor": [round(float(v), 3) for v in mid], "note": n["name"]})
report(after, "AFTER ")
if "--save" in sys.argv:
    stamp = time.strftime("%Y%m%d-%H%M")
    for c in data:
        shutil.copy2(path[c], path[c].replace("_floor.json", f"_floor.{stamp}.bak.json"))
        data[c]["points"] = after[c]
        data[c]["about"] += (f" + {len(new)} two-camera pairs 2026-10-21 (UR5e / window side, owner standing and"
                             f" Nour seated; full body on both cameras).")
        json.dump(data[c], open(path[c], "w", encoding="utf-8"), indent=1)
    print("saved both floor maps (backups *_floor." + stamp + ".bak.json); restart both camera services")

```
