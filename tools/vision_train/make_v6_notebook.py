"""Writes colab_train_lab_v6.ipynb (2026-11-12): one dataset (lab_v6.zip, build_v6_dataset.py), SIX models trained on
it - our two lab models warm-started + four universal COCO models - and two untrained baselines (the live model and the
previous one), all scored the same way on the same human-labelled splits; a comparison table at the end.
Safe to re-run after a disconnect: every model checkpoints to Drive and resumes; finished models are not retrained.
    py make_v6_notebook.py"""
import json

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s})


md("""# Smart Lab - lab detector v6 (all photos, all models, one comparison)
Needs in **My Drive/SmartLab/**: `lab_v6.zip` and in **My Drive/SmartLab_results/lab_v2_2026-11-03_1753/** the two lab models.
**Runtime > Change runtime type > T4 GPU**, then **Run all**. About 4-5 h for all six models; if Colab disconnects, just
Run all again - finished models are skipped, an interrupted one resumes. Results: `SmartLab/lab_v6_results/`
(comparison.md, report.json, one .onnx per model). Nothing is deployed from here.""")

code("""!nvidia-smi -L
!pip -q install "ultralytics>=8.3,<9" onnx onnxruntime""")

code("""import glob, json, os, shutil, time, zipfile
from pathlib import Path
import numpy as np
from google.colab import drive
drive.mount('/content/drive')
ROOT = '/content/drive/MyDrive/SmartLab'
ZIP = os.path.join(ROOT, 'lab_v6.zip')
for i in range(60):                    # Google Drive for desktop may still be uploading the 400 MB zip
    if os.path.exists(ZIP):
        break
    print('waiting for lab_v6.zip to appear in Drive...', i, 'min', flush=True); time.sleep(60)
assert os.path.exists(ZIP), 'lab_v6.zip is not in My Drive/SmartLab after 60 min - check the Drive app on the laptop'
V2 = '/content/drive/MyDrive/SmartLab_results/lab_v2_2026-11-03_1753'
for r in ('r1_n', 'r2_s'):
    assert os.path.exists(f'{V2}/{r}/weights/best.pt'), f'missing lab model {V2}/{r}/weights/best.pt'
OUT = os.path.join(ROOT, 'lab_v6_results')
CK = os.path.join(OUT, f'checkpoints_{os.path.getsize(ZIP)}')       # tied to this exact dataset
os.makedirs(CK, exist_ok=True)
W = Path('/content/lab_v6')
if not (W / 'data.yaml').exists():
    t0 = time.time()
    print('copying the zip from Drive to the Colab disk...', flush=True)
    shutil.copyfile(ZIP, '/content/lab_v6.zip')        # one sequential read; reading inside Drive is very slow
    print(f'copied {os.path.getsize("/content/lab_v6.zip") // 2**20} MB in {time.time() - t0:.0f} s; unpacking...', flush=True)
    with zipfile.ZipFile('/content/lab_v6.zip') as z:
        infos = z.infolist()
        for i, zi in enumerate(infos):
            name = zi.filename.replace(chr(92), '/')
            if not name.endswith('/'):
                os.makedirs(os.path.dirname('/content/' + name), exist_ok=True)
                with open('/content/' + name, 'wb') as f:
                    f.write(z.read(zi))
            if i % 1000 == 0:
                print(f'  {i}/{len(infos)} files', flush=True)
    os.remove('/content/lab_v6.zip')
    print(f'dataset ready in {time.time() - t0:.0f} s', flush=True)
NAMES = ['reusable_bin', 'consumables_node', 'environment_node', 'master_node', 'network_switch', 'network_router',
         'ur5e_robot', 'ur5e_teach_pendant', 'fanuc_robot', 'fanuc_teach_pendant', 'lab_pc', 'lab_door']
for s in ('train', 'val', 'test', 'test_multi', 'cam_test'):
    n = len(list((W / 'images' / s).glob('*')))
    b = sum(len([l for l in open(f) if l.strip()]) for f in (W / 'labels' / s).glob('*.txt'))
    print(f'{s:10s} {n:5d} photos {b:5d} boxes')
assert len(list((W / 'images' / 'test_multi').glob('*'))) >= 30, 'test_multi missing - wrong zip'
print(json.load(open(W / 'summary.json')).get('cam_note', 'camera frames included'))""")

