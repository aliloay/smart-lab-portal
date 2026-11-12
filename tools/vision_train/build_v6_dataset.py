"""2026-11-12: Round 6 - ONE dataset from every lab photo on this laptop -> lab_v6.zip (Linux-safe paths) on Drive.

  base       lab_r1 train/val/test as-is, EXCEPT the 397 full security-camera frames in train/old__neg_* that were
             labelled "empty" although robots and PCs are in view (they taught every model that far-away robots/PCs
             are background). The COCO-style empty photos stay (false-alarm training) and test/neg* stays the
             false-alarm test.
  multi      272 human-corrected multi-object photos (lab_multi_prelabel, 977 boxes), split by capture session
             70 % train / 30 % test_multi.
  single+    photos in lab_src/<class>/ not yet in any set: the class is known from the folder, the box is the live
             model's best box OF THAT CLASS (conf >= 0.15); no such box -> skipped and listed. Train only, and any photo
             that looks like a test photo (dHash distance <= 6) is dropped so the fair test stays fair.
  cam        security-camera frames with boxes copied from the owner-checked reference frame of each view - included
             only when D:/SmartLabData/colab/lab_cam_views/REVIEWED exists (make_cam_views.py). 80 % train / 20 % cam_test,
             split by recording so neighbouring frames never cross.
Images of people: only camera frames, already blurred by make_cam_views.py. Nothing here is committed.
    python build_v6_dataset.py            (backend venv: needs cv2, onnxruntime)"""
import glob, hashlib, json, os, random, re, shutil, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

D = r"D:\SmartLabData\vision_train_data"
R1 = os.path.join(D, "lab_r1")
MULTI = r"D:\SmartLabData\colab\lab_multi_prelabel"
CAM = r"D:\SmartLabData\colab\lab_cam_views"
OUT = r"D:\SmartLabData\colab\lab_v6"
ZIP = r"D:\SmartLabData\colab\lab_v6.zip"
DRIVE = r"G:\My Drive\SmartLab\lab_v6.zip"
M = os.path.join(HERE, "..", "..", "backend", "data", "models")
NAMES = ['reusable_bin', 'consumables_node', 'environment_node', 'master_node', 'network_switch', 'network_router',
         'ur5e_robot', 'ur5e_teach_pendant', 'fanuc_robot', 'fanuc_teach_pendant', 'lab_pc', 'lab_door']
IMG = (".jpg", ".jpeg", ".png")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def dhash(p):
    im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    s = cv2.resize(im, (9, 8))
    return np.packbits((s[:, 1:] > s[:, :-1]).flatten())


def ham(a, b):
    return int(np.unpackbits(a ^ b).sum())


def put(src, split, name, label_lines):
    shutil.copy2(src, os.path.join(OUT, "images", split, name))
    if label_lines is not None:
        with open(os.path.join(OUT, "labels", split, os.path.splitext(name)[0] + ".txt"), "w") as f:
            f.write("".join(label_lines))


if os.path.exists(OUT):
    shutil.rmtree(OUT)
SPLITS = ("train", "val", "test", "test_multi", "cam_test")
for s in SPLITS:
    os.makedirs(os.path.join(OUT, "images", s)); os.makedirs(os.path.join(OUT, "labels", s))
stats = {"dropped_camera_frames_marked_empty": 0, "multi_train": 0, "multi_test": 0, "multi_dup": 0,
         "single_added": {}, "single_skipped_no_box": [], "single_dropped_like_test": 0, "cam_train": 0, "cam_test": 0}
seen = set()

# 1. base
for s in ("train", "val", "test"):
    for p in sorted(glob.glob(os.path.join(R1, "images", s, "*"))):
        n = os.path.basename(p)
        if s == "train" and n.startswith("old__neg_"):
            im = cv2.imread(p)
            if im is not None and im.shape[:2] == (1296, 2304):
                stats["dropped_camera_frames_marked_empty"] += 1
                continue
        lp = os.path.join(R1, "labels", s, os.path.splitext(n)[0] + ".txt")
        put(p, s, n, open(lp).readlines() if os.path.exists(lp) else None)
        seen.add(md5(p))
test_hash = [h for h in (dhash(p) for p in glob.glob(os.path.join(R1, "images", "test", "*"))) if h is not None]


# 2. multi (human-corrected), split by capture session
def session(n):
    m = re.match(r"mb_IMG_(\d+)", n)
    if m:
        return f"mb{int(m.group(1)) // 4}"
    m = re.match(r"([a-z]+)(\d+)", n)
    return f"{m.group(1)}{int(m.group(2)) // 10}" if m else n


