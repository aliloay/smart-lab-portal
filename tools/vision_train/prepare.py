"""
Round-one dataset preparation (docs/VISUAL_AI_PLAN.md).

  py prepare.py frames <videos_dir> <out_dir> [fps=2]
        one folder per video = one SESSION (frames ~2/s, near-duplicates skipped); a session never spans two splits
  py prepare.py split <labeled_dir> <out_dir> [seed=0]
        <labeled_dir>/<session>/{*.jpg, *.txt (YOLO labels)}; sessions -> 70/15/15 train/val/test by session,
        writes data.yaml with the frozen 12 classes + split_manifest.json (which session went where, file counts)
Labels: draw them in any YOLO-format tool (e.g. Label Studio / CVAT export "YOLO"). Images without a .txt are kept as
NEGATIVES (no objects) - the plan's no-target scenes.
"""
import json
import os
import random
import shutil
import sys

CLASSES = ["person", "ur5e_robot", "fanuc_robot", "robot_controller", "lab_computer_station", "master_door_unit",
           "environment_node", "consumables_node", "reusable_bin_node", "plc_cabinet", "security_camera",
           "networking_device"]


def frames(videos, out, fps=2.0):
    import cv2
    import numpy as np
    for v in sorted(os.listdir(videos)):
        if not v.lower().endswith((".mp4", ".mov", ".m4v")):
            continue
        cap = cv2.VideoCapture(os.path.join(videos, v))
        step = max(1, round((cap.get(cv2.CAP_PROP_FPS) or 30) / fps))
        d = os.path.join(out, os.path.splitext(v)[0])
        os.makedirs(d, exist_ok=True)
        i = kept = 0
        last = None
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if i % step == 0:
                small = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 64)).astype("float32")
                if last is None or float(np.mean(np.abs(small - last))) > 4.0:     # skip near-identical frames
                    cv2.imwrite(os.path.join(d, f"{kept:05d}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    kept += 1
                    last = small
            i += 1
        print(f"{v}: {kept} frames -> {d}")


def split(src, out, seed=0):
    sessions = sorted(d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d)))
    random.Random(seed).shuffle(sessions)
    n = len(sessions)
    cut1, cut2 = round(n * 0.70), round(n * 0.85)
    plan = {"train": sessions[:cut1], "val": sessions[cut1:cut2], "test": sessions[cut2:]}
    shutil.rmtree(out, ignore_errors=True)
    counts = {}
    for part, ss in plan.items():
        for sub in ("images", "labels"):
            os.makedirs(os.path.join(out, sub, part), exist_ok=True)
        imgs = negs = 0
        for s in ss:
            for f in os.listdir(os.path.join(src, s)):
                if not f.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                stem = f"{s}__{os.path.splitext(f)[0]}"
                shutil.copy(os.path.join(src, s, f), os.path.join(out, "images", part, stem + ".jpg"))
                lab = os.path.join(src, s, os.path.splitext(f)[0] + ".txt")
                if os.path.isfile(lab):
                    shutil.copy(lab, os.path.join(out, "labels", part, stem + ".txt"))
                else:
                    negs += 1
                imgs += 1
        counts[part] = {"sessions": len(ss), "images": imgs, "negatives": negs}
    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {os.path.abspath(out)}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n"
                + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    json.dump({"seed": seed, "classes": CLASSES, "sessions": plan, "counts": counts},
              open(os.path.join(out, "split_manifest.json"), "w"), indent=1)
    print(json.dumps(counts))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "frames":
        frames(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 2.0)
    elif cmd == "split":
        split(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 0)
