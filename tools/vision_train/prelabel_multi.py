"""Pre-label the 152 multi-object photos (data/lab_src_multi) with the deployed lab_detector at its live thresholds, as
YOLO .txt files for HUMAN CORRECTION (labelImg / Roboflow / CVAT: open the folder, fix boxes, add missed objects).
These are proposals, never ground truth. Output: data/lab_multi_prelabel/{images,labels,classes.txt,prelabel_stats.json}"""
import glob, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402
M = os.path.join(HERE, "..", "..", "backend", "data", "models")
OUT = os.path.join(HERE, "data", "lab_multi_prelabel")
spec = next(s for s in json.load(open(os.path.join(M, "detectors.json"), encoding="utf-8")) if s["file"] == "lab_detector.onnx")
spec = {**spec, "classes": [{**c, "max_instances": 8} for c in spec["classes"]]}
rt = bd._load(os.path.join(M, "lab_detector.onnx"))
os.makedirs(os.path.join(OUT, "images"), exist_ok=True); os.makedirs(os.path.join(OUT, "labels"), exist_ok=True)
names = [c["name"] for c in sorted(spec["classes"], key=lambda c: c["index"])]
open(os.path.join(OUT, "classes.txt"), "w").write("\n".join(names) + "\n")
per_photo, per_class = [], {}
SRC = sorted(glob.glob(os.path.join(HERE, "data", "lab_src_multi", "**", "*.*"), recursive=True)
             + glob.glob(os.path.join(HERE, "data", "lab_src_multi2", "*.jpg")))   # 2026-11-12: + Multi_Boxes (120)
for p in SRC:
    if os.path.splitext(p)[1].lower() not in (".jpg", ".jpeg", ".png"):
        continue
    img = cv2.imread(p)
    if img is None:
        continue
    base = os.path.splitext(os.path.basename(p))[0]
    shutil.copy2(p, os.path.join(OUT, "images", os.path.basename(p)))
    hits = bd._infer_multi(rt, spec, img)
    with open(os.path.join(OUT, "labels", base + ".txt"), "w") as f:
        for h in hits:
            b = h["box"]; k = names.index(h["class"])
            f.write(f"{k} {b['x'] + b['w']/2:.6f} {b['y'] + b['h']/2:.6f} {b['w']:.6f} {b['h']:.6f}\n")
            per_class[h["class"]] = per_class.get(h["class"], 0) + 1
    per_photo.append(len(hits))
stats = {"photos": len(per_photo), "proposed_boxes": sum(per_photo),
         "photos_by_box_count": {str(n): per_photo.count(n) for n in sorted(set(per_photo))}, "per_class": per_class}
json.dump(stats, open(os.path.join(OUT, "prelabel_stats.json"), "w"), indent=1); print(json.dumps(stats))
