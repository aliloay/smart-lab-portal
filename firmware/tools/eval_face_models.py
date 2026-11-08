"""
Compare the door's face recognizers on the enrolled samples, offline.

    py firmware/tools/eval_face_models.py            (from the repo root)

Method: leave-one-out over firmware/face_server/dataset/<USERn>/*.jpg. Each
sample is identified against a model built from all OTHER samples, so no
sample is ever matched against itself.

  LBPH  - what the door uses now: OpenCV LBPHFaceRecognizer, default
          parameters, 200x200 grey crops, accept when distance <= 70.
  SFace - OpenCV FaceRecognizerSF (128-d embedding), YuNet landmarks for
          alignment, one template per person = mean embedding of the other
          samples, accept when cosine similarity >= 0.363 (OpenCV's value).

Prints accuracy, false accepts (identified as the WRONG person), false
rejects (right person refused), the genuine / impostor score ranges, and
CPU time per face. Writes the per-sample rows to a CSV next to the dataset
(gitignored with it) for the thesis tables.

Limits, to state with the result: only the people enrolled so far, samples
from one camera and one session each, and the stored samples are the grey
200x200 crops the door saved - not the colour frames SFace would normally
receive - so SFace is measured here at a disadvantage.
"""
import csv
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FACE_DIR = os.path.join(HERE, "..", "face_server")
DATASET = os.path.join(FACE_DIR, "dataset")
MODELS = os.path.join(FACE_DIR, "models")
YUNET = os.path.join(MODELS, "face_detection_yunet_2023mar.onnx")
SFACE = os.path.join(MODELS, "face_recognition_sface_2021dec.onnx")

LBPH_THRESHOLD = 70.0          # face_server.CONFIDENCE_THRESHOLD
SFACE_THRESHOLD = 0.363        # OpenCV model zoo, cosine


def load_dataset():
    people = {}
    for name in sorted(os.listdir(DATASET)):
        d = os.path.join(DATASET, name)
        if not os.path.isdir(d):
            continue
        imgs = []
        for fn in sorted(os.listdir(d), key=lambda f: (len(f), f)):
            img = cv2.imread(os.path.join(d, fn), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imgs.append((fn, img))
        if imgs:
            people[name] = imgs
    return people


def eval_lbph(people):
    rows, names = [], sorted(people)
    flat = [(n, fn, img) for n in names for fn, img in people[n]]
    times = []
    for i, (truth, fn, img) in enumerate(flat):
        rec = cv2.face.LBPHFaceRecognizer_create()
        others = [(names.index(n), im) for j, (n, _, im) in enumerate(flat) if j != i]
        rec.train([im for _, im in others], np.array([lab for lab, _ in others]))
        t0 = time.perf_counter()
        label, dist = rec.predict(img)
        times.append(time.perf_counter() - t0)
        rows.append({"method": "LBPH", "truth": truth, "sample": fn,
                     "predicted": names[label], "score": round(float(dist), 3),
                     "accepted": dist <= LBPH_THRESHOLD})
    return rows, times


def sface_features(people):
    det = cv2.FaceDetectorYN.create(YUNET, "", (200, 200), 0.6, 0.3, 5000)
    rec = cv2.FaceRecognizerSF.create(SFACE, "")
    feats, aligned_ok, times = {}, 0, []
    for name, imgs in people.items():
        for fn, grey in imgs:
            img = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)
            # The stored crop is tight (forehead to chin); a margin lets the
            # detector see a whole face and return its landmarks.
            pad = cv2.copyMakeBorder(img, 50, 50, 50, 50, cv2.BORDER_REPLICATE)
            t0 = time.perf_counter()
            det.setInputSize((pad.shape[1], pad.shape[0]))
            _, faces = det.detect(pad)
            if faces is not None and len(faces):
                face = max(faces, key=lambda f: f[2] * f[3])
                crop = rec.alignCrop(pad, face)
                aligned_ok += 1
            else:
                crop = cv2.resize(img, (112, 112))          # no landmarks found
            f = rec.feature(crop).flatten()
            times.append(time.perf_counter() - t0)
            feats[(name, fn)] = f / np.linalg.norm(f)
    return feats, aligned_ok, times


