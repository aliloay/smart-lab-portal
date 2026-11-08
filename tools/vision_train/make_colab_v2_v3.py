"""Colab packages v2 + v3 (2026-11-03). Zips are written with forward slashes (a Windows .NET zip used backslashes and
Colab unpacked 'lab_r1\\data.yaml' as one file name - the v2 run failed on that).
  v2 = lab_r1 (hand-checked) + 81 frames from today pre-labelled by the live model (train only).
  v3 = v2 + every remaining frame of today (6 new videos, 416 security-camera captures) + the 8 QR photos + the QR
       walkthrough video frames, put in multi_train WITHOUT labels: the notebook's round-1 teacher (YOLO11s, >= 0.6) boxes
       them, exactly as it does the owner's multi-box photos. Test split untouched (hand-checked) - fair comparison.
    .venv\\Scripts\\python.exe -I make_colab_v2_v3.py
"""
import glob
import json
import os
import zipfile

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "data", "lab_r1")
R2 = os.path.join(HERE, "data", "lab_r2")
OUT = r"C:\Users\dell\OneDrive\Desktop\Bsc\colab_2026-11-03"
QR = r"C:\Users\dell\OneDrive\Desktop\Bsc\lab_qr_2026-11-03"
NB = os.path.join(HERE, "colab_object", "SmartLab_train_lab.ipynb")


def add_tree(z, root, arc_root):
    n = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            z.write(p, (arc_root + "/" + os.path.relpath(p, root).replace("\\", "/")))
            n += 1
    return n


def qr_frames():
    out = os.path.join(R2, "qr_frames")
    os.makedirs(out, exist_ok=True)
    for v in glob.glob(os.path.join(QR, "*.mov")):
        cap = cv2.VideoCapture(v); fps = cap.get(cv2.CAP_PROP_FPS) or 30; i = 0
        while True:
            ok, im = cap.read()
            if not ok:
                break
            if i % int(fps) == 0:
                h, w = im.shape[:2]; s = 1280 / max(h, w)
                if s < 1:
                    im = cv2.resize(im, (int(w * s), int(h * s)))
                cv2.imwrite(os.path.join(out, f"qrvid_{i:05d}.jpg"), im)
            i += 1
        cap.release()
    return sorted(glob.glob(os.path.join(out, "*.jpg"))) + sorted(glob.glob(os.path.join(QR, "*.jpg")))


def build(name, extra_multi):
    zp = os.path.join(OUT, f"SmartLab_lab_{name}_dataset.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:            # jpgs are compressed already: fast
        n = add_tree(z, R1, "lab_r1")
        for kind in ("images", "labels"):
            for p in glob.glob(os.path.join(R2, "pseudo", kind, "*")):
                z.write(p, f"lab_r1/{kind}/train/r2_{os.path.basename(p)}"); n += 1
        for p in extra_multi:
            z.write(p, f"lab_r1/images/multi_train/{name}_{os.path.basename(p)}"); n += 1
    print(name, zp, n, "files", round(os.path.getsize(zp) / 2**20), "MB")


def notebook(name, sizes):
    nb = json.load(open(NB, encoding="utf-8"))
    for c in nb["cells"]:
        s = "".join(c["source"])
        s = s.replace("SmartLab_lab_r1_dataset*.zip", f"SmartLab_lab_{name}_dataset*.zip")
        s = s.replace("SmartLab_lab_r1_dataset.zip", f"SmartLab_lab_{name}_dataset.zip")
        s = s.replace("SmartLab_results/lab_", f"SmartLab_results/lab_{name}_")
        # unpack robustly: a zip made on Windows may hold backslash paths
        s = s.replace("zipfile.ZipFile(zs[0]).extractall('/content')",
                      "zf = zipfile.ZipFile(zs[0])\nfor m in zf.infolist():\n    m.filename = m.filename.replace('\\\\', '/')\n"
                      "    zf.extract(m, '/content')")
        if sizes != ("n", "s"):
            s = s.replace("for s in ('n', 's')", f"for s in {sizes!r}")
            s = s.replace("('r1_n', 'r1_s', 'r2_n', 'r2_s')", repr(tuple(f"r{r}_{k}" for r in (1, 2) for k in sizes)))
        c["source"] = s.splitlines(keepends=True)
    if name == "v3":
        nb["cells"][0]["source"] = [
            "# Smart Lab v3 - every lab object, more data, n / s / m compared (Colab GPU)\n",
            "1. Upload **SmartLab_lab_v3_dataset.zip** to Google Drive. 2. Runtime -> Change runtime type -> **T4 GPU**.\n",
            "3. **Runtime -> Run all**, allow Drive. About 2-3 h (three sizes, two rounds). Keep the tab open.\n\n",
            "v3 = v2 + all of today's frames (new videos, security cameras, QR photos/video) boxed by the round-1 teacher.\n",
            "Same hand-checked test split as v1/v2, so the scores compare directly. Best = highest mAP50-95; the portal\n",
            "detector runs on a CPU, so the report's per-model speed matters too (n fastest, m most accurate).\n"]
    p = os.path.join(OUT, f"SmartLab_train_lab_{name}.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), indent=1)
    print("notebook", p)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build("v2", [])
    notebook("v2", ("n", "s"))
    kept = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(R2, "pseudo", "images", "*"))}
    rest = [p for p in sorted(glob.glob(os.path.join(R2, "raw", "*.jpg"))) if os.path.basename(p)[:-4] not in kept]
    extra = rest + qr_frames()
    print("v3 extra frames for the teacher:", len(extra))
    build("v3", extra)
    notebook("v3", ("n", "s", "m"))
