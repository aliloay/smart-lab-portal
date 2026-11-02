"""
Lab-wide detector dataset (2026-11-02): one zip per object on the owner's Drive -> data/lab_r1, ready for Colab.
  py prepare_lab.py extract   zips in data/raw_all -> data/lab_src/<class>/*.jpg (HEIC -> JPG without EXIF/GPS,
                              videos -> 2 frames a second, shooting order kept)
  py prepare_lab.py label     YOLO-World draws each photo's OWN object (the zip's class) -> data/lab_boxes.json
                              + contact sheets data/lab_sheets/<class>_N.jpg to check by eye
  py prepare_lab.py build     checked boxes (minus data/lab_reject.json) -> data/lab_r1 {images,labels}/{train,val,test}
                              per class: shooting order, last 15 % test (scenes never trained on), 10 % val;
                              + earlier box-checked bin / switch / router photos + no-object photos (COCO, lab camera)
Other objects that also appear in a photo are boxed on Colab by the first model (pseudo-labels, conf >= 0.6) before the
second training round - see colab_object/SmartLab_train_lab.ipynb.
"""
import glob
import json
import os
import random
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
# class name, zip file name, YOLO-World prompts (plain words work far better than product names - 2026-10-29 switch)
CLASSES = [
    ("reusable_bin", "Resuables_Bin", ["black wicker trash bin", "black bin"]),
    ("consumables_node", "Consumables_Node", ["silver box", "silver electronic box", "metal box"]),
    ("environment_node", "Environment_node", ["black box", "black electronic box", "black plastic box"]),
    ("master_node", "Master_node", ["silver box", "silver electronic box with screen", "metal box"]),
    ("network_switch", "TPLink_Switch", ["black box", "black electronic device", "black plastic box"]),
    ("network_router", "SmartLab_router", ["white router", "wifi router", "white box"]),
    ("ur5e_robot", "UR5e_Robot", ["robot arm", "industrial robot arm", "white robot arm"]),
    ("ur5e_teach_pendant", "UR5e_Teachpendant", ["tablet", "touch screen tablet", "handheld controller"]),
    ("fanuc_robot", "Fanuc_robot", ["yellow robot arm", "industrial robot arm", "robot"]),
    ("fanuc_teach_pendant", "Fanuc_teachpendant", ["teach pendant", "handheld controller", "remote control"]),
    ("lab_pc", "Lab_PCs", ["computer monitor", "desktop computer", "computer"]),
    ("lab_door", "Lab_Door", ["door", "red door"]),
    ("security_camera_1", "Security_Camera_1", ["security camera", "small white camera", "camera"]),
    ("security_camera_2", "Security_Camera_2", ["security camera", "small white camera", "camera"]),
]
# 2026-11-02 review of every contact sheet:
#  - bin / switch / router: these zips repeat photos already boxed BY HAND in rounds 1-5 (data/all_r1); those checked
#    boxes are used instead (a second copy would also leak the same photos into both train and test)
#  - security cameras: the automatic boxes held the lens or the door closer, and both cameras are the same Mercusys
#    model - no detector can tell 1 from 2 by appearance. Left out until close-up videos exist; identity by mount place.
FROM_OLD = {"reusable_bin", "network_switch", "network_router"}
DROP = {"security_camera_1", "security_camera_2"}
NAMES = [c[0] for c in CLASSES if c[0] not in DROP]
SRC, BOXES, SHEETS, OUT = (os.path.join(D, p) for p in ("lab_src", "lab_boxes.json", "lab_sheets", "lab_r1"))


