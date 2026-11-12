"""Writes colab_train_lab_r5.ipynb (2026-11-12). Fixes found in the Round-4 notebook: datasets not found -> hard fail
with a clear message; teacher pseudo-labels never used as test truth; real resume (YOLO(last.pt).train(resume=True));
no dict mutation; versioned results; every GT box scored one-to-one; candidate exported beside, never deployed.
    py make_r5_notebook.py"""
import json

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s})


md("""# Smart Lab - lab detector, round 5 (multi-object)
Upload to **My Drive/SmartLab/**: `lab_r1.zip` (already there) and **`lab_multi_labeled.zip`** = the 152 wide lab photos
from `lab_multi_prelabel.zip` AFTER the boxes were corrected (images/ + labels/ + classes.txt, same 12 classes, same order).
Runtime > T4 GPU > Run all. Results: `SmartLab/lab_r5_<time>/` (report.json, summary.md, candidate onnx).
This notebook never replaces the deployed model.""")

code("""!nvidia-smi -L
!pip -q install "ultralytics>=8.3,<9" onnx onnxruntime""")

code("""import glob, hashlib, json, os, random, shutil, time, zipfile
from pathlib import Path
from google.colab import drive
drive.mount('/content/drive')
ROOT = next((c for c in glob.glob('/content/drive/MyDrive/SmartLab*')
             if os.path.isdir(c) and os.path.exists(os.path.join(c, 'lab_r1.zip'))), None)
assert ROOT, 'lab_r1.zip not found in My Drive/SmartLab'
MULTI = os.path.join(ROOT, 'lab_multi_labeled.zip')
assert os.path.exists(MULTI), 'Upload lab_multi_labeled.zip (the corrected 152 multi-object photos) to ' + ROOT
STAMP = time.strftime('%Y-%m-%d_%H%M')
OUT = os.path.join(ROOT, f'lab_r5_{STAMP}')
CK = os.path.join(ROOT, 'lab_r5_checkpoints')
os.makedirs(OUT, exist_ok=True)
os.makedirs(CK, exist_ok=True)
print('results ->', OUT)""")

code("""# Data: lab_r1 as-is + the corrected multi photos, split by capture session (file-name prefix): 65 % train / 35 % test_multi.
import yaml
W = Path('/content/lab_r5')
if W.exists():
    shutil.rmtree(W)
with zipfile.ZipFile(os.path.join(ROOT, 'lab_r1.zip')) as z:
    z.extractall('/content')
shutil.copytree('/content/lab_r1', W)
if os.path.exists('/content/multi'):
    shutil.rmtree('/content/multi')
with zipfile.ZipFile(MULTI) as z:
    z.extractall('/content/multi')
NAMES = [l.strip() for l in open(glob.glob('/content/multi/**/classes.txt', recursive=True)[0]) if l.strip()]
y = yaml.safe_load(open(W / 'data.yaml'))
r1_names = y['names'] if isinstance(y['names'], list) else [y['names'][k] for k in sorted(y['names'])]
assert r1_names == NAMES, f'class order differs: {r1_names} vs {NAMES}'
imgs = sorted(p for p in glob.glob('/content/multi/**/images/*', recursive=True)
              if p.lower().endswith(('.jpg', '.jpeg', '.png')))
def session(p):
    return os.path.basename(p).split('__')[0].split('_')[0]
sessions = sorted({session(p) for p in imgs})
random.Random(5).shuffle(sessions)
test_s = set(sessions[: max(1, round(len(sessions) * 0.35))]) if len(sessions) >= 3 else None
print('capture sessions:', len(sessions), '(fewer than 3 -> split by image hash, a weaker leakage guard)')
for p in imgs:
    lbl = p.replace(os.sep + 'images' + os.sep, os.sep + 'labels' + os.sep).rsplit('.', 1)[0] + '.txt'
    if not os.path.exists(lbl):
        continue
    if test_s is not None:
        is_test = session(p) in test_s
    else:
        is_test = int(hashlib.md5(open(p, 'rb').read()).hexdigest(), 16) % 100 < 35
    split = 'test_multi' if is_test else 'train'
    (W / 'images' / split).mkdir(parents=True, exist_ok=True)
    (W / 'labels' / split).mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, W / 'images' / split / ('m_' + os.path.basename(p)))
    shutil.copy2(lbl, W / 'labels' / split / ('m_' + os.path.basename(lbl)))
hashes = {}
for p in glob.glob(str(W / 'images' / '*' / '*')):
    hashes.setdefault(hashlib.md5(open(p, 'rb').read()).hexdigest(), []).append(p)
dups = [v for v in hashes.values() if len({Path(x).parent.name for x in v}) > 1]
print('duplicate images across splits:', len(dups))
assert not dups, dups[:3]
for s in ('train', 'val', 'test', 'test_multi'):
    d = W / 'labels' / s
    files = list(d.glob('*.txt')) if d.exists() else []
    boxes = sum(len([l for l in open(f) if l.strip()]) for f in files)
    print(f'{s}: {len(files)} photos, {boxes} boxes')""")

