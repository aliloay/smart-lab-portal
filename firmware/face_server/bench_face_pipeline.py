"""
Offline profile of the door's face pipeline - no camera, no door, nothing saved.

    py bench_face_pipeline.py            (in firmware/face_server)

Uses the ESP32-CAM's own frames already on disk (portraits/*.jpg, 640x480 enrolment frames) and
the aligned samples (dataset_sface/). Prints per-stage time for /analyze and /enroll, compares the
SFace embedding from OpenCV DNN with ONNX Runtime (must be the same numbers, or a faster runtime
would change who is recognised), and a leave-one-out check of the stored samples at the door's
threshold. Pictures of people stay local (gitignored); only numbers are printed.
"""
from __future__ import annotations

import glob
import os
import statistics
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
YUNET = os.path.join("models", "face_detection_yunet_2023mar.onnx")
SFACE = os.path.join("models", "face_recognition_sface_2021dec.onnx")
THRESHOLD = 0.363
N = 30


def ms(f, n=N):
    t = []
    for _ in range(n):
        t0 = time.perf_counter(); f(); t.append((time.perf_counter() - t0) * 1000)
    return statistics.median(t), sorted(t)[int(0.95 * (len(t) - 1))]


def unit(v):
    v = np.asarray(v, dtype=np.float64).flatten()
    return v / (np.linalg.norm(v) or 1.0)


def main():
    yunet = cv2.FaceDetectorYN.create(YUNET, "", (320, 240), 0.6, 0.3, 5000)
    sface = cv2.FaceRecognizerSF.create(SFACE, "")
    qr = cv2.QRCodeDetector()
    frames = [(p, open(p, "rb").read()) for p in sorted(glob.glob("portraits/*.jpg"))]
    print(f"{len(frames)} ESP32-CAM frames, threads {cv2.getNumThreads()}")
    rows = {}
    for path, raw in frames:
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(img, (320, int(img.shape[0] * 320 / img.shape[1])), interpolation=cv2.INTER_AREA)

        def detect():
            yunet.setInputSize((small.shape[1], small.shape[0]))
            return yunet.detect(small)[1]
        faces = detect()
        if faces is None:
            continue
        f = max(faces, key=lambda r: r[2] * r[3]).copy(); f[:14] *= img.shape[1] / 320
        crop = sface.alignCrop(img, f)
        stages = {"decode": lambda: cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR),
                  "qr_fast": lambda: qr.detectAndDecode(gray), "yunet_320": detect,
                  "align": lambda: sface.alignCrop(img, f), "sface": lambda: sface.feature(crop)}
        for k, fn in stages.items():
            rows.setdefault(k, []).append(ms(fn))
    print("\n/analyze per frame (median / p95 ms over frames):")
    for k, v in rows.items():
        print(f"  {k:10s} {statistics.median(x[0] for x in v):6.1f} / {max(x[1] for x in v):6.1f}")
    face_path = sum(statistics.median(x[0] for x in rows[k]) for k in ("decode", "qr_fast", "yunet_320", "align", "sface"))
    print(f"  = {face_path:.1f} ms for a face frame (WeChat QR is skipped when a face is seen)")

    # Enrolment: the current code runs YuNet three times on the frame; one pass gives the same row.
    det = statistics.median(x[0] for x in rows["yunet_320"])
    print(f"\n/enroll detection: 3 YuNet passes {3 * det:.1f} ms -> 1 pass {det:.1f} ms")

    # ONNX Runtime vs OpenCV DNN for SFace: same input (aligned 112x112 BGR), same output?
    try:
        import onnxruntime as ort
        samples = sorted(glob.glob("dataset_sface/*/*.png"))[:40]
        sess = ort.InferenceSession(SFACE, providers=["CPUExecutionProvider"])
        name = sess.get_inputs()[0].name
        diffs, t_cv, t_ort = [], [], []
        for p in samples:
            a = cv2.imread(p)
            t0 = time.perf_counter(); e1 = unit(sface.feature(a)); t_cv.append(time.perf_counter() - t0)
            blob = cv2.dnn.blobFromImage(a, 1.0, (112, 112), (0, 0, 0), swapRB=True)
            t0 = time.perf_counter(); e2 = unit(sess.run(None, {name: blob.astype(np.float32)})[0]); t_ort.append(time.perf_counter() - t0)
            diffs.append(float(np.dot(e1, e2)))
        print(f"\nSFace on {len(samples)} samples: OpenCV {statistics.median(t_cv) * 1000:.2f} ms, "
              f"ONNX Runtime CPU {statistics.median(t_ort) * 1000:.2f} ms, embedding agreement min cosine {min(diffs):.6f}")
    except Exception as e:
        print(f"\nONNX Runtime comparison skipped: {e}")

    # Leave-one-out over the stored samples, at the door's threshold.
    people = {os.path.basename(d): [unit(sface.feature(cv2.imread(p))) for p in sorted(glob.glob(d + "/*.png"))]
              for d in sorted(glob.glob("dataset_sface/*")) if os.path.isdir(d)}
    ok = wrong = refused = 0; gen, imp = [], []
    for who, feats in people.items():
        for i, q in enumerate(feats):
            tmpl = {n: unit(np.mean([x for j, x in enumerate(fs) if not (n == who and j == i)], axis=0))
                    for n, fs in people.items() if len(fs) - (n == who) > 0}
            scores = sorted(((float(np.dot(q, t)), n) for n, t in tmpl.items()), reverse=True)
            best, n = scores[0]
            gen.append(float(np.dot(q, tmpl[who])))
            imp += [s for s, m in scores if m != who]
            if best < THRESHOLD: refused += 1
            elif n == who: ok += 1
            else: wrong += 1
    tot = ok + wrong + refused
    print(f"\nLeave-one-out, {len(people)} people, {tot} samples, threshold {THRESHOLD}: "
          f"{ok} right ({100 * ok / tot:.1f}%), {refused} refused, {wrong} WRONG PERSON")
    print(f"  genuine cosine min {min(gen):.3f} median {statistics.median(gen):.3f} | "
          f"impostor max {max(imp):.3f} median {statistics.median(imp):.3f}")


if __name__ == "__main__":
    main()
