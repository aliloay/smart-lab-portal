"""One object's photo drop -> a ready-to-train YOLO dataset (2026-10-30), the same recipe the Colab notebook and the
local switch round use: YOLO-World draws the boxes (top box per photo), photos are split in shooting order so the test
split is scenes never trained on, and public / lab no-object photos are added as negatives.
    py make_object_round.py <photos dir> <out dir> <class> "<prompt>" ["<prompt>" ...] [--neg <dir> ...]
                           [--conf 0.08] [--imgsz 960]
Writes <out>/images|labels/{train,val,test} + data.yaml + boxes.json + contact sheets boxes_*.jpg (green = the box used,
open them first: a wrong box teaches the wrong thing). Photos without a box are left out.
"""
import glob
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw
from ultralytics import YOLOWorld

TILE, PER_ROW = 220, 8


def sheets(photos, boxes, out):
    for k in range(0, len(photos), 48):
        part = photos[k:k + 48]
        sh = Image.new("RGB", (PER_ROW * TILE, ((len(part) + PER_ROW - 1) // PER_ROW) * (TILE + 14)), "white")
        d = ImageDraw.Draw(sh)
        for i, p in enumerate(part):
            im = Image.open(p); im.thumbnail((TILE, TILE)); w, h = im.size
            x, y = (i % PER_ROW) * TILE, (i // PER_ROW) * (TILE + 14)
            sh.paste(im, (x, y))
            if p in boxes:
                b = boxes[p]
                d.rectangle([x + b[0] * w, y + b[1] * h, x + b[2] * w, y + b[3] * h], outline="lime", width=3)
            d.text((x + 3, y + TILE + 1), os.path.basename(p), fill="black" if p in boxes else "red")
        sh.save(os.path.join(out, f"boxes_{k // 48}.jpg"), quality=80)


def main():
    args = sys.argv[1:]
    negs, conf, imgsz = [], 0.08, 960
    for flag, store in (("--neg", negs), ("--conf", None), ("--imgsz", None)):
        while flag in args:
            i = args.index(flag)
            if store is not None:
                store.append(args[i + 1])
            elif flag == "--conf":
                conf = float(args[i + 1])
            else:
                imgsz = int(args[i + 1])
            del args[i:i + 2]
    src, out, cls, prompts = args[0], args[1], args[2], args[3:]
    photos = sorted(glob.glob(os.path.join(src, "*.jpg")) + glob.glob(os.path.join(src, "*.jpeg"))
                    + glob.glob(os.path.join(src, "*.png")))
    lab = YOLOWorld(os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8s-worldv2.pt"))
    lab.set_classes(prompts)
    boxes = {}
    for p in photos:
        r = lab.predict(p, conf=conf, imgsz=imgsz, verbose=False)[0]
        if len(r.boxes):
            boxes[p] = r.boxes.xyxyn[0].tolist()
    print(f"{len(boxes)} of {len(photos)} photos got a box")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    for sp in ("train", "val", "test"):
        os.makedirs(os.path.join(out, "images", sp))
        os.makedirs(os.path.join(out, "labels", sp))
    lab_ps = [p for p in photos if p in boxes]
    n = len(lab_ps)
    split = {p: ("test" if i >= .85 * n else "val" if i >= .75 * n else "train") for i, p in enumerate(lab_ps)}
    for p, sp in split.items():
        x1, y1, x2, y2 = boxes[p]
        f = os.path.basename(p)
        shutil.copy(p, os.path.join(out, "images", sp, f))
        with open(os.path.join(out, "labels", sp, f[:-4] + ".txt"), "w") as fh:
            fh.write(f"0 {(x1 + x2) / 2:.5f} {(y1 + y2) / 2:.5f} {x2 - x1:.5f} {y2 - y1:.5f}\n")
    negs_used = 0
    for nd in negs:
        for p in sorted(glob.glob(os.path.join(nd, "*.jpg"))):
            shutil.copy(p, os.path.join(out, "images", "train", f"neg_{os.path.basename(nd)}_{os.path.basename(p)}"))
            negs_used += 1
    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {os.path.abspath(out)}\ntrain: images/train\nval: images/val\ntest: images/test\nnames: [{cls}]\n")
    json.dump({os.path.basename(p): b for p, b in boxes.items()}, open(os.path.join(out, "boxes.json"), "w"), indent=1)
    sheets(photos, boxes, out)
    print({sp: sum(1 for v in split.values() if v == sp) for sp in ("train", "val", "test")},
          f"+ {negs_used} no-object photos -> {out}")


if __name__ == "__main__":
    main()
