"""Round 5 data (2026-11-12): lab_r1 labels mark ONE object per photo (1010/1012 train photos), so every other
visible object was trained as background - the reason multi-object scenes miss boxes. This adds, to TRAIN and VAL only,
the boxes the deployed lab_detector finds with high confidence that do not overlap an existing box. TEST is copied
untouched (it stays the apples-to-apples 171-object benchmark). Proposed boxes are listed in pseudo_report.json for
review. Run with the backend venv:  ..\..\backend\.venv\Scripts\python.exe build_r5_pseudo.py"""
import glob, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402
from app.services import bin_detector as bd  # noqa: E402

SRC, DST = os.path.join(HERE, "data", "lab_r1"), os.path.join(HERE, "data", "lab_r5")
CONF = 0.60            # proposal threshold (above every deployed per-class threshold)
IOU_MAX = 0.30         # a proposal overlapping an existing box this much is the same object


def iou(a, b):
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw, ih = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    u = a[2] * a[3] + b[2] * b[3] - iw * ih
    return iw * ih / u if u else 0


def main():
    if os.path.exists(DST):
        sys.exit(f"{DST} exists - remove it first (never overwritten)")
    shutil.copytree(SRC, DST)
    spec = next(s for s in json.load(open(os.path.join(bd.MODELS if hasattr(bd, 'MODELS') else os.path.join(HERE, '..', '..', 'backend', 'data', 'models'), 'detectors.json'), encoding='utf-8')) if s['file'] == 'lab_detector.onnx')
    spec = {**spec, "classes": [{**c, "conf": max(CONF, c.get("conf", 0.5)), "max_instances": 6} for c in spec["classes"]]}
    rt = bd._load(os.path.join(HERE, "..", "..", "backend", "data", "models", "lab_detector.onnx"))
    report = {"conf": CONF, "iou_max": IOU_MAX, "added": [], "photos_now_multi": 0}
    for split in ("train", "val"):
        for img_p in sorted(glob.glob(os.path.join(DST, "images", split, "*"))):
            lbl_p = os.path.join(DST, "labels", split, os.path.splitext(os.path.basename(img_p))[0] + ".txt")
            rows = [l.split() for l in open(lbl_p).read().splitlines() if l.strip()] if os.path.exists(lbl_p) else []
            if not rows:
                continue                                  # negatives / backgrounds stay empty
            boxes = [[float(v) for v in r[1:5]] for r in rows]
            img = cv2.imread(img_p)
            if img is None:
                continue
            h, w = img.shape[:2]
            new = []
            for hit in bd._infer_multi(rt, spec, img):
                b = hit["box"]                            # normalised x, y, w, h (top-left)
                cand = [b["x"] + b["w"] / 2, b["y"] + b["h"] / 2, b["w"], b["h"]]
                if 0.002 <= cand[2] * cand[3] <= 0.85 and all(iou(cand, o) < IOU_MAX for o in boxes + [n[1] for n in new]):
                    k = next(c["index"] for c in spec["classes"] if c["name"] == hit["class"])
                    new.append((k, cand, hit["confidence"]))
            if new:
                with open(lbl_p, "a") as f:
                    for k, c, _ in new:
                        f.write(f"\n{k} {c[0]:.6f} {c[1]:.6f} {c[2]:.6f} {c[3]:.6f}")
                report["added"] += [{"split": split, "image": os.path.basename(img_p), "class": spec["classes"][k]["name"],
                                     "conf": round(cf, 3)} for k, _, cf in new]
                report["photos_now_multi"] += 1
    json.dump(report, open(os.path.join(DST, "pseudo_report.json"), "w"), indent=1)
    print(f"added {len(report['added'])} boxes; {report['photos_now_multi']} photos now have 2+ objects")


if __name__ == "__main__":
    main()