def extract():
    import cv2
    from PIL import Image, ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener()
    for name, zname, _ in CLASSES:
        zs = [z for z in glob.glob(os.path.join(D, "raw_all", "*.zip")) if os.path.basename(z).lower().startswith(zname.lower())]
        if not zs:
            print("missing zip for", name); continue
        out = os.path.join(SRC, name); os.makedirs(out, exist_ok=True); n = v = 0
        with zipfile.ZipFile(zs[0]) as z:
            members = sorted(i for i in z.namelist() if not i.endswith("/") and "__MACOSX" not in i)
            tmp = os.path.join(D, "lab_tmp", name); z.extractall(tmp, members)
        for p in sorted(glob.glob(os.path.join(tmp, "**", "*"), recursive=True)):
            low = p.lower()
            if low.endswith((".heic", ".jpg", ".jpeg", ".png")):
                im = ImageOps.exif_transpose(Image.open(p)).convert("RGB"); im.thumbnail((1280, 1280))
                im.save(os.path.join(out, f"p{n:04d}.jpg"), quality=90); n += 1        # no EXIF -> no GPS
            elif low.endswith((".mov", ".mp4", ".m4v")):
                c = cv2.VideoCapture(p); fps = c.get(cv2.CAP_PROP_FPS) or 30; st = max(1, round(fps / 2)); i = 0
                while True:
                    ok, f = c.read()
                    if not ok:
                        break
                    if i % st == 0:
                        im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)); im.thumbnail((1280, 1280))
                        im.save(os.path.join(out, f"v{v:04d}.jpg"), quality=90); v += 1
                    i += 1
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"{name}: {n} photos, {v} video frames")


