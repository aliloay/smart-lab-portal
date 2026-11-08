"""
Bin detector test (2026-10-28) on scenes never trained on: data/bin_r2/images/test (coffee table + striped carpet)
plus the no-bin set (background patches from the test scenes, data/smoke_neg - the 4 pictures the 2026-10-27 model
called a bin -, held-out COCO photos and lab-camera frames). Per threshold: bins found with IoU >= 0.5, missed, no-bin pictures wrongly called a bin.
    .venv/Scripts/python eval_bin.py <weights.pt> [more.pt ...]
"""
import glob
import os
import sys

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(HERE, "data", "bin_r2", "images", "test")
NEG = glob.glob(os.path.join(TEST, "neg_*")) + glob.glob(os.path.join(HERE, "data", "smoke_neg", "*"))
# 2026-10-29: + 200 held-out COCO photos (people, textiles) + 221 lab-camera frames from before the bin existed
NEG += glob.glob(os.path.join(HERE, "data", "coco_val", "negtest", "*.jpg")) + glob.glob(os.path.join(HERE, "data", "lab_neg_test", "*.jpg"))
POS = [p for p in glob.glob(os.path.join(TEST, "*.jpg")) if not os.path.basename(p).startswith("neg_")]
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0


def truth(p):
    cx, cy, w, h = map(float, open(p.replace("images", "labels")[:-4] + ".txt").read().split()[1:])
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def run(wts):
    m = YOLO(wts)
    best = lambda p: (lambda r: (float(r.boxes.conf[0]), r.boxes.xyxyn[0].tolist()) if len(r.boxes) else (0.0, None))(
        m.predict(p, conf=0.05, imgsz=640, verbose=False)[0])
    pos = [(best(p), truth(p)) for p in POS]
    neg = [best(p)[0] for p in NEG]
    print(f"\n{wts}  ({len(POS)} bins in unseen scenes, {len(NEG)} no-bin pictures)")
    for t in THRESHOLDS:
        hit = sum(1 for (c, b), g in pos if c >= t and b and iou(b, g) >= 0.5)
        fp = sum(1 for c in neg if c >= t)
        print(f"  conf {t:.1f}: found {hit}/{len(POS)}   wrongly called a bin {fp}/{len(NEG)}")
    print("  no-bin top scores:", sorted(round(c, 2) for c in neg)[-5:])


if __name__ == "__main__":
    for w in sys.argv[1:]:
        run(w)
