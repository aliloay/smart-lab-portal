#!/usr/bin/env python3
"""
Person re-identification audit (read-only; never touches the live service).

  py tools/benchmarks/reid_audit.py DIR

DIR holds authorised raw lab frames (read only, never copied). Person boxes come
from the production detector (YOLO26s, production settings). Then, per frame:

  stage     colour signatures | crop+resize+normalise | re-id inference | L2 norm | tracker
  engines   cv2.dnn CPU (production) | ONNX Runtime CPU | ONNX Runtime DirectML (each adapter)
  parity    embedding cosine vs cv2.dnn, nearest-neighbour ranks, and every look_distance
            decision against the tracker's thresholds (0.35 / 0.45 / 0.65, swap margin 0.05)
  combined  YOLO26s on DirectML alone vs YOLO26s + re-id on DirectML (contention, VRAM)

Results printed and saved to tools/benchmarks/results/ (git-ignored).
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SV = os.path.join(ROOT, "tools", "security_vision")
sys.path.insert(0, SV)
REID = os.path.join(SV, "models", "person_reid_youtu_2021nov.onnx")
YOLO = os.path.join(SV, "models", "yolo26s.onnx")
THRESHOLDS = {"APPEAR_GATE": 0.35, "LEARN_MAX": 0.45, "VETO_AT": 0.65}


def stats(ms):
    a = np.asarray(ms, np.float64)
    return {"n": len(a), "mean": float(a.mean()), "median": float(np.median(a)),
            "p95": float(np.percentile(a, 95)), "min": float(a.min()), "max": float(a.max())}


def vram_mb():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.split()[0])
    except Exception:
        return None


def blob_from(frame, boxes, size=(128, 256)):
    """Exactly Appearance.looks' preprocessing -> NCHW float32 batch."""
    import cv2
    from vision import Appearance
    crops, idx = [], []
    H, W = frame.shape[:2]
    for i, (x, y, w, h) in enumerate(boxes):
        x0, y0 = int(max(0, x)), int(max(0, y))
        x1, y1 = int(min(W, x + w)), int(min(H, y + h))
        if x1 - x0 < 8 or y1 - y0 < 16:
            continue
        img = cv2.resize(frame[y0:y1, x0:x1], size)[:, :, ::-1].astype(np.float32) / 255.0
        crops.append((img - Appearance.MEAN) / Appearance.STD)
        idx.append(i)
    return (cv2.dnn.blobFromImages(crops) if crops else None), idx