code("""from ultralytics import YOLO
RUNS = {'r5_n': 'yolo11n.pt', 'r5_s': 'yolo11s.pt'}
HP = dict(data=str(W / 'data.yaml'), imgsz=640, epochs=120, patience=30, batch=16, optimizer='AdamW', lr0=0.001,
          cos_lr=True, mosaic=1.0, close_mosaic=15, mixup=0.0, copy_paste=0.1, degrees=5, fliplr=0.5,
          project='/content/runs', exist_ok=True)
def ckpt_cb(name):
    d = os.path.join(CK, name)
    os.makedirs(d, exist_ok=True)
    def cb(tr):
        for fn in ('last.pt', 'best.pt'):
            s = Path(tr.save_dir) / 'weights' / fn
            if s.exists():
                shutil.copy2(s, os.path.join(d, fn))
    return cb
for name, base in RUNS.items():
    last = os.path.join(CK, name, 'last.pt')
    if os.path.exists(last):            # a real resume of an interrupted run (same args are stored in last.pt)
        m = YOLO(last)
        m.add_callback('on_fit_epoch_end', ckpt_cb(name))
        m.train(resume=True)
    else:
        m = YOLO(base)
        m.add_callback('on_fit_epoch_end', ckpt_cb(name))
        m.train(name=name, **HP)""")

code("""# Evaluation on HUMAN labels only: every GT box matched one-to-one (same class, IoU >= 0.5).
import numpy as np
def load(lbl):
    if not os.path.exists(lbl):
        return []
    return [(int(r[0]), *map(float, r[1:5])) for r in (l.split() for l in open(lbl)) if len(r) >= 5]
def iou(a, b):
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw, ih = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    u = a[2] * a[3] + b[2] * b[3] - iw * ih
    return iw * ih / u if u else 0
def evaluate(weights, split, conf=0.35):
    m = YOLO(weights)
    per = {n: [0, 0, 0] for n in NAMES}
    neg_fp = all_found = multi = 0
    t = []
    for p in sorted((W / 'images' / split).glob('*')):
        gt = load(str(W / 'labels' / split / (p.stem + '.txt')))
        t0 = time.time()
        r = m.predict(str(p), imgsz=640, conf=conf, verbose=False)[0]
        t.append(time.time() - t0)
        pr = [(int(c), *b) for c, b in zip(r.boxes.cls.tolist(), r.boxes.xywhn.tolist())]
        if not gt:
            neg_fp += bool(pr)
            continue
        used, hit = set(), 0
        for g in gt:
            per[NAMES[g[0]]][1] += 1
            best = max(((iou(g[1:], q[1:]), j) for j, q in enumerate(pr) if q[0] == g[0] and j not in used),
                       default=(0, None))
            if best[0] >= 0.5:
                used.add(best[1])
                per[NAMES[g[0]]][0] += 1
                hit += 1
        for j, q in enumerate(pr):
            if j not in used:
                per[NAMES[q[0]]][2] += 1
        if len(gt) >= 2:
            multi += 1
            all_found += hit == len(gt)
    found = sum(v[0] for v in per.values())
    total = sum(v[1] for v in per.values())
    return {'split': split, 'instance_recall': f'{found}/{total}', 'extra_boxes': sum(v[2] for v in per.values()),
            'negative_photos_with_a_box': neg_fp, 'multi_photos_all_found': f'{all_found}/{multi}',
            'per_class': {k: f'{v[0]}/{v[1]} (+{v[2]})' for k, v in per.items() if v[1] or v[2]},
            'ms_per_image_T4': round(1000 * float(np.median(t)), 1) if t else None}
report = {}
for name in RUNS:
    w = f'/content/runs/{name}/weights/best.pt'
    if os.path.exists(w):
        report[name] = {s: evaluate(w, s) for s in ('test', 'test_multi')}
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
print(json.dumps(report, indent=1))""")

code("""# Candidate export ONLY (beside the results). Deploying is the owner's decision after comparing with the deployed
# model on the SAME test + test_multi. Gates: lab_pc not worse, false hits not worse, multi-object recall better.
def recall(k):
    return int(report[k]['test_multi']['instance_recall'].split('/')[0])
best = max(report, key=recall) if report else None
if best:
    YOLO(f'/content/runs/{best}/weights/best.pt').export(format='onnx', imgsz=640, opset=12, simplify=True)
    shutil.copy2(f'/content/runs/{best}/weights/best.onnx', os.path.join(OUT, f'{best}_candidate.onnx'))
    open(os.path.join(OUT, 'summary.md'), 'w').write(f'# Round 5\\nCandidate: {best} (NOT deployed)\\n\\n' + json.dumps(report, indent=1))
print('done ->', OUT)""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open("colab_train_lab_r5.ipynb", "w", encoding="utf-8"), indent=1)
print("written colab_train_lab_r5.ipynb,", len(cells), "cells")
