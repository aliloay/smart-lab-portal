"""2026-11-12: training photos FROM the two security cameras (the wide lab view the AR/equipment finder sees).
Step 1 (this script, `extract`): frames from the camera recordings + saved live views, people BLURRED (local yolo26s
person boxes; faces never leave the laptop unblurred), grouped by view (a camera that was moved = new view). One
REFERENCE frame per view gets pre-drawn boxes (live lab model + rough robot/door boxes) for the owner to correct.
Step 2 (`propagate`): the cameras are fixed, so the corrected reference boxes are copied to every frame of its view.
Output: D:/SmartLabData/colab/lab_cam_views/{reference,all}/{images,labels}, classes.txt.  Never committed (people)."""
import glob, json, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(REPO, "backend"))
import cv2  # noqa: E402
import onnxruntime as ort  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

OUT = r"D:\SmartLabData\colab\lab_cam_views"
# 2026-11-17 (lab day): a NEW day's recordings go to their own folder, so the owner-corrected references above are never
# regenerated:  set CAM_VIEWS_DAY=2026-11-17 (recordings in D:\SmartLabData\lab_<day>\recordings, one frame / 15 s);
# the output then defaults to D:\SmartLabData\colab\lab_cam_views_<day> (CAM_VIEWS_OUT overrides it).
DAY = os.environ.get("CAM_VIEWS_DAY", "").strip()
if DAY:
    OUT = os.environ.get("CAM_VIEWS_OUT") or rf"D:\SmartLabData\colab\lab_cam_views_{DAY}"
DAY_REC = os.path.join(r"D:\SmartLabData", f"lab_{DAY}", "recordings") if DAY else ""
DAY_EVERY_S = 15
SV = os.path.join(REPO, "tools", "security_vision")
SNAP = os.path.join(SV, "anchors", "box_snapshots", "2026-10-21_1539")
M = os.path.join(REPO, "backend", "data", "models")
spec = next(s for s in json.load(open(os.path.join(M, "detectors.json"), encoding="utf-8")) if s["file"] == "lab_detector.onnx")
spec = {**spec, "classes": [{**c, "max_instances": 30, "conf": min(c["conf"], 0.3)} for c in spec["classes"]]}
NAMES = [c["name"] for c in sorted(spec["classes"], key=lambda c: c["index"])]
EVERY_S = 40            # one frame every 40 s of video

# Rough fixed boxes per view (x1, y1, x2, y2 as fractions) - starting points ONLY, the owner corrects them.
ROUGH = {
    "cam1_2026-10-12": [("fanuc_robot", .040, .565, .082, .705), ("ur5e_robot", .810, .460, .858, .635)],
    "cam1_2026-10-21": [("fanuc_robot", .102, .595, .140, .745), ("ur5e_robot", .838, .480, .885, .640)],
    "cam2_2026-10-21": [("ur5e_robot", .165, .255, .215, .425), ("fanuc_robot", .848, .330, .888, .445),
                        ("lab_door", .642, .125, .685, .405)],
}
# Starting boxes for the new day's views: the owner's own "Equipment & door boxes" of that day (exported from the
# portal to D:\SmartLabData\lab_<day>\camera_zones.json, fractions of the picture) - robots, door and every PC; the
# 21 Oct rough boxes only when that file is missing. The owner still checks the reference frame before training.
ZONE_CLASS = {"Fanuc": "fanuc_robot", "UR5e": "ur5e_robot", "Door": "lab_door"}
DAY_ZONES = False
if DAY:
    zf = os.path.join(r"D:\SmartLabData", f"lab_{DAY}", "camera_zones.json")
    if os.path.exists(zf):
        DAY_ZONES = True
        for cam in ("1", "2"):
            ROUGH[f"cam{cam}_{DAY}"] = [
                (ZONE_CLASS.get(z["name"], "lab_pc" if z["name"].upper().startswith("PC-") else None),
                 z["x"], z["y"], z["x"] + z["w"], z["y"] + z["h"])
                for z in json.load(open(zf, encoding="utf-8")) if z["cam"] == f"SECCAM_LAB0{cam}"]
            ROUGH[f"cam{cam}_{DAY}"] = [r for r in ROUGH[f"cam{cam}_{DAY}"] if r[0]]
    else:
        ROUGH[f"cam1_{DAY}"] = ROUGH["cam1_2026-10-21"]
        ROUGH[f"cam2_{DAY}"] = ROUGH["cam2_2026-10-21"]

_person = None


