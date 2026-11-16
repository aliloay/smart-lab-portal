"""Writes colab_train_lab_v7.ipynb (2026-11-13): the same three best v6 model types trained on TWO datasets -
  A = lab_v6.zip  (robot pack: only the 79 photos the owner changed count as checked)
  B = lab_v6b.zip (robot pack: all 224 photos count as checked - the owner confirmed the rest were right)
Both include the 228 security-camera frames. Every model + the live model is scored on the SAME truth (B's test/val
labels, the most complete), so A vs B vs live is a fair comparison. Re-run safe (checkpoints on Drive).
    py make_v7_notebook.py"""
import json

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s})


md("""# Smart Lab - lab detector v7 (dataset A vs B, camera frames included)
Needs `lab_v6.zip` and `lab_v6b.zip` anywhere in My Drive. **Runtime > T4 GPU > Run all** (~3 h). Disconnected? Run all
again. Results: `lab_v7_results/comparison.md` next to the zips. Nothing is deployed from here.""")

code("""!nvidia-smi -L
!pip -q install "ultralytics>=8.3,<9" onnx onnxruntime""")

code("""import glob, json, os, shutil, time, zipfile
from pathlib import Path
import numpy as np
from google.colab import drive
for attempt in range(3):                 # Colab's Drive connection sometimes times out on a big Drive
    try:
        drive.mount('/content/drive', force_remount=attempt > 0, timeout_ms=600000)
        break
    except Exception as e:
        print('Drive connect failed, retrying...', repr(e)[:120], flush=True); time.sleep(20)
assert os.path.isdir('/content/drive/MyDrive'), 'Drive did not connect - Runtime > Disconnect and delete runtime, then Run all'
def find(name):
    hits = sorted(glob.glob(f'/content/drive/MyDrive/**/{name}', recursive=True), key=os.path.getmtime, reverse=True)
    assert hits, f'{name} not found in My Drive'
    return hits[0]
ZIPS = {'A': find('lab_v6.zip'), 'B': find('lab_v6b.zip')}
LIVE = find('lab_v6_results/checkpoints_423445150/v6_v8s/best.pt')          # deployed since 13 Nov
OLD = find('SmartLab_results/lab_v2_2026-11-03_1753/r2_s/weights/best.pt')  # deployed 12 Nov
OUT = os.path.join(os.path.dirname(ZIPS['B']), 'lab_v7_results')
CK = os.path.join(OUT, f"checkpoints_{os.path.getsize(ZIPS['A'])}_{os.path.getsize(ZIPS['B'])}")
os.makedirs(CK, exist_ok=True)
DS = {}
for tag, z in ZIPS.items():
    W = Path(f'/content/ds_{tag}')
    if not (W / 'data.yaml').exists():
        t0 = time.time(); shutil.copyfile(z, '/content/tmp.zip')
        with zipfile.ZipFile('/content/tmp.zip') as zz:
            for zi in zz.infolist():
                name = zi.filename.replace(chr(92), '/')
                if name.endswith('/'):
                    continue
                rel = name.split('/', 1)[1]                      # drop the 'lab_v6/' top folder
                os.makedirs(os.path.dirname(str(W / rel)), exist_ok=True)
                with open(W / rel, 'wb') as f:
                    f.write(zz.read(zi))
        os.remove('/content/tmp.zip')
        y = open(W / 'data.yaml').read().replace('path: /content/lab_v6', f'path: {W}')
        open(W / 'data.yaml', 'w').write(y)
        print(tag, 'unpacked in', round(time.time() - t0), 's')
    DS[tag] = W
    assert len(list((W / 'images' / 'cam_test').glob('*'))) >= 10, f'{tag}: old zip (no camera frames) - wait for the Drive upload, then Run all again'
    for s in ('train', 'val', 'test', 'test_multi', 'cam_test'):
        n = len(list((W / 'images' / s).glob('*')))
        b = sum(len([l for l in open(f) if l.strip()]) for f in (W / 'labels' / s).glob('*.txt'))
        print(f'  {tag} {s:10s} {n:5d} photos {b:5d} boxes')
TRUTH = DS['B']                                                   # common scoring truth
NAMES = ['reusable_bin', 'consumables_node', 'environment_node', 'master_node', 'network_switch', 'network_router',
         'ur5e_robot', 'ur5e_teach_pendant', 'fanuc_robot', 'fanuc_teach_pendant', 'lab_pc', 'lab_door']""")

