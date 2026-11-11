"""Writes colab_train_lab_r3.ipynb and the dataset zip for it (2026-11-11).

    py tools/vision_train/make_colab_lab_r3.py            -> notebook next to this file + D:/SmartLabData/colab/lab_r1.zip

Round 3 of the lab-wide 12-class detector (the model behind the phone's "Scan the lab"). Same data as round 1
(data/lab_r1: 1,821 train / 110 val / 371 test images), three candidates compared on the SAME held-out test split,
with the same per-class "found / false on no-object photos" count as results/lab_2026-11-02_1731/test_report.json:
  A  YOLO11n 640, 150 epochs   (round 1 was YOLO11n; deploy size, 2 CPU threads ~77 ms)
  B  YOLO11s 640, 150 epochs   (round 1's r1_s found the switch 25/29 vs 12/29 - slower on the CPU)
  C  YOLO11n 640, 150 epochs, stronger augmentation for the rare classes (pendants 12-15, PCs / door 24 boxes)
Only a 640 input is exported: the backend letterboxes every phone frame to 640 (app/services/bin_detector.py).
"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "lab_r1")
OUT_ZIP = r"D:\SmartLabData\colab\lab_r1.zip"

CELLS = [
    ("markdown", """# Smart Lab - lab-wide detector, round 3 (12 classes)
Upload **lab_r1.zip** to Google Drive at `MyDrive/SmartLab/lab_r1.zip`, then *Runtime -> Change runtime type -> T4 GPU*,
then *Runtime -> Run all*. About 1.5-2.5 h on a free T4 for the three candidates.

What it does: trains three candidates on the same data, scores each on the same held-out test split exactly like round 1
(per class: objects found at confidence >= 0.5 with IoU >= 0.5, and false hits on the no-object photos), exports the
best-scoring one to ONNX at 640, and saves everything to `MyDrive/SmartLab/lab_r3_<time>/`.

Bring back: the folder's `best.onnx`, `test_report.json` and `summary.md`. Deploying = copy best.onnx to
`backend/data/models/lab_detector.onnx` **only if** it beats round 1 on the classes that matter, without more false hits."""),
    ("code", """!nvidia-smi -L
!pip -q install "ultralytics>=8.3,<9" onnx onnxruntime"""),
    ("code", """from google.colab import drive
drive.mount('/content/drive')
import os, zipfile, time, json, shutil
SRC = '/content/drive/MyDrive/SmartLab/lab_r1.zip'
assert os.path.exists(SRC), 'Upload lab_r1.zip to MyDrive/SmartLab/ first'
if not os.path.exists('/content/lab_r1/data.yaml'):
    zipfile.ZipFile(SRC).extractall('/content')
for s in ('train', 'val', 'test'):
    print(s, len(os.listdir(f'/content/lab_r1/images/{s}')), 'images')
STAMP = time.strftime('%Y-%m-%d_%H%M')
OUT = f'/content/drive/MyDrive/SmartLab/lab_r3_{STAMP}'
os.makedirs(OUT, exist_ok=True)
print('results go to', OUT)"""),
    ("code", """from ultralytics import YOLO
COMMON = dict(data='/content/lab_r1/data.yaml', imgsz=640, epochs=150, patience=40, batch=16, cos_lr=True,
              close_mosaic=15, project='/content/runs', exist_ok=True, plots=True, seed=0)
CANDIDATES = {
    'r3_n':     dict(model='yolo11n.pt'),
    'r3_s':     dict(model='yolo11s.pt'),
    'r3_n_aug': dict(model='yolo11n.pt', mixup=0.15, scale=0.7, degrees=8.0, translate=0.15, hsv_v=0.5, fliplr=0.5),
}
for name, extra in CANDIDATES.items():
    if os.path.exists(f'/content/runs/{name}/weights/best.pt'):
        print('done already:', name); continue
    m = YOLO(extra.pop('model'))
    m.train(name=name, **COMMON, **extra)"""),
    ("code", """# Same scoring as round 1 (results/lab_2026-11-02_1731/test_report.json): per class, objects found at conf >= 0.5