def main(directory):
    import cv2
    import onnxruntime as ort
    from vision import PERSON, Look, Tracker, Yolo26Detector, color_signature, look_distance

    frames = [cv2.imread(f) for f in sorted(glob.glob(os.path.join(directory, "*.jpg")))]
    frames = [f for f in frames if f is not None]
    os.environ["SMARTLAB_DETECTOR"] = "gpu"
    det = Yolo26Detector(YOLO, conf=0.35, size=640, threads=8)
    boxes = [[d.box for d in det.detect(f) if d.cls == PERSON] for f in frames]
    out = {"frames": len(frames), "detector": det.engine,
           "people_per_frame": [len(b) for b in boxes], "crops_total": sum(len(b) for b in boxes)}
    print(f"{len(frames)} frames, {out['crops_total']} person crops, detector {det.engine}")

    # ---- engines (each loaded once) ----
    t = time.perf_counter(); net = cv2.dnn.readNet(REID); setup_cv = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    so = ort.SessionOptions(); so.intra_op_num_threads = 8
    s_cpu = ort.InferenceSession(REID, so, providers=["CPUExecutionProvider"])
    setup_cpu = (time.perf_counter() - t) * 1000
    engines = {"cv2dnn-cpu (production)": (lambda b: (net.setInput(b), net.forward())[1], setup_cv),
               "ort-cpu": (lambda b, s=s_cpu: s.run(None, {"input": b})[0], setup_cpu)}
    placement = {}
    for dev in (0, 1):
        try:
            o = ort.SessionOptions()
            o.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
            t = time.perf_counter()
            s = ort.InferenceSession(REID, o, providers=[("DmlExecutionProvider", {"device_id": dev})])
            engines[f"dml{dev}"] = (lambda b, s=s: s.run(None, {"input": b})[0], (time.perf_counter() - t) * 1000)
            placement[f"dml{dev}"] = "loads with CPU fallback disabled: all nodes on DirectML"
        except Exception as e:
            placement[f"dml{dev}"] = f"refused: {str(e)[:160]}"
    out["placement"] = placement
    print("placement:", placement)

    blobs = [blob_from(f, b) for f, b in zip(frames, boxes)]
    work = [(bl, ix) for bl, ix in blobs if bl is not None]

    # ---- standalone inference by batch size (synthetic, deterministic) ----
    rng = np.random.default_rng(20261013)
    out["by_batch"] = {}
    for name, (fn, setup) in engines.items():
        row = {"setup_ms": setup}
        for n in (1, 2, 3, 5, 8):
            x = rng.standard_normal((n, 3, 256, 128), dtype=np.float32)
            for _ in range(10):
                fn(x)
            ms = []
            for _ in range(100):
                t = time.perf_counter(); fn(x); ms.append((time.perf_counter() - t) * 1000)
            row[n] = stats(ms)
        out["by_batch"][name] = row
        print(f"{name:24s} setup {setup:6.0f} ms | " + " | ".join(
            f"b{n}: {row[n]['median']:6.1f} ms (p95 {row[n]['p95']:5.1f})" for n in (1, 2, 3, 5, 8)))

    # ---- per-stage on real frames (deep every frame = worst case: people close) ----
    out["stages"] = {}
    for name, (fn, _) in engines.items():
        col, prep, inf, norm = [], [], [], []
        for _ in range(3):
            for f, b in zip(frames, boxes):
                t0 = time.perf_counter(); [color_signature(f, x) for x in b]; t1 = time.perf_counter()
                bl, ix = blob_from(f, b); t2 = time.perf_counter()
                if bl is None:
                    continue
                y = fn(bl).reshape(len(ix), -1); t3 = time.perf_counter()
                y /= np.maximum(np.linalg.norm(y, axis=1, keepdims=True), 1e-6); t4 = time.perf_counter()
                col.append((t1 - t0) * 1000); prep.append((t2 - t1) * 1000)
                inf.append((t3 - t2) * 1000); norm.append((t4 - t3) * 1000)
        tot = [a + b + c + d for a, b, c, d in zip(col, prep, inf, norm)]
        out["stages"][name] = {"colour": stats(col), "crop_resize_normalise": stats(prep),
                               "inference": stats(inf), "l2norm": stats(norm), "appearance_total": stats(tot)}
        S = out["stages"][name]
        print(f"{name:24s} colour {S['colour']['median']:5.1f} | crops {S['crop_resize_normalise']['median']:5.1f} | "
              f"infer {S['inference']['median']:6.1f} (p95 {S['inference']['p95']:6.1f}) | norm {S['l2norm']['median']:4.2f} | "
              f"appearance {S['appearance_total']['median']:6.1f} ms/frame")

    # tracker alone (looks precomputed, so only the tracker's own work is timed)
    looks = []
    for f, b in zip(frames, boxes):
        bl, ix = blob_from(f, b)
        L = [Look(color_signature(f, x)) for x in b]
        if bl is not None:
            y = engines["cv2dnn-cpu (production)"][0](bl).reshape(len(ix), -1)
            y /= np.maximum(np.linalg.norm(y, axis=1, keepdims=True), 1e-6)
            for i, v in zip(ix, y):
                L[i].deep = v
        looks.append(L)
    tr, ms = Tracker(), []
    for n, (b, L) in enumerate(zip(boxes, looks)):
        t = time.perf_counter(); tr.update(b, 1000.0 + n * 0.2, L); ms.append((time.perf_counter() - t) * 1000)
    out["tracker_only"] = stats(ms)
    print(f"tracker alone: median {out['tracker_only']['median']:.2f} ms, p95 {out['tracker_only']['p95']:.2f} ms")

    # ---- parity: embeddings and identity decisions ----
    ref = []
    for bl, ix in work:
        y = engines["cv2dnn-cpu (production)"][0](bl).reshape(len(ix), -1)
        ref.append(y / np.linalg.norm(y, axis=1, keepdims=True))
    R = np.concatenate(ref)
    out["parity"] = {}
    for name, (fn, _) in engines.items():
        if name.startswith("cv2dnn"):
            continue
        E = []
        for bl, ix in work:
            y = fn(bl).reshape(len(ix), -1)
            E.append(y / np.linalg.norm(y, axis=1, keepdims=True))
        E = np.concatenate(E)
        cos = (R * E).sum(1)
        nn_ref = np.argsort(-(R @ R.T), 1)[:, 1]
        nn_new = np.argsort(-(E @ E.T), 1)[:, 1]
        # look_distance on every pair, colour included (as the tracker uses it)
        cols = [c for f, b in zip(frames, boxes) for c in
                [color_signature(f, x) for i, x in enumerate(b)]]
        idx_all = [(fi, i) for fi, (bl, ix) in enumerate(blobs) if bl is not None for i in ix]
        col_of = {}
        k = 0
        for fi, b in enumerate(boxes):
            for i in range(len(b)):
                col_of[(fi, i)] = cols[k]; k += 1
        A = [Look(col_of[p], R[j]) for j, p in enumerate(idx_all)]
        B = [Look(col_of[p], E[j]) for j, p in enumerate(idx_all)]
        flips = {k: 0 for k in THRESHOLDS}
        maxd, pairs = 0.0, 0
        for i in range(len(A)):
            for j in range(i + 1, len(A)):
                da, db = look_distance(A[i], A[j]), look_distance(B[i], B[j])
                if da is None or db is None:
                    continue
                pairs += 1
                maxd = max(maxd, abs(da - db))
                for kname, th in THRESHOLDS.items():
                    flips[kname] += (da < th) != (db < th)
        out["parity"][name] = {"embeddings": int(len(E)), "cosine_min": float(cos.min()),
                               "cosine_mean": float(cos.mean()),
                               "max_abs_diff": float(np.abs(R - E).max()),
                               "nearest_neighbour_changed": int((nn_ref != nn_new).sum()),
                               "look_pairs": pairs, "max_look_distance_diff": maxd,
                               "threshold_decisions_flipped": flips}
        P = out["parity"][name]
        print(f"parity {name:8s} {P['embeddings']} emb | cos min {P['cosine_min']:.6f} mean {P['cosine_mean']:.6f} | "
              f"max |diff| {P['max_abs_diff']:.2e} | NN changed {P['nearest_neighbour_changed']} | "
              f"{pairs} pairs, max look-dist diff {maxd:.2e}, flips {flips}")

    # ---- combined: YOLO alone vs YOLO + re-id (both DirectML) ----
    best = min((k for k in engines if k.startswith("dml")),
               key=lambda k: out["by_batch"][k][3]["median"], default=None)
    if best:
        out["combined"] = {}
        for label, with_reid in (("yolo only", False), (f"yolo + reid {best}", True)):
            ydet, rre, tot = [], [], []
            for rep in range(5):
                for (f, b), (bl, ix) in zip(zip(frames, boxes), blobs):
                    t0 = time.perf_counter(); det.detect(f); t1 = time.perf_counter()
                    if with_reid and bl is not None:
                        engines[best][0](bl)
                    t2 = time.perf_counter()
                    ydet.append((t1 - t0) * 1000); rre.append((t2 - t1) * 1000); tot.append((t2 - t0) * 1000)
            out["combined"][label] = {"yolo": stats(ydet), "reid": stats(rre), "total": stats(tot), "vram_mb": vram_mb()}
            C = out["combined"][label]
            print(f"{label:22s} yolo {C['yolo']['median']:6.1f} (p95 {C['yolo']['p95']:5.1f}) | reid {C['reid']['median']:6.1f} | "
                  f"total {C['total']['median']:6.1f} ms | VRAM {C['vram_mb']} MB")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    p = os.path.join(HERE, "results", f"reid_audit_{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("saved", p)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
