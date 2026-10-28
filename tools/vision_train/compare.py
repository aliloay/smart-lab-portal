"""
YOLO11n vs YOLO26n on ONE frozen dataset (docs/VISUAL_AI_PLAN.md, section "Training and comparison").

  py compare.py <data.yaml> [epochs=100] [imgsz=640] [seeds=0] [negatives_dir]
For each model x seed: train from pretrained weights (same settings), evaluate on the TEST split, then report per class
P / R / mAP50 / mAP50-95, the confusion matrix, CPU inference ms (median, p95) and - when a negatives folder (images
with none of the classes) is given - false detections per image. Writes runs/compare/report.json.
Nothing is deployed from here: a model goes to the portal only after it passes the plan's acceptance criteria.
"""
import json
import os
import statistics
import sys
import time

from ultralytics import YOLO

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", "compare")


def bench(model, imgs, imgsz):
    ts = []
    for f in imgs[:60]:
        t = time.perf_counter()
        model.predict(f, imgsz=imgsz, device="cpu", verbose=False)
        ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    return {"median_ms": round(statistics.median(ts), 1), "p95_ms": round(ts[int(len(ts) * .95) - 1], 1), "n": len(ts)}


def main():
    data = sys.argv[1]
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    imgsz = int(sys.argv[3]) if len(sys.argv) > 3 else 640
    seeds = [int(s) for s in (sys.argv[4] if len(sys.argv) > 4 else "0").split(",")]
    negs = sys.argv[5] if len(sys.argv) > 5 else None
    neg_imgs = sorted(os.path.join(negs, f) for f in os.listdir(negs)) if negs else []
    report = {"data": data, "epochs": epochs, "imgsz": imgsz, "runs": []}
    for base in ("yolo11n.pt", "yolo26n.pt"):
        for seed in seeds:
            name = f"{base[:-3]}_s{seed}_{imgsz}"
            m = YOLO(base)
            m.train(data=data, epochs=epochs, imgsz=imgsz, seed=seed, deterministic=True, device="cpu", workers=0,
                    project=OUT, name=name, exist_ok=True, verbose=False, patience=30)
            best = YOLO(os.path.join(str(m.trainer.save_dir), "weights", "best.pt"))
            v = best.val(data=data, split="test", imgsz=imgsz, device="cpu", verbose=False, plots=True,
                         project=OUT, name=name + "_test", exist_ok=True)
            names = v.names
            per = {names[c]: {"P": round(float(v.box.p[i]), 3), "R": round(float(v.box.r[i]), 3),
                              "mAP50": round(float(v.box.ap50[i]), 3), "mAP50_95": round(float(v.box.ap[i]), 3)}
                   for i, c in enumerate(v.box.ap_class_index)}
            fp = None
            if neg_imgs:
                dets = sum(len(r.boxes) for f in neg_imgs for r in best.predict(f, imgsz=imgsz, conf=0.25, verbose=False))
                fp = round(dets / len(neg_imgs), 3)
            test_imgs = sorted(os.path.join(os.path.dirname(data), "images", "test", f)
                               for f in os.listdir(os.path.join(os.path.dirname(data), "images", "test")))
            run = {"model": base, "seed": seed, "mAP50": round(float(v.box.map50), 4), "mAP50_95": round(float(v.box.map), 4),
                   "per_class": per, "false_detections_per_negative_image": fp,
                   "cpu_inference": bench(best, test_imgs, imgsz),
                   "confusion_matrix": v.confusion_matrix.matrix.astype(int).tolist()}
            report["runs"].append(run)
            print(name, "mAP50", run["mAP50"], "mAP50-95", run["mAP50_95"], "fp/neg", fp, run["cpu_inference"])
    os.makedirs(OUT, exist_ok=True)
    json.dump(report, open(os.path.join(OUT, "report.json"), "w"), indent=1)
    print("report:", os.path.join(OUT, "report.json"))


if __name__ == "__main__":
    main()
