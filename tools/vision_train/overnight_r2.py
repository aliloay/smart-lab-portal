"""Overnight lab-detector round 2 (2026-11-03): the owner's 6 new training videos (Trian_videos.zip) + today's 416
lab-camera captures, pre-labelled by the LIVE model (r1_n), added to the hand-checked lab_r1 train set; trained from
r1_n; both models scored on lab_r1's untouched TEST split (hand-checked). Nothing is deployed here - the report says
whether the candidate is better, and the contact sheets show the pre-labels for review (a wrong box teaches wrong).
    .venv\\Scripts\\python.exe -I overnight_r2.py
Writes data/lab_r2/ (dataset, sheets, report.txt, lab_detector_r2.onnx) and data/lab_r2/done.txt."""
import glob
import json
import os
import shutil
import zipfile

import cv2
from PIL import Image, ImageDraw
from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "data", "lab_r1")
OUT = os.path.join(HERE, "data", "lab_r2")
BASE = os.path.join(HERE, "results", "lab_2026-11-02_1731", "drive", "lab_2026-11-02_1731", "r1_n", "weights", "best.pt")
ZIP = r"C:\Users\dell\Downloads\lab_drive_2026-11-03\Trian_videos.zip"
CAPS = r"C:\Users\dell\OneDrive\Desktop\Bsc\lab_captures_2026-11-03"
EVERY_S, CONF, EPOCHS = 1.0, 0.5, 30


def log(*a):
    print(*a, flush=True)
    with open(os.path.join(OUT, "report.txt"), "a", encoding="utf-8") as f:
        print(*a, file=f)


def frames():
    src = os.path.join(OUT, "raw")
    os.makedirs(src, exist_ok=True)
    vids = os.path.join(OUT, "videos")
    with zipfile.ZipFile(ZIP) as z:
        for n in z.namelist():
            if n.lower().endswith(".mov") and "__MACOSX" not in n:
                z.extract(n, vids)
    n = 0
    for v in sorted(glob.glob(os.path.join(vids, "**", "*.MOV"), recursive=True)):
        cap = cv2.VideoCapture(v)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        step, i = max(1, int(fps * EVERY_S)), 0
        while True:
            ok, im = cap.read()
            if not ok:
                break
            if i % step == 0:
                h, w = im.shape[:2]
                s = 1280 / max(h, w)
                if s < 1:
                    im = cv2.resize(im, (int(w * s), int(h * s)))
                cv2.imwrite(os.path.join(src, f"{os.path.splitext(os.path.basename(v))[0]}_{i:05d}.jpg"), im)
                n += 1
            i += 1
        cap.release()
    for p in sorted(glob.glob(os.path.join(CAPS, "*_raw_*.jpg"))):       # camera views, no boxes drawn
        shutil.copy(p, os.path.join(src, "cap_" + os.path.basename(p)))
        n += 1
    log(f"frames: {n} (videos every {EVERY_S}s + lab-camera captures)")
    return src


