"""2026-11-17 (lab day): Round 8 dataset = lab_v6b (the v7 training set, unchanged) + the 17 Nov lab day -> lab_v8.zip.

  base        D:/SmartLabData/colab/lab_v6b as-is (train/val/test/test_multi/cam_test), hard-linked (same disk, no copy).
  day photos  data/lab_day_2026-11-17_prelabel: 15 FANUC + 11 node photos, owner-corrected in labelImg (the consumables
              node added in all 11). Every 3rd photo of each folder -> test_day (held out), the rest -> train.
  day frames  D:/SmartLabData/colab/lab_cam_views_2026-11-17: 49 frames per camera (people blurred), boxes copied from
              each camera's reference frame (= the owner's portal Equipment & door boxes of that morning). The LAST 10
              frames of each recording -> cam_test_day, the rest -> train (neighbouring frames never cross).
The old test sets stay identical, so v8 is scored against v7 on exactly the same pictures plus the two new day tests.
Nothing here is committed (pictures of the lab and blurred people stay on D: / the owner's Drive).
    backend\\.venv\\Scripts\\python build_v8_dataset.py
"""
import json, os, shutil, sys, zipfile

DAY = "2026-11-17"
BASE = r"D:\SmartLabData\colab\lab_v6b"
TAG = "lab_v8"
OUT = os.path.join(r"D:\SmartLabData\colab", TAG)
ZIP = OUT + ".zip"
DRIVE_DIR = r"G:\My Drive\SmartLab"
PHOTOS = os.path.join(r"D:\SmartLabData\vision_train_data", f"lab_day_{DAY}_prelabel")
VIEWS = os.path.join(r"D:\SmartLabData\colab", f"lab_cam_views_{DAY}")
CAM_TEST_LAST = 10


def link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def add(img, lbl_lines, split, name):
    link(img, os.path.join(OUT, "images", split, name + os.path.splitext(img)[1].lower()))
    with open(os.path.join(OUT, "labels", split, name + ".txt"), "w") as f:
        f.writelines(l if l.endswith("\n") else l + "\n" for l in lbl_lines if l.strip())


def main():
    if os.path.exists(OUT) or os.path.exists(ZIP):
        sys.exit(f"{OUT} or its zip already exists - rename it first (this script never deletes)")
    for root, _, files in os.walk(BASE):                       # 1) the v7 dataset, untouched
        for fn in files:
            src = os.path.join(root, fn)
            link(src, os.path.join(OUT, os.path.relpath(src, BASE)))
    for split in ("test_day", "cam_test_day"):
        os.makedirs(os.path.join(OUT, "images", split), exist_ok=True)
        os.makedirs(os.path.join(OUT, "labels", split), exist_ok=True)
    stats = {"day": DAY, "photos": {"train": 0, "test_day": 0}, "frames": {"train": 0, "cam_test_day": 0}, "boxes": {}}
    names = [l.strip() for l in open(os.path.join(PHOTOS, "classes.txt")) if l.strip()]
    # 2) the day's phone photos: every 3rd of each folder held out
    groups = {}
    for fn in sorted(os.listdir(os.path.join(PHOTOS, "images"))):
        groups.setdefault(fn.split("_")[1], []).append(fn)    # d20261117_<fanuc|node>_...
    for g, fns in groups.items():
        for i, fn in enumerate(fns):
            stem = os.path.splitext(fn)[0]
            lines = open(os.path.join(PHOTOS, "labels", stem + ".txt")).read().splitlines()
            split = "test_day" if i % 3 == 2 else "train"
            add(os.path.join(PHOTOS, "images", fn), lines, split, stem)
            stats["photos"][split] += 1
            for l in lines:
                if l.strip():
                    k = names[int(l.split()[0])]; stats["boxes"][k] = stats["boxes"].get(k, 0) + 1
    # 3) the day's camera frames: reference boxes, last frames of each recording held out
    meta = json.load(open(os.path.join(VIEWS, "views.json")))
    for view, frames in meta["views"].items():
        ref = open(os.path.join(VIEWS, "reference", "labels", meta["reference"][view] + ".txt")).read().splitlines()
        frames = sorted(frames)
        for i, n in enumerate(frames):
            split = "cam_test_day" if i >= len(frames) - CAM_TEST_LAST else "train"
            add(os.path.join(VIEWS, "all", "images", n + ".jpg"), ref, split, f"cam_{n}")
            stats["frames"][split] += 1
    y = open(os.path.join(BASE, "data.yaml")).read().replace("path: /content/lab_v6", f"path: /content/{TAG}")
    with open(os.path.join(OUT, "data.yaml"), "w") as f:
        f.write(y)
    for split in sorted(os.listdir(os.path.join(OUT, "images"))):
        stats.setdefault("splits", {})[split] = len(os.listdir(os.path.join(OUT, "images", split)))
    with open(os.path.join(OUT, "summary_v8.json"), "w") as f:
        json.dump(stats, f, indent=1)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_STORED) as z:  # jpgs do not compress; stored = fast
        for root, _, files in os.walk(OUT):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, TAG + "/" + os.path.relpath(p, OUT).replace(os.sep, "/"))
    stats["zip_mb"] = os.path.getsize(ZIP) // 2**20
    if os.path.isdir(DRIVE_DIR):
        shutil.copy2(ZIP, os.path.join(DRIVE_DIR, TAG + ".zip"))
        stats["drive"] = os.path.join(DRIVE_DIR, TAG + ".zip")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
