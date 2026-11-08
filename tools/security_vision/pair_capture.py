"""
Two-camera floor pairs, captured live (2026-10-21): for N samples, every track on both cameras - its box
(pixels), name, identity state, floor position - plus both pictures once. Saved to
anchors/floor_pairs/<time>/ (git-ignored local data) for the floor-map refit. Read-only.

    py pair_capture.py "Ali standing at the UR5e, Nour seated beside him"   [samples] [interval_s]
"""
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from security_vision import device_key  # noqa: E402

note = sys.argv[1] if len(sys.argv) > 1 else ""
n, every = int(sys.argv[2]) if len(sys.argv) > 2 else 20, float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
H = {"X-Device-Key": device_key()}
out = os.path.join(HERE, "anchors", "floor_pairs", time.strftime("%Y-%m-%d_%H%M%S"))
os.makedirs(out, exist_ok=True)
for port in (5100, 5101):
    open(os.path.join(out, f"cam{port - 5099}.jpg"), "wb").write(
        requests.get(f"http://127.0.0.1:{port}/frame.jpg", headers=H, timeout=5).content)
rows = []
for i in range(n):
    t = time.time()
    row = {"t": round(t, 2)}
    for port in (5100, 5101):
        st = requests.get(f"http://127.0.0.1:{port}/state", headers=H, timeout=3).json()
        pv = requests.get(f"http://127.0.0.1:{port}/peer", headers=H, timeout=3).json()
        floor = {p["id"]: p["floor"] for p in pv["tracks"]}
        row[f"cam{port - 5099}"] = [{"id": tr["id"], "label": tr["label"], "state": tr["identity_state"],
                                     "box": [round(v, 1) for v in tr["box"]], "floor": floor.get(tr["id"])}
                                    for tr in st["tracks"]]
    rows.append(row)
    time.sleep(max(0.0, every - (time.time() - t)))
json.dump({"note": note, "frame": [960, 540], "samples": rows}, open(os.path.join(out, "pairs.json"), "w"), indent=1)
last = rows[-1]
for cam in ("cam1", "cam2"):
    print(cam, [(p["label"] or "Unknown", [int(v) for v in p["box"]], p["floor"] and [round(v, 2) for v in p["floor"]])
                for p in last[cam]])
print("saved", out)