def eval_sface(people, feats):
    rows, names = [], sorted(people)
    for truth in names:
        for fn, _ in people[truth]:
            q = feats[(truth, fn)]
            best, best_score, scores = None, -2.0, {}
            for n in names:
                others = [feats[(n, f)] for f, _ in people[n] if (n, f) != (truth, fn)]
                if not others:
                    continue
                t = np.mean(others, axis=0)
                s = float(np.dot(q, t / np.linalg.norm(t)))
                scores[n] = s
                if s > best_score:
                    best, best_score = n, s
            rows.append({"method": "SFace", "truth": truth, "sample": fn,
                         "predicted": best, "score": round(best_score, 4),
                         "accepted": best_score >= SFACE_THRESHOLD,
                         "impostor_best": round(max((v for k, v in scores.items() if k != truth),
                                                    default=float("nan")), 4)})
    return rows


def summary(rows, label, higher_is_better):
    n = len(rows)
    correct = sum(r["accepted"] and r["predicted"] == r["truth"] for r in rows)
    false_acc = sum(r["accepted"] and r["predicted"] != r["truth"] for r in rows)
    false_rej = sum(not r["accepted"] and r["predicted"] == r["truth"] for r in rows)
    wrong_rej = sum(not r["accepted"] and r["predicted"] != r["truth"] for r in rows)
    genuine = [r["score"] for r in rows if r["predicted"] == r["truth"]]
    print(f"\n{label}  ({n} samples)")
    print(f"  correctly identified and accepted : {correct}/{n} = {100 * correct / n:.1f}%")
    print(f"  FALSE ACCEPT (wrong person let in) : {false_acc}")
    print(f"  false reject (right person refused): {false_rej}")
    print(f"  wrong person, but refused          : {wrong_rej}")
    if genuine:
        print(f"  best-match score of correct IDs    : min {min(genuine):.3f}  "
              f"mean {np.mean(genuine):.3f}  max {max(genuine):.3f} "
              f"({'higher' if higher_is_better else 'lower'} = better match)")


def main():
    for p in (YUNET, SFACE):
        if not os.path.isfile(p):
            sys.exit(f"missing model: {p}\nsee firmware/face_server/models/README.md")
    people = load_dataset()
    if len(people) < 2:
        sys.exit("need at least two enrolled people in dataset/")
    print("Enrolled:", ", ".join(f"{n} ({len(v)} samples)" for n, v in people.items()))

    lbph_rows, lbph_t = eval_lbph(people)
    feats, aligned, sf_t = sface_features(people)
    sface_rows = eval_sface(people, feats)

    summary(lbph_rows, f"LBPH  (accept if distance <= {LBPH_THRESHOLD})", False)
    summary(sface_rows, f"SFace (accept if cosine >= {SFACE_THRESHOLD})", True)
    imp = [r["impostor_best"] for r in sface_rows if not np.isnan(r["impostor_best"])]
    if imp:
        print(f"  impostor score (other person)      : max {max(imp):.3f}  mean {np.mean(imp):.3f}")
    total = sum(len(v) for v in people.values())
    print(f"  YuNet landmarks found on the crop  : {aligned}/{total}")
    print(f"\nCPU time per face: LBPH predict {1000 * np.median(lbph_t):.1f} ms, "
          f"SFace detect+align+embed {1000 * np.median(sf_t):.1f} ms (median)")

    out = os.path.join(FACE_DIR, "dataset", "..", "face_model_comparison.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        keys = ["method", "truth", "sample", "predicted", "score", "accepted", "impostor_best"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in lbph_rows + sface_rows:
            w.writerow({k: r.get(k, "") for k in keys})
    print(f"Per-sample rows: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
