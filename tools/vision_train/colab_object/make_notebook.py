"""Builds SmartLab_train_object.ipynb + HOW_TO_RUN.txt + SmartLab_Colab_Training.zip (2026-10-29): one object
(default: the TP-Link switch) trained on Colab's free GPU from the owner's Drive photo zip.   py make_notebook.py"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
md, code = "markdown", "code"
cells = [
(md, """# Smart Lab - train a detector for one object (Colab, free GPU)
**How to run:** Runtime -> Change runtime type -> **T4 GPU** -> Save, then **Runtime -> Run all**. Allow Google Drive when asked.
About 15-25 minutes. Change nothing unless you train a different object (cell 2).

Downloads your photo zip from the Smart Lab Drive folder -> converts iPhone HEIC to JPG (no GPS) -> draws the boxes
automatically (YOLO-World) -> adds 400 public no-object photos (COCO) -> trains **YOLO11n** (the model that won the bin
test) -> tests it -> saves the model, the test report and contact sheets of every box to
`MyDrive/SmartLab_results/<object>_<date>/` plus one zip of all of it."""),
(code, "!nvidia-smi --query-gpu=name,memory.total --format=csv\n!pip -q install ultralytics==8.4.* pillow-heif gdown onnx onnxruntime"),
(code, """# ---- 2. What to train (edit only to train a different object) ----
DRIVE_FOLDER = 'https://drive.google.com/drive/folders/12DlDTUkGZK3G37YGxNNONLzUJKG07xrk'
ZIP_NAME_HAS = 'switch'                 # part of the zip's file name on Drive (not case-sensitive)
CLASS = 'network_switch'                # class name in the model
PROMPT = ['black network switch', 'ethernet switch']   # what the automatic labeller looks for
EPOCHS = 100"""),
(code, """import os, glob, zipfile, random, shutil, datetime, json
from google.colab import drive
drive.mount('/content/drive')
OUT = f"/content/drive/MyDrive/SmartLab_results/{CLASS}_{datetime.datetime.now():%Y-%m-%d_%H%M}"
os.makedirs(OUT, exist_ok=True)
!gdown --folder "$DRIVE_FOLDER" -O /content/raw --quiet
zips = [z for z in glob.glob('/content/raw/**/*.zip', recursive=True) if ZIP_NAME_HAS.lower() in os.path.basename(z).lower()]
print('zips found:', zips); assert zips, f'No zip with "{ZIP_NAME_HAS}" in its name in the Drive folder'
for z in zips: zipfile.ZipFile(z).extractall('/content/unzipped')"""),
(code, """from PIL import Image, ImageOps
import pillow_heif; pillow_heif.register_heif_opener()
os.makedirs('/content/photos', exist_ok=True); n = 0
for p in sorted(glob.glob('/content/unzipped/**/*', recursive=True)):
    if '__MACOSX' in p or not p.lower().endswith(('.heic', '.jpg', '.jpeg', '.png')): continue
    im = ImageOps.exif_transpose(Image.open(p)).convert('RGB'); im.thumbnail((1280, 1280))
    im.save(f'/content/photos/{n:04d}.jpg', quality=90); n += 1      # saved without EXIF -> no GPS
print(n, 'photos')"""),
(code, """# automatic boxes + contact sheets (saved to Drive: green = the box used for training)
from ultralytics import YOLOWorld
from PIL import ImageDraw
lab = YOLOWorld('yolov8m-worldv2.pt'); lab.set_classes(PROMPT)
photos = sorted(glob.glob('/content/photos/*.jpg')); boxes = {}
for p in photos:
    r = lab.predict(p, conf=0.08, imgsz=960, verbose=False)[0]
    if len(r.boxes): boxes[p] = (r.boxes.xyxyn[0].tolist(), float(r.boxes.conf[0]))