def label(world):
    from ultralytics import YOLOWorld
    from PIL import Image, ImageDraw
    m = YOLOWorld(world); res = json.load(open(BOXES)) if os.path.exists(BOXES) else {}
    os.makedirs(SHEETS, exist_ok=True)
    for name, _, prompts in CLASSES:
        fs = sorted(glob.glob(os.path.join(SRC, name, "*.jpg")))
        if not fs:
            continue
        m.set_classes(prompts)
        for f in fs:
            k = os.path.relpath(f, SRC).replace("\\", "/")
            if k in res:
                continue
            r = m.predict(f, conf=0.03, imgsz=960, verbose=False)[0]
            # the photo's own object: the most confident box (ties -> the larger one)
            if len(r.boxes):
                c = r.boxes.conf.tolist(); b = r.boxes.xyxyn.tolist()
                j = max(range(len(c)), key=lambda i: (round(c[i], 2), (b[i][2] - b[i][0]) * (b[i][3] - b[i][1])))
                res[k] = [b[j], c[j]]
            else:
                res[k] = [None, 0.0]
        json.dump(res, open(BOXES, "w"))
        W, T = 10, 190
        for s in range(0, len(fs), 80):
            part = fs[s:s + 80]; sh = Image.new("RGB", (W * T, ((len(part) + W - 1) // W) * (T + 14)), "white"); d = ImageDraw.Draw(sh)
            for i, f in enumerate(part):
                b, c = res[os.path.relpath(f, SRC).replace("\\", "/")]
                im = Image.open(f); im.thumbnail((T, T)); w, h = im.size; x, y = (i % W) * T, (i // W) * (T + 14); sh.paste(im, (x, y))
                if b:
                    d.rectangle([x + b[0] * w, y + b[1] * h, x + b[2] * w, y + b[3] * h], outline="lime" if c >= .1 else "orange", width=3)
                d.rectangle([x, y + h, x + T, y + h + 14], fill="white"); d.text((x + 2, y + h + 1), f"{s + i} {os.path.basename(f)[:5]} {c:.2f}", fill="black")
            sh.save(os.path.join(SHEETS, f"{name}_{s // 80}.jpg"), quality=80)
        print(name, sum(1 for f in fs if res[os.path.relpath(f, SRC).replace('\\', '/')][0]), "/", len(fs), "boxed")


def build():
    res = json.load(open(BOXES))
    rej = json.load(open(os.path.join(D, "lab_reject.json"))) if os.path.exists(os.path.join(D, "lab_reject.json")) else {}
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for sp in ("train", "val", "test"):
        for k in ("images", "labels"):
            os.makedirs(os.path.join(OUT, k, sp), exist_ok=True)
    cnt = {}
    for name, _, _ in CLASSES:
        if name in DROP or name in FROM_OLD:
            continue
        ci = NAMES.index(name)
        fs = sorted(glob.glob(os.path.join(SRC, name, "*.jpg")))
        bad = set(rej.get(name, []))
        keep = [f for i, f in enumerate(fs) if i not in bad and res.get(os.path.relpath(f, SRC).replace("\\", "/"), [None])[0]]
        n = len(keep)
        for i, f in enumerate(keep):
            sp = "test" if i >= .85 * n else "val" if i >= .75 * n else "train"
            b = res[os.path.relpath(f, SRC).replace("\\", "/")][0]
            base = f"{name}__{os.path.basename(f)}"
            shutil.copy(f, os.path.join(OUT, "images", sp, base))
            open(os.path.join(OUT, "labels", sp, base[:-4] + ".txt"), "w").write(
                f"{ci} {(b[0] + b[2]) / 2:.5f} {(b[1] + b[3]) / 2:.5f} {b[2] - b[0]:.5f} {b[3] - b[1]:.5f}\n")
            cnt.setdefault(name, {}).setdefault(sp, 0); cnt[name][sp] += 1
    # earlier box-checked photos (bin rounds, switch, router) as extra training data, class ids remapped
    old = {0: NAMES.index("reusable_bin"), 1: NAMES.index("network_switch"), 2: NAMES.index("network_router")}
    # (their own train / val / test split is kept, so their test scenes stay unseen)
    for sp in ("train", "val", "test"):
        for p in glob.glob(os.path.join(D, "all_r1", "images", sp, "*")):
            lab = p.replace("images", "labels").rsplit(".", 1)[0] + ".txt"
            if sp != "train" and not os.path.exists(lab):
                continue                     # their no-object test photos are the same COCO / lab files added below
            if os.path.basename(p).startswith("lab_"):
                continue                     # lab-camera frames show PCs / FANUC / UR5e - not "no object" any more
            base = "old__" + os.path.basename(p)
            shutil.copy(p, os.path.join(OUT, "images", sp, base))
            if os.path.exists(lab):
                lines = [l.split() for l in open(lab).read().splitlines() if l.strip()]
                open(os.path.join(OUT, "labels", sp, base.rsplit(".", 1)[0] + ".txt"), "w").write(
                    "".join(f"{old[int(l[0])]} {' '.join(l[1:])}\n" for l in lines))
                for l in lines:
                    n = NAMES[old[int(l[0])]]; cnt.setdefault(n, {}).setdefault(sp, 0); cnt[n][sp] += 1
    # several boxes in one photo (owner's Multi_Boxes, 2026-11-02): no hand labels - the Colab round-2 teacher boxes
    # multi_train before round 2; multi_test is never trained on and is drawn + counted for checking by eye
    ms = sorted(glob.glob(os.path.join(D, "lab_src_multi", "*.jpg")))
    for i, p in enumerate(ms):
        sp = "multi_train" if i < .75 * len(ms) else "multi_test"
        os.makedirs(os.path.join(OUT, "images", sp), exist_ok=True)
        shutil.copy(p, os.path.join(OUT, "images", sp, "multi__" + os.path.basename(p)))
    cnt["multi"] = {"multi_train": sum(1 for i in range(len(ms)) if i < .75 * len(ms)), "multi_test": sum(1 for i in range(len(ms)) if i >= .75 * len(ms))}
    # no-object test photos: held-out COCO + lab-camera frames from before any box existed
    # lab-camera frames (2026-10-12, before any box existed) show the FANUC, ~15 lab PCs and the UR5e from the real
    # camera viewpoint: every 4th one goes to multi_train so the round-2 teacher boxes those objects (no longer negatives)
    lab = sorted(glob.glob(os.path.join(D, "lab_neg", "*.jpg")) + glob.glob(os.path.join(D, "lab_neg_test", "*.jpg")))[::4]
    for p in lab:
        shutil.copy(p, os.path.join(OUT, "images", "multi_train", "labcam__" + os.path.basename(p)))
    cnt["multi"]["multi_train"] += len(lab)
    for p in glob.glob(os.path.join(D, "coco_val", "negtest", "*.jpg")):
        shutil.copy(p, os.path.join(OUT, "images", "test", "neg__" + os.path.basename(p)))
    names = "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES))
    open(os.path.join(OUT, "data.yaml"), "w").write(f"path: /content/lab_r1\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}")
    json.dump({"classes": NAMES, "per_class": cnt}, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(cnt))


if __name__ == "__main__":
    {"extract": extract, "build": build}.get(sys.argv[1], lambda: label(sys.argv[2]))()