code("""from ultralytics import YOLO
TYPES = {'v8s': 'yolov8s.pt', 'y11s': 'yolo11s.pt', 'y11n': 'yolo11n.pt'}       # the v6 top three
RUNS = {f'{tag}_{t}': (tag, w) for t, w in TYPES.items() for tag in ('B', 'A')}
HP = dict(imgsz=640, epochs=80, patience=20, batch=16, optimizer='AdamW', lr0=0.001, cos_lr=True, mosaic=1.0,
          close_mosaic=10, copy_paste=0.1, degrees=5, fliplr=0.5, project='/content/runs', exist_ok=True, plots=False)
def ckpt_cb(name):
    def cb(tr):
        for fn in ('last.pt', 'best.pt'):
            s = Path(tr.save_dir) / 'weights' / fn
            if s.exists():
                shutil.copy2(s, os.path.join(CK, name, fn))
    return cb
for name, (tag, base) in RUNS.items():
    d = os.path.join(CK, name); os.makedirs(d, exist_ok=True)
    if os.path.exists(os.path.join(d, 'done')):
        print(name, 'already trained - skipped'); continue
    t0 = time.time()
    try:
        if os.path.exists(os.path.join(d, 'last.pt')) and Path('/content/runs', name).exists():
            m = YOLO(os.path.join(d, 'last.pt')); m.add_callback('on_fit_epoch_end', ckpt_cb(name)); m.train(resume=True)
        else:
            m = YOLO(base); m.add_callback('on_fit_epoch_end', ckpt_cb(name))
            m.train(name=name, data=str(DS[tag] / 'data.yaml'), **HP)
        shutil.copy2(f'/content/runs/{name}/weights/best.pt', os.path.join(d, 'best.pt'))
        open(os.path.join(d, 'done'), 'w').write(f'{(time.time() - t0) / 60:.0f} min')
        print(name, 'done in', round((time.time() - t0) / 60), 'min')
    except Exception as e:
        print('FAILED', name, repr(e)[:300])""")

code("""def load(lbl):
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
    files = sorted((TRUTH / 'images' / split).glob('*'))
    m = YOLO(weights)
    per = {n: [0, 0, 0] for n in NAMES}; neg_fp = 0; t = []
    for p in files:
        gt = load(str(TRUTH / 'labels' / split / (p.stem + '.txt')))
        t0 = time.time(); r = m.predict(str(p), imgsz=640, conf=conf, verbose=False)[0]; t.append(time.time() - t0)
        pr = [(int(c), *b) for c, b in zip(r.boxes.cls.tolist(), r.boxes.xywhn.tolist())]
        if not gt:
            neg_fp += bool(pr); continue
        used = set()
        for g in gt:
            per[NAMES[g[0]]][1] += 1
            best = max(((iou(g[1:], q[1:]), j) for j, q in enumerate(pr) if q[0] == g[0] and j not in used), default=(0, None))
            if best[0] >= 0.5:
                used.add(best[1]); per[NAMES[g[0]]][0] += 1
        for j, q in enumerate(pr):
            if j not in used:
                per[NAMES[q[0]]][2] += 1
    return {'found': sum(v[0] for v in per.values()), 'total': sum(v[1] for v in per.values()),
            'extra_boxes': sum(v[2] for v in per.values()), 'empty_photos_with_a_box': neg_fp,
            'per_class': {k: f'{v[0]}/{v[1]} (+{v[2]})' for k, v in per.items() if v[1] or v[2]},
            'ms_T4': round(1000 * float(np.median(t)), 1)}
models = {'LIVE v6_v8s (deployed 13 Nov)': LIVE, 'old v2_r2_s (deployed 12 Nov)': OLD}
for n in RUNS:
    if os.path.exists(os.path.join(CK, n, 'done')):
        models[n] = os.path.join(CK, n, 'best.pt')
report = {n: {s: evaluate(w, s) for s in ('test', 'test_multi', 'cam_test')} for n, w in models.items()}
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
rows = ['| model | single test | multi test | camera test | extra boxes | empty photos with a box | ms/img T4 |',
        '|---|---|---|---|---|---|---|']
tot = lambda n: sum(report[n][s]['found'] for s in report[n])
for n in sorted(report, key=tot, reverse=True):
    r = report[n]; c = lambda s: f"{r[s]['found']}/{r[s]['total']}"
    rows.append(f"| {n} | {c('test')} | {c('test_multi')} | {c('cam_test')} | {sum(r[s]['extra_boxes'] for s in r)} | "
                f"{r['test']['empty_photos_with_a_box']} | {r['test']['ms_T4']} |")
table = '\\n'.join(rows)
for n in RUNS:
    if n in report:
        try:
            YOLO(os.path.join(CK, n, 'best.pt')).export(format='onnx', imgsz=640, opset=12, simplify=True)
            shutil.copy2(os.path.join(CK, n, 'best.onnx'), os.path.join(OUT, f'{n}.onnx'))
        except Exception as e:
            print('export failed', n, repr(e)[:200])
open(os.path.join(OUT, 'comparison.md'), 'w').write('# v7: dataset A vs B (truth = B labels, conf 0.35)\\n\\n' + table + '\\n')
print(table); print('results ->', OUT)""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open("colab_train_lab_v7.ipynb", "w", encoding="utf-8"), indent=1)
print("written colab_train_lab_v7.ipynb,", len(cells), "cells")
