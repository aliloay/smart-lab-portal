"""
Which set of ONNX models should /scan/appearance run? (2026-11-04, audit P2-D and the Colab v2/v3 comparison.)
Through the backend's own code (app/services/bin_detector.py) at the DEPLOYED thresholds of detectors.json, on the
hand-checked test split (data/lab_r1) and the empty frames (data/lab_neg_test): objects found, false hits, time per image.

    .venv/Scripts/python.exe eval_detector_sets.py
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "backend"))
import cv2  # noqa: E402

from app.services import bin_detector as bd  # noqa: E402

MODELS = os.path.join(HERE, "..", "..", "backend", "data", "models")
COLAB = os.path.join(os.path.expanduser("~"), "Downloads", "colab_results_2026-11-04")
TEST = os.path.join(HERE, "data", "lab_r1")
NEG = os.path.join(HERE, "data", "lab_neg_test")


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0


def truth(img_path):
    lab = img_path.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep).rsplit(".", 1)[0] + ".txt"
    out = {}
    if os.path.exists(lab):
        for line in open(lab, encoding="utf-8").read().splitlines():
            if line.strip():
                k, cx, cy, w, h = line.split()[:5]
                cx, cy, w, h = map(float, (cx, cy, w, h))
                out.setdefault(int(k), []).append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def run_set(specs, img):
    """What detect_all does for this set of (spec, runtime)."""
    lb = bd.letterbox(img)
    hits = []
    for spec, rt in specs:
        hits += bd._infer_multi(rt, spec, img, lb)
    best = {}
    for h in hits:
        if h["code"] not in best or h["confidence"] > best[h["code"]]["confidence"]:
            best[h["code"]] = h
    return bd._suppress_overlaps(sorted(best.values(), key=lambda h: -h["confidence"]))


def evaluate(name, specs, tests, negs, names):
    found = {n: 0 for n in names}
    total = {n: 0 for n in names}
    t0, n_img = time.perf_counter(), 0
    for path, t in tests:
        img = cv2.imread(path)
        n_img += 1
        hits = {h["class"]: h for h in run_set(specs, img)}
        for k, gts in t.items():
            cls = names[k]
            total[cls] += len(gts)
            h = hits.get(cls)
            if h:
                b = h["box"]
                box = (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])
                found[cls] += any(iou(box, g) >= 0.5 for g in gts)     # one hit per class per photo: the portal's limit
    false_hits = 0
    for path in negs:
        img = cv2.imread(path)
        n_img += 1
        false_hits += bool(run_set(specs, img))
    ms = (time.perf_counter() - t0) * 1000 / max(1, n_img)
    row = {"set": name, "found": sum(found.values()), "objects": sum(total.values()), "false_frames": false_hits,
           "empty_frames": len(negs), "ms_per_image": round(ms, 1), "per_class": {n: f"{found[n]}/{total[n]}" for n in names}}
    print(json.dumps(row), flush=True)
    return row


def main():
    specs = json.load(open(os.path.join(MODELS, "detectors.json"), encoding="utf-8"))
    lab_spec = next(s for s in specs if s["file"] == "lab_detector.onnx")
    all_spec = next(s for s in specs if s["file"] == "all_detector.onnx")
    names = [c["name"] for c in sorted(lab_spec["classes"], key=lambda c: c["index"])]
    tests = [(p, truth(p)) for p in sorted(glob.glob(os.path.join(TEST, "images", "test", "*")))]
    tests = [(p, t) for p, t in tests if t]
    negs = sorted(glob.glob(os.path.join(NEG, "**", "*.jpg"), recursive=True))
    print(f"{len(tests)} test photos, {len(negs)} empty frames", flush=True)
    lab = (lab_spec, bd._load(os.path.join(MODELS, "lab_detector.onnx")))
    other = (all_spec, bd._load(os.path.join(MODELS, "all_detector.onnx")))
    sets = {"LIVE: lab_detector + all_detector": [lab, other], "lab_detector alone": [lab]}
    for tag in ("v2", "v3"):
        p = os.path.join(COLAB, tag, "lab_detector.onnx")
        if os.path.exists(p):
            sets[f"Colab {tag} best alone"] = [(lab_spec, bd._load(p))]
    v2 = os.path.join(COLAB, "v2", "lab_detector.onnx")
    if os.path.exists(v2):
        sets["Colab v2 + all_detector"] = [(lab_spec, bd._load(v2)), other]

    def conf(spec, value):             # the same model, another threshold for the switch
        return {**spec, "classes": [{**c, "conf": value} if c["name"] == "network_switch" else c for c in spec["classes"]]}
    for v in (0.6, 0.5):
        sets[f"LIVE, switch threshold {v}"] = [(conf(lab_spec, v), lab[1]), (conf(all_spec, v), other[1])]
        if os.path.exists(v2):
            sets[f"Colab v2 + all_detector, switch threshold {v}"] = [(conf(lab_spec, v), sets["Colab v2 + all_detector"][0][1]),
                                                                      (conf(all_spec, v), other[1])]
    rows = [evaluate(k, v, tests, negs, names) for k, v in sets.items()]
    json.dump(rows, open(os.path.join(HERE, "results", "detector_sets_2026-11-04.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
