"""
Network-switch detector test (2026-10-30) on scenes never trained on: data/switch_r1/images/test (the held-out
switch photos) plus no-switch pictures (data/switch_negtest - the owner's bin photos, the 221 held-out lab-camera
frames and 200 held-out COCO photos). Per threshold: switches found with IoU >= 0.5, missed, no-switch pictures
wrongly called a switch.
    .venv/Scripts/python eval_switch.py <weights.pt> [more.pt ...]
"""
import glob
import os
import sys

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(HERE, "data", "switch_r1", "images", "test")
NEG = (glob.glob(os.path.join(HERE, "data", "switch_negtest", "*"))
       + glob.glob(os.path.join(HERE, "data", "lab_neg_test", "*.jpg"))
       + glob.glob(os.path.join(HERE, "data", "coco_val", "negtest", "*.jpg")))
POS = sorted(p for p in glob.glob(os.path.join(TEST, "*.jpg"))
             if os.path.isfile(p.replace("images", "labels")[:-4] + ".txt"))
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0


def truth(p):
    cx, cy, w, h = map(float, open(p.replace("images", "labels")[:-4] + ".txt").read().split()[1:5])
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def run(wts):
    m = YOLO(wts)
    best = lambda p: (lambda r: (float(r.boxes.conf[0]), r.boxes.xyxyn[0].tolist()) if len(r.boxes) else (0.0, None))(
        m.predict(p, conf=0.05, imgsz=640, verbose=False)[0])
    pos = [(best(p), truth(p)) for p in POS]
    neg = [best(p)[0] for p in NEG]
    print(f"\n{wts}  ({len(POS)} switches in unseen scenes, {len(NEG)} no-switch pictures)")
    for t in THRESHOLDS:
        hit = sum(1 for (c, b), g in pos if c >= t and b and iou(b, g) >= 0.5)
        fp = sum(1 for c in neg if c >= t)
        print(f"  conf {t:.1f}: found {hit}/{len(POS)}   wrongly called a switch {fp}/{len(NEG)}")
    print("  no-switch top scores:", sorted(round(c, 2) for c in neg)[-5:])


if __name__ == "__main__":
    for w in sys.argv[1:]:
        run(w)
