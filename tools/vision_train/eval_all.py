"""
Which of our things does the combined model find (2026-10-30): per class, the objects found in the held-out test scenes
(right class, IoU >= 0.5) and how often that class fires on no-object pictures, per threshold.
    .venv/Scripts/python.exe eval_all.py [data/all_r1] <weights.pt> [more.pt ...]
"""
import glob
import os
import sys
from collections import Counter

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0


def load_truth(label_path):
    out = []
    for line in open(label_path):
        parts = line.split()
        if len(parts) < 5:
            continue
        cls, cx, cy, w, h = int(parts[0]), *map(float, parts[1:5])
        out.append((cls, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def run(data_dir, wts):
    names = YOLO(wts).names
    pos, neg = [], []
    for p in sorted(glob.glob(os.path.join(data_dir, "images", "test", "*.jpg"))):
        lab = os.path.join(data_dir, "labels", "test", os.path.basename(p)[:-4] + ".txt")
        (pos if os.path.isfile(lab) else neg).append((p, load_truth(lab) if os.path.isfile(lab) else []))
    m = YOLO(wts)
    preds = {}
    for p, _ in pos + neg:
        r = m.predict(p, conf=0.05, imgsz=640, verbose=False)[0]
        preds[p] = [(int(c), float(cf), *b) for c, cf, b in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(),
                                                               r.boxes.xyxyn.tolist())]
    print(f"\n{wts}  ({len(pos)} photos with our things, {len(neg)} no-object photos)")
    for t in THRESHOLDS:
        line = [f"  conf {t:.1f}:"]
        for c, name in names.items():
            gts = [(p, b) for p, g in pos for b in g if b[0] == c]
            det = {p: [d for d in preds[p] if d[0] == c and d[1] >= t] for p in preds}
            found = sum(1 for p, b in gts if any(iou(d[2:], b[1:]) >= 0.5 for d in det[p]))
            false = sum(len(det[p]) for p, _ in neg)
            line.append(f"{name} {found}/{len(gts)} found, {false}/{len(neg)} false")
        print("   ".join(line))
    extra = Counter(d[0] for p, _ in neg for d in preds[p] if d[1] >= 0.3)
    print("  false detections per class at 0.3:", {names[c]: n for c, n in extra.items()} or "none")


if __name__ == "__main__":
    args = sys.argv[1:]
    data = args.pop(0) if args and os.path.isdir(args[0]) else os.path.join(HERE, "data", "all_r1")
    for w in args or [os.path.join(data, "runs", "detect", "runs", "all11", "weights", "best.pt")]:
        run(data, w)