# with IoU >= 0.5, and false hits on test photos that contain none of that class.
import glob, numpy as np
from PIL import Image
NAMES = YOLO(f'/content/runs/r3_n/weights/best.pt').names
def boxes_of(lbl, w, h):
    out = []
    if os.path.exists(lbl):
        for line in open(lbl):
            p = line.split()
            if len(p) >= 5:
                c, x, y, bw, bh = int(p[0]), *map(float, p[1:5])
                out.append((c, (x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h))
    return out
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0
def score(weights, conf=0.5):
    m = YOLO(weights)
    per = {n: {'test_objects': 0, 'found': 0, 'false_on_no_object': 0} for n in NAMES.values()}
    imgs = sorted(glob.glob('/content/lab_r1/images/test/*'))
    for path in imgs:
        w, h = Image.open(path).size
        gt = boxes_of(path.replace('/images/', '/labels/').rsplit('.', 1)[0] + '.txt', w, h)
        r = m.predict(path, conf=conf, imgsz=640, verbose=False)[0]
        pred = [(int(c), *map(float, b)) for c, b in zip(r.boxes.cls.tolist(), r.boxes.xyxy.tolist())]
        for c, name in NAMES.items():
            g = [b for b in gt if b[0] == c]; p = [b for b in pred if b[0] == c]
            per[name]['test_objects'] += len(g)
            per[name]['found'] += sum(1 for gb in g if any(iou(gb[1:], pb[1:]) >= 0.5 for pb in p))
            if not g and p:
                per[name]['false_on_no_object'] += 1
    t = m.val(data='/content/lab_r1/data.yaml', split='test', imgsz=640, verbose=False)
    return {'per_class': per, 'mAP50': round(float(t.box.map50), 3), 'mAP50_95': round(float(t.box.map), 3)}
report = {n: score(f'/content/runs/{n}/weights/best.pt') for n in CANDIDATES}
json.dump(report, open(f'{OUT}/test_report.json', 'w'), indent=1)
for n, r in report.items():
    tot = sum(v['found'] for v in r['per_class'].values()), sum(v['test_objects'] for v in r['per_class'].values())
    fp = sum(v['false_on_no_object'] for v in r['per_class'].values())
    print(f"{n}: found {tot[0]}/{tot[1]}, false {fp}, mAP50 {r['mAP50']}, mAP50-95 {r['mAP50_95']}")"""),
    ("code", """# Pick: most objects found, then fewest false hits; export it to ONNX at 640 (what the backend loads).
def key(n):
    pc = report[n]['per_class']
    return (sum(v['found'] for v in pc.values()), -sum(v['false_on_no_object'] for v in pc.values()), report[n]['mAP50_95'])
best = max(report, key=key)
onnx = YOLO(f'/content/runs/{best}/weights/best.pt').export(format='onnx', imgsz=640, opset=12, simplify=True)
shutil.copy(onnx, f'{OUT}/best.onnx')
for n in CANDIDATES:
    shutil.copytree(f'/content/runs/{n}', f'{OUT}/{n}', dirs_exist_ok=True)
lines = ['# Round 3 result', '', f'Best: **{best}** (exported as best.onnx, 640 input)', '',
         '| class | ' + ' | '.join(CANDIDATES) + ' |', '|---|' + '---|' * len(CANDIDATES)]
for name in NAMES.values():
    cells = [f"{report[n]['per_class'][name]['found']}/{report[n]['per_class'][name]['test_objects']}"
             f" ({report[n]['per_class'][name]['false_on_no_object']} false)" for n in CANDIDATES]
    lines.append(f'| {name} | ' + ' | '.join(cells) + ' |')
lines += ['', 'Round 1 (deployed) for comparison: switch 12/29, FANUC 2/6, PC 3/4, environment 34/35, others all found.']
open(f'{OUT}/summary.md', 'w').write('\\n'.join(lines))
print('\\n'.join(lines)); print('saved to', OUT)"""),
]


def notebook() -> dict:
    cells = []
    for kind, src in CELLS:
        c = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            c.update(execution_count=None, outputs=[])
        cells.append(c)
    return {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                         "kernelspec": {"display_name": "Python 3", "name": "python3"}},
            "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    nb = os.path.join(HERE, "colab_train_lab_r3.ipynb")
    json.dump(notebook(), open(nb, "w", encoding="utf-8"), indent=1)
    print("notebook:", nb)
    os.makedirs(os.path.dirname(OUT_ZIP), exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_STORED) as z:          # JPEGs do not compress further
        for root, _, files in os.walk(DATA):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, os.path.join("lab_r1", os.path.relpath(p, DATA)))
                n += 1
    print(f"dataset: {OUT_ZIP} ({n} files, {os.path.getsize(OUT_ZIP) / 1e6:.0f} MB)")