code("""from ultralytics import YOLO
# Trained here, in this order (most promising first, so a short session still gives the important ones):
RUNS = {
    'v6_ours_s': f'{V2}/r2_s/weights/best.pt',   # our lab model (live since 12 Nov), warm start
    'v6_ours_n': f'{V2}/r1_n/weights/best.pt',   # our smaller lab model, warm start
    'v6_y11s':   'yolo11s.pt',                   # universal COCO models, fine-tuned on our lab
    'v6_y11n':   'yolo11n.pt',
    'v6_y11m':   'yolo11m.pt',                   # bigger: best accuracy chance, slowest on the laptop
    'v6_v8s':    'yolov8s.pt',                   # other architecture family
}
BASELINES = {'live_r2_s (untrained, deployed)': f'{V2}/r2_s/weights/best.pt',
             'old_r1_n (untrained, before 12 Nov)': f'{V2}/r1_n/weights/best.pt'}
HP = dict(data=str(W / 'data.yaml'), imgsz=640, epochs=80, patience=20, batch=16, optimizer='AdamW', lr0=0.001,
          cos_lr=True, mosaic=1.0, close_mosaic=10, copy_paste=0.1, degrees=5, fliplr=0.5,
          project='/content/runs', exist_ok=True, plots=False)
def ckpt_cb(name):
    def cb(tr):
        for fn in ('last.pt', 'best.pt'):
            s = Path(tr.save_dir) / 'weights' / fn
            if s.exists():
                shutil.copy2(s, os.path.join(CK, name, fn))
    return cb
for name, base in RUNS.items():
    d = os.path.join(CK, name)
    os.makedirs(d, exist_ok=True)
    if os.path.exists(os.path.join(d, 'done')):
        print(name, 'already trained - skipped'); continue
    t0 = time.time()
    try:
        if os.path.exists(os.path.join(d, 'last.pt')) and Path('/content/runs', name).exists():
            m = YOLO(os.path.join(d, 'last.pt')); m.add_callback('on_fit_epoch_end', ckpt_cb(name)); m.train(resume=True)
        else:                                           # fresh VM: start this model again (dataset is the same)
            m = YOLO(base); m.add_callback('on_fit_epoch_end', ckpt_cb(name)); m.train(name=name, **HP)
        shutil.copy2(f'/content/runs/{name}/weights/best.pt', os.path.join(d, 'best.pt'))
        open(os.path.join(d, 'done'), 'w').write(f'{(time.time() - t0) / 60:.0f} min')
        print(name, 'done in', round((time.time() - t0) / 60), 'min')
    except Exception as e:                              # one failed model never stops the others
        print('FAILED', name, repr(e)[:300])""")

code("""# Same scoring for every model, human labels only: each true box matched once (same class, IoU >= 0.5).
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
    files = sorted((W / 'images' / split).glob('*'))
    if not files:
        return None
    m = YOLO(weights)
    per = {n: [0, 0, 0] for n in NAMES}
    neg_fp = all_found = multi = 0
    t = []
    for p in files:
        gt = load(str(W / 'labels' / split / (p.stem + '.txt')))
        t0 = time.time()
        r = m.predict(str(p), imgsz=640, conf=conf, verbose=False)[0]
        t.append(time.time() - t0)
        pr = [(int(c), *b) for c, b in zip(r.boxes.cls.tolist(), r.boxes.xywhn.tolist())]
        if not gt:
            neg_fp += bool(pr); continue
        used, hit = set(), 0
        for g in gt:
            per[NAMES[g[0]]][1] += 1
            best = max(((iou(g[1:], q[1:]), j) for j, q in enumerate(pr) if q[0] == g[0] and j not in used), default=(0, None))
            if best[0] >= 0.5:
                used.add(best[1]); per[NAMES[g[0]]][0] += 1; hit += 1
        for j, q in enumerate(pr):
            if j not in used:
                per[NAMES[q[0]]][2] += 1
        if len(gt) >= 2:
            multi += 1; all_found += hit == len(gt)
    found = sum(v[0] for v in per.values()); total = sum(v[1] for v in per.values())
    return {'found': found, 'total': total, 'extra_boxes': sum(v[2] for v in per.values()),
            'empty_photos_with_a_box': neg_fp, 'multi_all_found': f'{all_found}/{multi}',
            'per_class': {k: f'{v[0]}/{v[1]} (+{v[2]})' for k, v in per.items() if v[1] or v[2]},
            'ms_T4': round(1000 * float(np.median(t)), 1)}
models = dict(BASELINES)
for name in RUNS:
    w = os.path.join(CK, name, 'best.pt')
    if os.path.exists(os.path.join(CK, name, 'done')):
        models[name] = w
report = {}
for name, w in models.items():
    report[name] = {s: evaluate(w, s) for s in ('test', 'test_multi', 'cam_test')}
    print(name, {s: (v['found'], v['total']) for s, v in report[name].items() if v})
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)""")

code("""# Comparison table + one ONNX per trained model (for the laptop speed test). Nothing is deployed.
def cell(v):
    return f"{v['found']}/{v['total']}" if v else '-'
rows = ['| model | single test | multi test | camera test | extra boxes | empty photos with a box | ms/img T4 |',
        '|---|---|---|---|---|---|---|']
def score(n):
    r = report[n]; return sum(r[s]['found'] for s in r if r[s])
for n in sorted(report, key=score, reverse=True):
    r = report[n]
    extra = sum(r[s]['extra_boxes'] for s in r if r[s])
    rows.append(f"| {n} | {cell(r['test'])} | {cell(r['test_multi'])} | {cell(r['cam_test'])} | {extra} | "
                f"{r['test']['empty_photos_with_a_box']} | {r['test']['ms_T4']} |")
table = '\\n'.join(rows)
for n in RUNS:
    if n in report:
        try:
            YOLO(os.path.join(CK, n, 'best.pt')).export(format='onnx', imgsz=640, opset=12, simplify=True)
            shutil.copy2(os.path.join(CK, n, 'best.onnx'), os.path.join(OUT, f'{n}.onnx'))
        except Exception as e:
            print('export failed', n, repr(e)[:200])
open(os.path.join(OUT, 'comparison.md'), 'w').write('# Lab detector v6 - comparison (conf 0.35, IoU 0.5)\\n\\n' + table +
    '\\n\\nPer class: report.json. Laptop speed and live thresholds are measured on the laptop before any swap.\\n')
print(table)
print('results ->', OUT)""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open("colab_train_lab_v6.ipynb", "w", encoding="utf-8"), indent=1)
print("written colab_train_lab_v6.ipynb,", len(cells), "cells")
