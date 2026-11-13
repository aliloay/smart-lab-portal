"""2026-11-13: box-review pack for the weak classes (robots, pendants, PCs, door). Collects
  - every photo in lab_src/{fanuc_robot, fanuc_teach_pendant, ur5e_robot, ur5e_teach_pendant, lab_pc, lab_door}
  - frames (one per second) from the owner's UR5e video(s) in ~/.claude/uploads
  - owner photos sent in chats (~/.claude/uploads/*.jpg|png) in which the live model sees a robot / pendant / PC / door
near-duplicates removed (dHash <= 5), and pre-boxes EVERY class with the live model (low threshold) so the owner only
corrects. Output D:/SmartLabData/colab/robot_pack/{images,labels/classes.txt}. build_v6_dataset.py then uses these
human boxes instead of the single auto box. Never committed (photos)."""
import glob, os, shutil, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import json  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

D = r"D:\SmartLabData\vision_train_data"
UP = os.path.expanduser(r"~\.claude\uploads")
OUT = r"D:\SmartLabData\colab\robot_pack"
TMP = r"D:\SmartLabData\colab\robot_pack_tmp"
WEAK = ["fanuc_robot", "fanuc_teach_pendant", "ur5e_robot", "ur5e_teach_pendant", "lab_pc", "lab_door"]
M = os.path.join(HERE, "..", "..", "backend", "data", "models")
spec = next(s for s in json.load(open(os.path.join(M, "detectors.json"), encoding="utf-8")) if s["file"] == "lab_detector.onnx")
spec = {**spec, "classes": [{**c, "conf": 0.25, "max_instances": 10} for c in spec["classes"]]}
NAMES = [c["name"] for c in sorted(spec["classes"], key=lambda c: c["index"])]
rt = bd._load(os.path.join(M, "lab_detector.onnx"))


def dhash(img):
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (9, 8))
    return np.packbits((g[:, 1:] > g[:, :-1]).flatten())


for d in (OUT, TMP):
    if os.path.exists(d):
        shutil.rmtree(d)
os.makedirs(os.path.join(OUT, "images")); os.makedirs(os.path.join(OUT, "labels")); os.makedirs(TMP)
open(os.path.join(OUT, "labels", "classes.txt"), "w").write("\n".join(NAMES) + "\n")
open(os.path.join(OUT, "classes.txt"), "w").write("\n".join(NAMES) + "\n")

cands = []                                          # (name, image, source)
for cls in WEAK:
    for p in sorted(glob.glob(os.path.join(D, "lab_src", cls, "**", "*"), recursive=True)):
        if p.lower().endswith((".jpg", ".jpeg", ".png")) and "__MACOSX" not in p:
            cands.append((f"{cls}__{os.path.basename(p)}", p, "lab_src"))
vids = glob.glob(os.path.join(UP, "**", "*.mov"), recursive=True) + glob.glob(os.path.join(UP, "**", "*.mp4"), recursive=True)
for z in glob.glob(os.path.join(UP, "**", "*Ur5e*.zip"), recursive=True):
    with zipfile.ZipFile(z) as zz:
        for n in zz.namelist():
            if n.lower().endswith((".mov", ".mp4")) and "__MACOSX" not in n:
                out = os.path.join(TMP, os.path.basename(n)); open(out, "wb").write(zz.read(n)); vids.append(out)
for v in vids:
    if "IMG_6247" in v:                              # the TP-Link switch video, already used
        continue
    cap = cv2.VideoCapture(v); fps = cap.get(5) or 30; n = int(cap.get(7))
    for i in range(0, n, int(fps)):
        cap.set(1, i); ok, im = cap.read()
        if ok:
            p = os.path.join(TMP, f"vid_{os.path.splitext(os.path.basename(v))[0]}_{i:05d}.jpg"); cv2.imwrite(p, im)
            cands.append((os.path.basename(p), p, "video"))
for p in glob.glob(os.path.join(UP, "**", "*-image.jpg"), recursive=True):
    cands.append((f"chat_{os.path.basename(p)}", p, "chat"))

seen, kept, src_count = [], 0, {}
for name, p, src in cands:
    im = cv2.imread(p)
    if im is None or min(im.shape[:2]) < 300:
        continue
    h = dhash(im)
    if any(int(np.unpackbits(h ^ s).sum()) <= 5 for s in seen):
        continue
    hits = bd._infer_multi(rt, spec, im)
    if src != "lab_src" and not any(x["class"] in WEAK for x in hits):
        continue                                     # chat screenshots / frames without a weak-class object
    seen.append(h)
    name = os.path.splitext(name)[0] + ".jpg"
    cv2.imwrite(os.path.join(OUT, "images", name), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    with open(os.path.join(OUT, "labels", os.path.splitext(name)[0] + ".txt"), "w") as f:
        for x in hits:
            b = x["box"]
            f.write(f"{NAMES.index(x['class'])} {b['x'] + b['w']/2:.6f} {b['y'] + b['h']/2:.6f} {b['w']:.6f} {b['h']:.6f}\n")
    kept += 1; src_count[src] = src_count.get(src, 0) + 1
shutil.rmtree(TMP, ignore_errors=True)
print("robot pack:", kept, "photos", src_count, "->", OUT)