mimgs = sorted(p for p in glob.glob(os.path.join(MULTI, "images", "*")) if p.lower().endswith(IMG))
sess = sorted({session(os.path.basename(p)) for p in mimgs})
random.Random(6).shuffle(sess)
test_s = set(sess[: round(len(sess) * 0.30)])
for p in mimgs:
    h = md5(p)
    if h in seen:
        stats["multi_dup"] += 1
        continue
    seen.add(h)
    n = os.path.basename(p); lp = os.path.join(MULTI, "labels", os.path.splitext(n)[0] + ".txt")
    split = "test_multi" if session(n) in test_s else "train"
    put(p, split, "m_" + n, open(lp).readlines())
    stats["multi_test" if split == "test_multi" else "multi_train"] += 1

# 3. new single-object photos, class from the folder, box from the live model
spec = next(s for s in json.load(open(os.path.join(M, "detectors.json"), encoding="utf-8")) if s["file"] == "lab_detector.onnx")
spec = {**spec, "classes": [{**c, "conf": 0.15, "max_instances": 5} for c in spec["classes"]]}
rt = bd._load(os.path.join(M, "lab_detector.onnx"))
for cls in NAMES:
    for p in sorted(glob.glob(os.path.join(D, "lab_src", cls, "**", "*"), recursive=True)):
        if not p.lower().endswith(IMG) or "__MACOSX" in p:
            continue
        h = md5(p)
        if h in seen:
            continue
        dh = dhash(p)
        if dh is None:
            continue
        if any(ham(dh, t) <= 6 for t in test_hash):
            stats["single_dropped_like_test"] += 1; seen.add(h)
            continue
        img = cv2.imread(p)
        hits = [x for x in bd._infer_multi(rt, spec, img) if x["class"] == cls]
        if not hits:
            stats["single_skipped_no_box"].append(f"{cls}/{os.path.basename(p)}")
            continue
        b = max(hits, key=lambda x: x.get("confidence", 0))["box"]
        seen.add(h)
        put(p, "train", f"s6_{cls}__{os.path.basename(p)}",
            [f"{NAMES.index(cls)} {b['x'] + b['w']/2:.6f} {b['y'] + b['h']/2:.6f} {b['w']:.6f} {b['h']:.6f}\n"])
        stats["single_added"][cls] = stats["single_added"].get(cls, 0) + 1

# 4. camera views (only after the owner checked the reference boxes)
if os.path.exists(os.path.join(CAM, "REVIEWED")):
    meta = json.load(open(os.path.join(CAM, "views.json")))
    for view, names in meta["views"].items():
        ref = open(os.path.join(CAM, "reference", "labels", meta["reference"][view] + ".txt")).readlines()
        recs = sorted({re.sub(r"_\d{6}$", "", n) for n in names})          # one recording = one group
        test_recs = set(recs[-max(1, len(recs) // 5):]) if len(recs) >= 3 else set()
        for i, n in enumerate(names):
            rec = re.sub(r"_\d{6}$", "", n)
            split = "cam_test" if (rec in test_recs or (not test_recs and i % 5 == 4)) else "train"
            put(os.path.join(CAM, "all", "images", n + ".jpg"), split, "c6_" + n + ".jpg", ref)
            stats["cam_test" if split == "cam_test" else "cam_train"] += 1
else:
    stats["cam_note"] = "camera frames NOT included (reference boxes not reviewed yet - FIX_CAMERA_BOXES.bat)"

open(os.path.join(OUT, "data.yaml"), "w").write(
    "path: /content/lab_v6\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n"
    + "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES)))
counts = {}
for s in SPLITS:
    imgs = os.listdir(os.path.join(OUT, "images", s)); labs = glob.glob(os.path.join(OUT, "labels", s, "*.txt"))
    boxes = sum(len([l for l in open(f) if l.strip()]) for f in labs)
    counts[s] = {"photos": len(imgs), "labelled": len(labs), "boxes": boxes}
stats["splits"] = counts
json.dump(stats, open(os.path.join(OUT, "summary.json"), "w"), indent=1)

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_STORED) as z:          # jpgs do not compress; stored = fast
    for root, _, files in os.walk(OUT):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, "lab_v6/" + os.path.relpath(full, OUT).replace(os.sep, "/"))
shutil.copy2(ZIP, DRIVE)
print(json.dumps({k: v for k, v in stats.items() if k != "single_skipped_no_box"}, indent=1))
print("skipped (no box of the folder's class):", len(stats["single_skipped_no_box"]), "| zip", os.path.getsize(ZIP) // 2**20, "MB ->", DRIVE)
