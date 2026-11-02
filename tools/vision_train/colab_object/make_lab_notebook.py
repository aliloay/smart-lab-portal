"""Builds SmartLab_train_lab.ipynb (2026-11-02): ONE detector for every Smart Lab object (14 classes), trained on Colab's
GPU from the dataset prepared and box-checked locally (SmartLab_lab_r1_dataset.zip, made by prepare_lab.py build).
    py make_lab_notebook.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
md, code = "markdown", "code"
cells = [
(md, """# Smart Lab - one detector for every lab object (Colab GPU)
1. Upload **SmartLab_lab_r1_dataset.zip** anywhere in your Google Drive.  2. Runtime -> Change runtime type -> **T4 GPU**.
3. **Runtime -> Run all**, allow Drive. About 60-90 min (two model sizes, two rounds each). Leave the tab open.

Round 1 learns each photo's own object (boxes checked on the laptop). Then the round-1 model boxes the OTHER objects
it is very sure about (>= 0.6) in every training photo - a robot next to its pendant, two boxes side by side - and
round 2 retrains with them, so several objects in one frame are learned. YOLO11n (fast) and YOLO11s (better on small /
far objects) are both trained; per-class results and a multi-object test decide. Everything is saved to
`MyDrive/SmartLab_results/lab_<date>/`."""),
(code, "!nvidia-smi --query-gpu=name,memory.total --format=csv\n!pip -q install ultralytics==8.4.* onnx onnxruntime"),
(code, """import os, glob, zipfile, shutil, datetime, json, yaml
from google.colab import drive
drive.mount('/content/drive')
zs = glob.glob('/content/drive/MyDrive/**/SmartLab_lab_r1_dataset*.zip', recursive=True)
print(zs); assert zs, 'Upload SmartLab_lab_r1_dataset.zip to your Google Drive first'
zipfile.ZipFile(zs[0]).extractall('/content')
D = '/content/lab_r1'; NAMES = yaml.safe_load(open(f'{D}/data.yaml'))['names']; NAMES = [NAMES[i] for i in sorted(NAMES)]
OUT = f"/content/drive/MyDrive/SmartLab_results/lab_{datetime.datetime.now():%Y-%m-%d_%H%M}"; os.makedirs(OUT, exist_ok=True)
print(len(NAMES), 'classes'); [print(sp, len(os.listdir(f'{D}/images/{sp}'))) for sp in ('train', 'val', 'test')]"""),
(code, """from ultralytics import YOLO
AUG = dict(fliplr=0.5, degrees=10, scale=0.6, translate=0.15, mosaic=1.0, mixup=0.1, copy_paste=0.0, hsv_h=0.015, hsv_s=0.6,
           hsv_v=0.5, erasing=0.3, close_mosaic=10)
def train(weights, name, data, epochs=100):
    YOLO(weights).train(data=data, epochs=epochs, imgsz=640, batch=32, device=0, project='/content/runs', name=name,
                        exist_ok=True, seed=0, patience=25, cos_lr=True, **AUG)
    return f'/content/runs/{name}/weights/best.pt'