def prelabel(src):
    m = YOLO(BASE)
    img_dir, lab_dir = os.path.join(OUT, "pseudo", "images"), os.path.join(OUT, "pseudo", "labels")
    os.makedirs(img_dir, exist_ok=True); os.makedirs(lab_dir, exist_ok=True)
    kept, per_class, sheet = 0, {}, []
    for p in sorted(glob.glob(os.path.join(src, "*.jpg"))):
        r = m.predict(p, conf=CONF, imgsz=640, device="cpu", verbose=False)[0]
        if not len(r.boxes):
            continue
        lines = []
        for c, b in zip(r.boxes.cls.tolist(), r.boxes.xywhn.tolist()):
            lines.append(f"{int(c)} " + " ".join(f"{v:.6f}" for v in b))
            per_class[m.names[int(c)]] = per_class.get(m.names[int(c)], 0) + 1
        base = os.path.splitext(os.path.basename(p))[0]
        shutil.copy(p, os.path.join(img_dir, base + ".jpg"))
        with open(os.path.join(lab_dir, base + ".txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        sheet.append((p, r.boxes.xyxyn.tolist(), [m.names[int(c)] for c in r.boxes.cls.tolist()]))
        kept += 1
    log(f"pre-labelled frames kept: {kept}; boxes per class: {json.dumps(per_class)}")
    tile = 240
    for k in range(0, len(sheet), 40):                                    # contact sheets for the morning review
        part = sheet[k:k + 40]
        sh = Image.new("RGB", (8 * tile, ((len(part) + 7) // 8) * (tile + 14)), "white")
        d = ImageDraw.Draw(sh)
        for i, (p, boxes, names) in enumerate(part):
            im = Image.open(p); im.thumbnail((tile, tile)); w, h = im.size
            x, y = (i % 8) * tile, (i // 8) * (tile + 14)
            sh.paste(im, (x, y))
            for b, nm in zip(boxes, names):
                d.rectangle([x + b[0] * w, y + b[1] * h, x + b[2] * w, y + b[3] * h], outline="lime", width=2)
                d.text((x + b[0] * w + 2, y + b[1] * h + 1), nm[:14], fill="yellow")
            d.text((x + 3, y + tile + 1), os.path.basename(p)[:30], fill="black")
        sh.save(os.path.join(OUT, f"sheet_{k // 40:02d}.jpg"), quality=80)
    return kept


def dataset():
    ds = os.path.join(OUT, "ds")
    for split in ("train", "val", "test"):
        for kind in ("images", "labels"):
            src = os.path.join(R1, kind, split)
            dst = os.path.join(ds, kind, split)
            if os.path.isdir(src) and not os.path.isdir(dst):
                shutil.copytree(src, dst)
    for kind in ("images", "labels"):                                     # pre-labels: TRAIN only
        for p in glob.glob(os.path.join(OUT, "pseudo", kind, "*")):
            shutil.copy(p, os.path.join(ds, kind, "train", "r2_" + os.path.basename(p)))
    names = YOLO(BASE).names
    with open(os.path.join(ds, "data.yaml"), "w") as f:
        f.write(f"path: {ds}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n")
        for i in sorted(names):
            f.write(f"  {i}: {names[i]}\n")
    log(f"dataset: train {len(os.listdir(os.path.join(ds, 'images', 'train')))}, test (hand-checked, untouched) "
        f"{len(os.listdir(os.path.join(ds, 'images', 'test')))}")
    return os.path.join(ds, "data.yaml")


def score(weights, data, tag):
    r = YOLO(weights).val(data=data, split="test", imgsz=640, device="cpu", workers=0, plots=False, verbose=False,
                          project=os.path.join(OUT, "val"), name=tag, exist_ok=True)
    log(f"{tag}: test mAP50 {r.box.map50:.3f}  mAP50-95 {r.box.map:.3f}  P {r.box.mp:.3f}  R {r.box.mr:.3f}")
    return r.box.map


def smart_lab_running() -> bool:
    """Portal (8000) or a camera service (5100/5101) answering on this laptop (Gemini ACT-01 guard)."""
    import socket
    for port in (8000, 5100, 5101):
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
    return False


def main():
    os.makedirs(OUT, exist_ok=True)
    if smart_lab_running() and os.environ.get("SMARTLAB_TRAIN_ANYWAY") != "1":
        log("ABORTED: Smart Lab is running on this laptop - local CPU training next to the portal and cameras "
            "overloads the 16 GB. Train on Colab (colab_2026-11-03), or stop Smart Lab first.")
        return
    log("=== overnight round 2 started ===")
    kept = prelabel(frames())
    data = dataset()
    old = score(BASE, data, "r1_n_live")
    if kept == 0:
        log("no pre-labelled frames - nothing to train"); return
    YOLO(BASE).train(data=data, epochs=EPOCHS, imgsz=640, batch=8, device="cpu", workers=0, project=os.path.join(OUT, "runs"),
                     name="r2", exist_ok=True, plots=False, verbose=False, seed=0, patience=10,
                     fliplr=0.5, degrees=10, scale=0.6, mosaic=1.0, hsv_v=0.5)
    best = os.path.join(OUT, "runs", "r2", "weights", "best.pt")
    new = score(best, data, "r2_candidate")
    onnx = YOLO(best).export(format="onnx", imgsz=640)
    shutil.copy(onnx, os.path.join(OUT, "lab_detector_r2.onnx"))
    log(f"VERDICT: candidate {'BETTER' if new > old + 0.005 else 'NOT better'} than live "
        f"(mAP50-95 {new:.3f} vs {old:.3f}). Not deployed - review sheet_*.jpg first; deploy = copy "
        f"lab_detector_r2.onnx to backend/data/models/lab_detector.onnx (backup the old one).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FAILED: {e!r}")
        raise
    finally:
        open(os.path.join(OUT, "done.txt"), "w").write("done\n")
