"""Pre-label one lab day's phone photos (2026-11-17: 15 FANUC + 11 node photos) with the deployed lab_detector, as YOLO
.txt files for HUMAN CORRECTION in labelImg. Proposals only, never ground truth.

Writes ONLY to its own folder, data/lab_day_<day>_prelabel/{images,labels,classes.txt,prelabel_stats.json}; it never
touches data/lab_multi_prelabel (the owner's 977 corrected boxes). Re-running skips photos that already have a label
file, so corrections made in labelImg are never overwritten.
Photos are re-encoded (no EXIF, so no GPS or phone data) and shrunk to 1280 px on the long side. Some node photos show
hands/legs (no faces): they stay on D: and are never committed.
    backend\\.venv\\Scripts\\python prelabel_day.py 2026-11-17 D:\\SmartLabData\\lab_2026-11-17\\fanuc_photos D:\\SmartLabData\\lab_2026-11-17\\node_photos
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

MAX_SIDE = 1280


def main(day: str, folders: list[str]) -> dict:
    m = os.path.join(HERE, "..", "..", "backend", "data", "models")
    out = os.path.join(HERE, "data", f"lab_day_{day}_prelabel")
    spec = next(s for s in json.load(open(os.path.join(m, "detectors.json"), encoding="utf-8"))
                if s["file"] == "lab_detector.onnx")
    spec = {**spec, "classes": [{**c, "max_instances": 8} for c in spec["classes"]]}
    rt = bd._load(os.path.join(m, "lab_detector.onnx"))
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    os.makedirs(os.path.join(out, "labels"), exist_ok=True)
    names = [c["name"] for c in sorted(spec["classes"], key=lambda c: c["index"])]
    with open(os.path.join(out, "classes.txt"), "w") as f:
        f.write("\n".join(names) + "\n")
    per_photo, per_class, kept = [], {}, 0
    for folder in folders:
        tag = os.path.basename(os.path.normpath(folder))
        for p in sorted(glob.glob(os.path.join(folder, "*.*"))):
            if os.path.splitext(p)[1].lower() not in (".jpg", ".jpeg", ".png"):
                continue
            base = f"d{day.replace('-', '')}_{tag}_{os.path.splitext(os.path.basename(p))[0]}"
            lab = os.path.join(out, "labels", base + ".txt")
            if os.path.exists(lab):
                kept += 1
                continue                                   # already proposed / corrected: never overwrite
            img = cv2.imread(p)
            if img is None:
                continue
            h, w = img.shape[:2]
            s = MAX_SIDE / max(h, w)
            if s < 1:
                img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
            cv2.imwrite(os.path.join(out, "images", base + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            hits = bd._infer_multi(rt, spec, img)
            with open(lab, "w") as f:
                for hh in hits:
                    b = hh["box"]
                    f.write(f"{names.index(hh['class'])} {b['x'] + b['w'] / 2:.6f} {b['y'] + b['h'] / 2:.6f} "
                            f"{b['w']:.6f} {b['h']:.6f}\n")
                    per_class[hh["class"]] = per_class.get(hh["class"], 0) + 1
            per_photo.append(len(hits))
    stats = {"day": day, "new_photos": len(per_photo), "kept_existing": kept, "proposed_boxes": sum(per_photo),
             "photos_without_a_box": per_photo.count(0), "per_class": per_class}
    with open(os.path.join(out, "prelabel_stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    return stats


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2:])))