print(len(boxes), 'of', len(photos), 'photos got a box')
T, W = 220, 8
for k in range(0, len(photos), 48):
    part = photos[k:k+48]; sh = Image.new('RGB', (W*T, ((len(part)+W-1)//W)*(T+14)), 'white'); d = ImageDraw.Draw(sh)
    for i, p in enumerate(part):
        im = Image.open(p); im.thumbnail((T, T)); w, h = im.size; x, y = (i % W)*T, (i//W)*(T+14); sh.paste(im, (x, y))
        if p in boxes:
            b, c = boxes[p]; d.rectangle([x+b[0]*w, y+b[1]*h, x+b[2]*w, y+b[3]*h], outline='lime', width=3)
        d.text((x+3, y+T+1), f"{os.path.basename(p)} {boxes.get(p, (0, 0))[1]:.2f}", fill='black')
    sh.save(f'{OUT}/boxes_{k//48}.jpg', quality=80)"""),
(code, """# dataset: photos in shooting order -> last 15 % = test (scenes not trained on), 10 % val; + COCO no-object photos
D = '/content/data'
for sp in ('train', 'val', 'test'):
    os.makedirs(f'{D}/images/{sp}', exist_ok=True); os.makedirs(f'{D}/labels/{sp}', exist_ok=True)
lab_ps = [p for p in photos if p in boxes]; n = len(lab_ps)
split = {p: ('test' if i >= .85*n else 'val' if i >= .75*n else 'train') for i, p in enumerate(lab_ps)}
for p, sp in split.items():
    (x1, y1, x2, y2), _ = boxes[p]; f = os.path.basename(p)
    shutil.copy(p, f'{D}/images/{sp}/{f}')
    open(f'{D}/labels/{sp}/{f[:-4]}.txt', 'w').write(f'0 {(x1+x2)/2:.5f} {(y1+y2)/2:.5f} {x2-x1:.5f} {y2-y1:.5f}\\n')
!wget -q http://images.cocodataset.org/zips/val2017.zip -O /content/coco.zip
z = zipfile.ZipFile('/content/coco.zip'); names = sorted(i for i in z.namelist() if i.endswith('.jpg')); random.Random(1).shuffle(names)
for i in names[:400]: open(f'{D}/images/train/coco_' + os.path.basename(i), 'wb').write(z.read(i))
os.makedirs('/content/negtest', exist_ok=True)
for i in names[400:600]: open('/content/negtest/' + os.path.basename(i), 'wb').write(z.read(i))
open(f'{D}/data.yaml', 'w').write(f"path: {D}\\ntrain: images/train\\nval: images/val\\ntest: images/test\\nnames: [{CLASS}]\\n")
print({sp: sum(1 for v in split.values() if v == sp) for sp in ('train', 'val', 'test')}, '+ 400 COCO no-object photos')"""),
(code, """from ultralytics import YOLO
YOLO('yolo11n.pt').train(data=f'{D}/data.yaml', epochs=EPOCHS, imgsz=640, batch=32, device=0, project='/content/runs', name=CLASS,
                         exist_ok=True, seed=0, patience=30, fliplr=0.5, degrees=10, scale=0.6, mosaic=1.0, hsv_v=0.5)
best = f'/content/runs/{CLASS}/weights/best.pt'"""),
(code, """# test: objects found in the held-back photos (box overlap >= 0.5) and no-object photos wrongly flagged
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - ix*iy
    return ix*iy/u if u else 0
m = YOLO(best)
top = lambda p: (lambda r: (float(r.boxes.conf[0]), r.boxes.xyxyn[0].tolist()) if len(r.boxes) else (0.0, None))(m.predict(p, conf=0.05, verbose=False)[0])
pos = [(top(p), boxes[p][0]) for p, sp in split.items() if sp == 'test']
neg = [top(p)[0] for p in glob.glob('/content/negtest/*.jpg')]
report = {'class': CLASS, 'photos': len(photos), 'boxed': len(boxes), 'test_objects': len(pos), 'no_object_photos': len(neg), 'by_threshold': {}}
for t in (.3, .4, .5, .6, .7):
    report['by_threshold'][t] = {'found': sum(1 for (c, b), g in pos if c >= t and b and iou(b, g) >= .5), 'false': sum(c >= t for c in neg)}
report['no_object_top_scores'] = sorted(round(c, 2) for c in neg)[-5:]
print(json.dumps(report, indent=1)); json.dump(report, open(f'{OUT}/test_report.json', 'w'), indent=1)"""),
(code, """YOLO(best).export(format='onnx', imgsz=640, opset=12, simplify=False, dynamic=False)
shutil.copytree(f'/content/runs/{CLASS}', f'{OUT}/run', dirs_exist_ok=True)
json.dump({os.path.basename(p): b for p, (b, c) in boxes.items()}, open(f'{OUT}/boxes.json', 'w'))
shutil.make_archive(OUT, 'zip', OUT)
print('DONE - results in', OUT, 'and', OUT + '.zip')"""),
]
HOW = """Smart Lab - train an object detector on Google Colab (free GPU)

1. Upload the photos to the Smart Lab Drive folder as ONE zip with "switch" in its name (e.g. tplink_switch.zip).
   60-100 photos: near / far, all sides, from above and low, lights on and dimmed, with other things around it.
2. Open https://colab.research.google.com -> File -> Upload notebook -> SmartLab_train_object.ipynb
3. Runtime -> Change runtime type -> T4 GPU -> Save
4. Runtime -> Run all. Allow Google Drive access when asked. Wait ~15-25 min until the last cell prints DONE.
5. Results land in Google Drive: MyDrive/SmartLab_results/network_switch_<date>/ (+ a .zip of it):
     test_report.json        found / false alarms per threshold
     boxes_*.jpg             every automatic box (green) - a quick visual check
     run/weights/best.onnx   the model for the portal
6. Tell Claude "Colab done" and drag the results .zip into the Smart Lab Drive folder (the one with the photos).
   Claude downloads it, checks every box and the report, tests the model through the portal's own code and deploys it
   only if it passes. Colab does not send anything to Claude by itself.

Another object later (UR5e, FANUC, PCs, door...): in cell 2 change ZIP_NAME_HAS, CLASS and PROMPT, then Run all.
Keep faces out of the photos. Nothing from the lab cameras goes to Colab.
"""

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "cells": [{"cell_type": t, "metadata": {}, "source": s, **({"outputs": [], "execution_count": None} if t == code else {})}
                for t, s in cells]}
nbp, howp = os.path.join(HERE, "SmartLab_train_object.ipynb"), os.path.join(HERE, "HOW_TO_RUN.txt")
json.dump(nb, open(nbp, "w"), indent=1)
open(howp, "w").write(HOW)
with zipfile.ZipFile(os.path.join(HERE, "SmartLab_Colab_Training.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.write(nbp, os.path.basename(nbp)); z.write(howp, os.path.basename(howp))
print("ok")
