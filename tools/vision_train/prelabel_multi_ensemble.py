"""2026-11-12: second-opinion pre-labels for the multi-object photos. Two different models (deployed v2 r2_s and the old
v2 r1_n) each propose boxes; a box both agree on (same class, IoU >= 0.5) is AGREED, anything only one model sees is a
DOUBT. Labels = agreed boxes (r2_s geometry) + doubts, so nothing is lost; REVIEW_LIST.txt ranks photos by doubts so a
human checks ~the worst third instead of every photo. Still proposals, never ground truth (a model cannot grade itself).
Output: D:/SmartLabData/colab/lab_multi_prelabel_v2/{images,labels,classes.txt,REVIEW_LIST.txt,stats.json}
Usage: python prelabel_multi_ensemble.py [old_model.onnx]"""
import glob, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

M = os.path.join(HERE, "..", "..", "backend", "data", "models")
OLD = sys.argv[1] if len(sys.argv) > 1 else r"D:\SmartLabData\model_backups\lab_detector_v2_r1_n_2026-11-12.onnx"
OUT = r"D:\SmartLabData\colab\lab_multi_prelabel_v2"
spec = next(s for s in json.load(open(os.path.join(M, "detectors.json"), encoding="utf-8")) if s["file"] == "lab_detector.onnx")
spec = {**spec, "classes": [{**c, "max_instances": 8} for c in spec["classes"]]}
names = [c["name"] for c in sorted(spec["classes"], key=lambda c: c["index"])]
models = {"r2_s": bd._load(os.path.join(M, "lab_detector.onnx")), "r1_n": bd._load(OLD)}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0.0


def boxes(rt, img):
    out = []
    for h in bd._infer_multi(rt, spec, img):
        b = h["box"]
        out.append((names.index(h["class"]), (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])))
    return out


for d in ("images", "labels"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
open(os.path.join(OUT, "classes.txt"), "w").write("\n".join(names) + "\n")
SRC = sorted(glob.glob(os.path.join(HERE, "data", "lab_src_multi", "**", "*.*"), recursive=True)
             + glob.glob(os.path.join(HERE, "data", "lab_src_multi2", "*.jpg")))
review, agreed_n, doubt_n, per_class = [], 0, 0, {}
for p in SRC:
    if os.path.splitext(p)[1].lower() not in (".jpg", ".jpeg", ".png"):
        continue
    img = cv2.imread(p)
    if img is None:
        continue
    base = os.path.splitext(os.path.basename(p))[0]
    shutil.copy2(p, os.path.join(OUT, "images", os.path.basename(p)))
    a, b = boxes(models["r2_s"], img), boxes(models["r1_n"], img)
    used, keep, doubts = set(), [], []
    for k, g in a:
        m = max(((iou(g, q[1]), j) for j, q in enumerate(b) if q[0] == k and j not in used), default=(0, None))
        if m[0] >= 0.5:
            used.add(m[1]); keep.append((k, g))
        else:
            doubts.append((k, g, "only r2_s"))
    doubts += [(k, g, "only r1_n") for j, (k, g) in enumerate(b) if j not in used]
    with open(os.path.join(OUT, "labels", base + ".txt"), "w") as f:
        for k, g in keep + [(k, g) for k, g, _ in doubts]:
            f.write(f"{k} {(g[0]+g[2])/2:.6f} {(g[1]+g[3])/2:.6f} {g[2]-g[0]:.6f} {g[3]-g[1]:.6f}\n")
            per_class[names[k]] = per_class.get(names[k], 0) + 1
    agreed_n += len(keep); doubt_n += len(doubts)
    review.append((len(doubts), os.path.basename(p), ", ".join(f"{names[k]} ({w})" for k, _, w in doubts)))

review.sort(key=lambda r: -r[0])
with open(os.path.join(OUT, "REVIEW_LIST.txt"), "w", encoding="utf-8") as f:
    f.write("Photos where the two models disagree - check these first (also add objects BOTH missed: PCs, robots, door).\n\n")
    for n, name, why in review:
        if n:
            f.write(f"{n}  {name}: {why}\n")
stats = {"photos": len(review), "agreed_boxes": agreed_n, "doubt_boxes": doubt_n,
         "photos_to_review": sum(1 for r in review if r[0]), "per_class": per_class}
json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1)
print(json.dumps(stats))