R1 = {s: train(f'yolo11{s}.pt', f'r1_{s}', f'{D}/data.yaml') for s in ('n', 's')}"""),
(code, """# pseudo-labels: every OTHER object the round-1 model is very sure about, added to each training photo's labels
P = '/content/lab_r2'
if os.path.exists(P): shutil.rmtree(P)
shutil.copytree(D, P)
teacher = YOLO(R1['s']); added = 0
for img in glob.glob(f'{P}/images/train/*'):
    lab = img.replace('/images/', '/labels/').rsplit('.', 1)[0] + '.txt'
    have = [l.split() for l in open(lab).read().splitlines() if l.strip()] if os.path.exists(lab) else []
    own = {int(l[0]) for l in have}
    r = teacher.predict(img, conf=0.6, verbose=False)[0]
    for (cx, cy, w, h), c, k in zip(r.boxes.xywhn.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
        if int(k) in own: continue                       # never second-guess the checked box of the photo's own object
        have.append([str(int(k)), f'{cx:.5f}', f'{cy:.5f}', f'{w:.5f}', f'{h:.5f}']); own.add(int(k)); added += 1
    if have: open(lab, 'w').write(''.join(' '.join(l) + '\\n' for l in have))
open(f'{P}/data.yaml', 'w').write(open(f'{D}/data.yaml').read().replace('/content/lab_r1', P))
print(added, 'extra boxes added for other objects in the same photos')
R2 = {s: train(R1[s], f'r2_{s}', f'{P}/data.yaml', epochs=60) for s in ('n', 's')}"""),
(code, """# test: per class (unseen sessions, box overlap >= 0.5) + no-object photos + photos holding 2+ objects
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - ix*iy
    return ix*iy/u if u else 0
tests = sorted(glob.glob(f'{D}/images/test/*'))
def truth(p):
    lab = p.replace('/images/', '/labels/').rsplit('.', 1)[0] + '.txt'
    t = {}
    if os.path.exists(lab):
        for l in open(lab).read().splitlines():
            if l.strip():
                k, cx, cy, w, h = l.split(); cx, cy, w, h = map(float, (cx, cy, w, h)); t[int(k)] = (cx-w/2, cy-h/2, cx+w/2, cy+h/2)
    return t
T = {p: truth(p) for p in tests}
def evaluate(w, th=0.5):
    m = YOLO(w); rep = {'per_class': {}, 'speed_ms': None}
    preds = {}
    for p in tests:
        r = m.predict(p, conf=0.05, verbose=False)[0]; b = {}
        for xy, c, k in zip(r.boxes.xyxyn.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            if c > b.get(int(k), (0, None))[0]: b[int(k)] = (c, xy)
        preds[p] = b
    for k, n in enumerate(NAMES):
        pos = [(preds[p].get(k, (0, None)), t[k]) for p, t in T.items() if k in t]
        neg = [preds[p].get(k, (0, None))[0] for p, t in T.items() if not t]
        rep['per_class'][n] = {'test_objects': len(pos), 'found': sum(1 for (c, b), g in pos if c >= th and b and iou(b, g) >= .5),
                               'false_on_no_object': sum(c >= th for c in neg)}
    multi = [p for p, t in T.items() if len(t) >= 2]
    rep['multi_object_photos'] = len(multi)
    rep['multi_object_all_found'] = sum(1 for p in multi if all(preds[p].get(k, (0, None))[0] >= th and preds[p][k][1]
                                                                  and iou(preds[p][k][1], g) >= .5 for k, g in T[p].items()))
    v = m.val(data=f'{D}/data.yaml', split='test', verbose=False)
    rep['mAP50'], rep['mAP50_95'] = round(float(v.box.map50), 3), round(float(v.box.map), 3)
    rep['speed_ms'] = round(float(v.speed['inference']), 1)
    return rep
REPORT = {f'{r}_{s}': evaluate(w) for r, d in (('r1', R1), ('r2', R2)) for s, w in d.items()}
for k, v in REPORT.items():
    print(k, 'mAP50', v['mAP50'], 'mAP50-95', v['mAP50_95'], '| multi-object photos all found', v['multi_object_all_found'], '/', v['multi_object_photos'])
    print('   ', ' '.join(f"{n}:{c['found']}/{c['test_objects']}({c['false_on_no_object']}fp)" for n, c in v['per_class'].items()))
json.dump(REPORT, open(f'{OUT}/test_report.json', 'w'), indent=1)"""),
(code, """# best = highest mAP50-95 (ties -> the faster n); export it and save everything
best_key = max(REPORT, key=lambda k: (REPORT[k]['mAP50_95'], k.endswith('_n')))
best_w = {**{f'r1_{s}': w for s, w in R1.items()}, **{f'r2_{s}': w for s, w in R2.items()}}[best_key]
print('BEST:', best_key)
YOLO(best_w).export(format='onnx', imgsz=640, opset=12, simplify=False, dynamic=False)
for k in ('r1_n', 'r1_s', 'r2_n', 'r2_s'):
    shutil.copytree(f'/content/runs/{k}', f'{OUT}/{k}', dirs_exist_ok=True)
json.dump({'best': best_key, 'classes': NAMES}, open(f'{OUT}/best.json', 'w'))
shutil.copy(best_w.replace('.pt', '.onnx'), f'{OUT}/lab_detector.onnx')
print('DONE - results in', OUT)"""),
]
nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "cells": [{"cell_type": t, "metadata": {}, "source": s, **({"outputs": [], "execution_count": None} if t == code else {})}
                for t, s in cells]}
json.dump(nb, open(os.path.join(HERE, "SmartLab_train_lab.ipynb"), "w"), indent=1)
print("ok")