def blur_people(img):
    """Blur every person box (yolo26s COCO class 0). Output layout handled for [1,N,6] (x1,y1,x2,y2,score,cls)."""
    global _person
    if _person is None:
        _person = ort.InferenceSession(os.path.join(SV, "models", "yolo26s.onnx"), providers=["CPUExecutionProvider"])
    inp = _person.get_inputs()[0]; S = inp.shape[2] if isinstance(inp.shape[2], int) else 640
    h, w = img.shape[:2]; r = S / max(h, w)
    canvas = np.full((S, S, 3), 114, np.uint8)
    canvas[:int(h * r), :int(w * r)] = cv2.resize(img, (int(w * r), int(h * r)))
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255
    out = _person.run(None, {inp.name: x})[0][0].T          # [8400, 84]: cx, cy, w, h, 80 COCO scores
    keep = out[:, 4] >= 0.2                                   # COCO class 0 = person; low bar, blurring is cheap
    bx = [[float(cx - w_ / 2), float(cy - h_ / 2), float(w_), float(h_)] for cx, cy, w_, h_ in out[keep, :4]]
    sc = out[keep, 4].tolist()
    n = 0
    for i in np.array(cv2.dnn.NMSBoxes(bx, sc, 0.2, 0.5)).flatten() if bx else []:
        x1, y1, bw, bh = bx[i]
        a, b, c, d = [int(v / r) for v in (x1, y1, x1 + bw, y1 + bh)]
        a, b = max(0, a - 10), max(0, b - 10); c, d = min(w, c + 10), min(h, d + 10)
        if c > a and d > b:
            img[b:d, a:c] = cv2.GaussianBlur(img[b:d, a:c], (0, 0), 25); n += 1
    return n


def frames():
    if DAY:                                    # only the new day's two cameras, nothing from the earlier rounds
        for cam in ("1", "2"):
            for f in sorted(glob.glob(os.path.join(DAY_REC, f"SECCAM_LAB0{cam}_{DAY}_*.mp4"))):
                cap = cv2.VideoCapture(f); fps = cap.get(5) or 15; n = int(cap.get(7)); step = max(1, int(fps * DAY_EVERY_S))
                for i in range(step // 2, n, step):
                    cap.set(1, i); ok, im = cap.read()
                    if ok:
                        yield f"cam{cam}_{DAY}", f"c{cam}_{os.path.basename(f)[13:32]}_{i:06d}", im
        return
    for f in sorted(glob.glob(os.path.join(SV, "recordings", "SECCAM_LAB01_2026-10-12_*.mp4"))):
        cap = cv2.VideoCapture(f); fps = cap.get(5) or 15; n = int(cap.get(7)); step = int(fps * EVERY_S)
        for i in range(step // 2, n, step):
            cap.set(1, i); ok, im = cap.read()
            if ok:
                yield "cam1_2026-10-12", f"c1_{os.path.basename(f)[13:32]}_{i:06d}", im
    for cam, view in (("camera1", "cam1_2026-10-21"), ("camera2", "cam2_2026-10-21")):
        for fn in ("plain_view.jpg",):
            im = cv2.imread(os.path.join(SNAP, cam, fn))
            if im is not None:
                yield view, f"{cam}_{fn[:-4]}_2026-10-21", im


def write_labels(path, boxes):
    with open(path, "w") as f:
        for k, (x1, y1, x2, y2) in boxes:
            f.write(f"{k} {(x1+x2)/2:.6f} {(y1+y2)/2:.6f} {x2-x1:.6f} {y2-y1:.6f}\n")


def extract():
    rt = bd._load(os.path.join(M, "lab_detector.onnx"))
    for part in ("reference", "all"):
        for d in ("images", "labels"):
            os.makedirs(os.path.join(OUT, part, d), exist_ok=True)
        open(os.path.join(OUT, part, "classes.txt"), "w").write("\n".join(NAMES) + "\n")
    views, blurred = {}, 0
    for view, name, im in frames():
        blurred += blur_people(im)
        cv2.imwrite(os.path.join(OUT, "all", "images", name + ".jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
        views.setdefault(view, []).append(name)
        if len(views[view]) == 1 or view.startswith("cam1_2026-10-12") and len(views[view]) == 40:
            pass
    ref = {}
    for view, names in views.items():
        name = names[len(names) // 2]           # middle frame of the view = reference
        ref[view] = name
        im = cv2.imread(os.path.join(OUT, "all", "images", name + ".jpg"))
        boxes = []
        for h in bd._infer_multi(rt, spec, im):
            b = h["box"]
            fixed = ("fanuc_robot", "ur5e_robot", "lab_door") + (("lab_pc",) if DAY_ZONES else ())
            if h["class"] not in fixed:             # PCs too come from the owner's boxes when the day has them
                boxes.append((NAMES.index(h["class"]), (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])))
        boxes += [(NAMES.index(c), (a, b, cc, d)) for c, a, b, cc, d in ROUGH.get(view, [])]
        shutil.copy2(os.path.join(OUT, "all", "images", name + ".jpg"), os.path.join(OUT, "reference", "images"))
        write_labels(os.path.join(OUT, "reference", "labels", name + ".txt"), boxes)
    json.dump({"views": views, "reference": ref}, open(os.path.join(OUT, "views.json"), "w"), indent=1)
    print(json.dumps({v: len(n) for v, n in views.items()}), "frames; people blurred:", blurred, "; references:", ref)


def propagate():
    meta = json.load(open(os.path.join(OUT, "views.json")))
    total = 0
    for view, names in meta["views"].items():
        src = os.path.join(OUT, "reference", "labels", meta["reference"][view] + ".txt")
        for n in names:
            shutil.copy2(src, os.path.join(OUT, "all", "labels", n + ".txt")); total += 1
    print("labels copied to", total, "frames")


if __name__ == "__main__":
    {"extract": extract, "propagate": propagate}[sys.argv[1] if len(sys.argv) > 1 else "extract"]()
