---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/benchmarks/audit_engines.py"
source_hash: "2639a1dc529fac919806c87e2b16d9b132bbd2476d973954574b4a9e2c86a4cb"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/benchmarks/audit_engines.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[docs_benchmarks_REID_GPU_AUDIT_2026-10-13.md]] - mentioned by docs
- [[docs_benchmarks_SECURITYCAM_ENGINE_AUDIT_2026-10-13.md]] - mentioned by docs
- [[tools_security_vision_vision.py]] - imports

```py
#!/usr/bin/env python3
"""
SecurityCam detector-engine audit (read-only; never touches the live service).

  py tools/benchmarks/audit_engines.py synthetic   # per-device, isolated processes
  py tools/benchmarks/audit_engines.py placement   # does DirectML run every node on the GPU?
  py tools/benchmarks/audit_engines.py frames DIR  # same real frames, PRODUCTION pre/post-processing
  py tools/benchmarks/audit_engines.py stages DIR  # offline per-stage timing (pre / infer / post / tracker)

Every engine runs the same tools/security_vision/models/yolo26s.onnx. Results
are printed and saved as JSON under tools/benchmarks/results/ (git-ignored).
Frames are read from DIR and never copied or written anywhere.
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
MODEL = os.path.join(ROOT, "tools", "security_vision", "models", "yolo26s.onnx")
OUT = os.path.join(HERE, "results")
sys.path.insert(0, os.path.join(ROOT, "tools", "security_vision"))


def stats(ms: list[float]) -> dict:
    a = np.asarray(ms, dtype=np.float64)
    return {"n": len(a), "mean": float(a.mean()), "median": float(np.median(a)),
            "p90": float(np.percentile(a, 90)), "p95": float(np.percentile(a, 95)),
            "min": float(a.min()), "max": float(a.max()), "std": float(a.std()),
            "fps_median": 1000.0 / float(np.median(a))}


def save(name: str, data) -> str:
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f"{name}_{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, default=str)
    return p


# ------------------------------------------------------------ one engine ---
def make_runner(engine: str):
    """(run(x) -> output, setup_ms, detail) for one engine; raises if it cannot run."""
    t0 = time.perf_counter()
    if engine.startswith("dml"):
        import onnxruntime as ort
        dev = int(engine[3:])
        so = ort.SessionOptions()
        so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")   # fail, never silently CPU
        s = ort.InferenceSession(MODEL, so, providers=[("DmlExecutionProvider", {"device_id": dev})])
        i = s.get_inputs()[0].name
        return (lambda x: s.run(None, {i: x})[0]), (time.perf_counter() - t0) * 1000, s.get_providers()
    if engine == "ort-cpu":
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = 8                      # production setting
        s = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
        i = s.get_inputs()[0].name
        return (lambda x: s.run(None, {i: x})[0]), (time.perf_counter() - t0) * 1000, s.get_providers()
    if engine.startswith("ov-"):
        import openvino as ov
        dev = engine[3:]
        cfg = {"PERFORMANCE_HINT": "LATENCY"}
        if dev == "CPU":
            cfg["INFERENCE_NUM_THREADS"] = 8              # production setting
        cm = ov.Core().compile_model(MODEL, dev, cfg)
        r = cm.create_infer_request()
        return (lambda x: r.infer({0: x})[0]), (time.perf_counter() - t0) * 1000, [f"OpenVINO {dev}"]
    raise ValueError(engine)


def child_synthetic(engine: str, warmup: int, iters: int) -> dict:
    run, setup_ms, detail = make_runner(engine)
    x = np.random.default_rng(20261013).random((1, 3, 640, 640), dtype=np.float32)
    for _ in range(warmup):
        run(x)
    ms = []
    for _ in range(iters):
        t = time.perf_counter()
        y = run(x)                     # returns a host numpy array: the GPU work has completed
        ms.append((time.perf_counter() - t) * 1000)
    return {"engine": engine, "setup_ms": setup_ms, "providers": detail,
            "finite": bool(np.isfinite(y).all()), "out_shape": list(y.shape), "latency": stats(ms)}


ENGINES = ["dml0", "dml1", "ov-CPU", "ort-cpu", "ov-GPU.0", "ov-GPU.1"]


def synthetic(rounds: int = 3) -> None:
    """Each engine in its OWN process (a crashing driver cannot take the others
    down), one after another, repeated `rounds` times."""
    res = {e: [] for e in ENGINES}
    for r in range(rounds):
        for e in ENGINES:
            p = subprocess.run([sys.executable, __file__, "_child", e], capture_output=True, text=True,
                               timeout=900, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            line = next((l for l in p.stdout.splitlines() if l.startswith("{")), None)
            if p.returncode != 0 or line is None:
                err = (p.stderr.strip().splitlines() or [f"exit code {p.returncode}"])[-1][:200]
                res[e].append({"engine": e, "status": "FAILED", "exit": p.returncode, "error": err})
                print(f"round {r+1} {e:9s} FAILED (exit {p.returncode}): {err}", flush=True)
                continue
            d = json.loads(line)
            d["status"] = "OK"
            res[e].append(d)
            L = d["latency"]
            print(f"round {r+1} {e:9s} setup {d['setup_ms']:7.0f} ms | median {L['median']:7.2f} "
                  f"p90 {L['p90']:7.2f} p95 {L['p95']:7.2f} min {L['min']:7.2f} max {L['max']:7.2f} "
                  f"| {L['fps_median']:5.1f}/s | finite={d['finite']}", flush=True)
    print("saved", save("synthetic_isolated", res))


def placement() -> None:
    """With CPU fallback disabled, a DirectML session that loads at all runs every
    node on DirectML. Also log what ORT assigns at verbose level."""
    import onnxruntime as ort
    out = {}
    for dev in (0, 1):
        so = ort.SessionOptions()
        so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        try:
            ort.InferenceSession(MODEL, so, providers=[("DmlExecutionProvider", {"device_id": dev})])
            out[f"dml{dev}"] = "loads with CPU fallback DISABLED -> every node assigned to DirectML"
        except Exception as e:
            out[f"dml{dev}"] = f"refused with CPU fallback disabled: {str(e)[:200]}"
        print(f"dml{dev}: {out[f'dml{dev}']}")
    print("saved", save("placement", out))


# ------------------------------------------------- real frames, production path ---
def frames(directory: str) -> None:
    import cv2
    from vision import PERSON, Yolo26Detector, iou
    files = sorted(glob.glob(os.path.join(directory, "*.jpg")))
    imgs = [cv2.imread(f) for f in files]
    imgs = [i for i in imgs if i is not None]
    if not imgs:
        raise SystemExit(f"no frames in {directory}")
    engines = {}
    for e, env in (("ort-cpu", "onnxruntime"), ("ov-CPU", "openvino"), ("dml-auto", "gpu")):
        os.environ["SMARTLAB_DETECTOR"] = env
        engines[e] = Yolo26Detector(MODEL, conf=0.35, size=640, threads=8)   # production settings
    os.environ.pop("SMARTLAB_DETECTOR", None)
    base = "ort-cpu"
    report = {"frames": len(imgs), "settings": {"conf": 0.35, "nms": 0.45, "size": 640},
              "engines": {k: d.engine for k, d in engines.items()}, "per_engine": {}}
    dets = {k: [d.detect(im) for im in imgs] for k, d in engines.items()}
    for k in engines:
        people = [sum(1 for x in fr if x.cls == PERSON) for fr in dets[k]]
        all_cls = [sorted(x.cls for x in fr) for fr in dets[k]]
        # Box agreement with the CPU baseline: each baseline box matched by IoU >= 0.9, same class.
        matched = total = extra = 0
        worst_iou, score_diff = 1.0, 0.0
        for fb, fk in zip(dets[base], dets[k]):
            used = set()
            for b in fb:
                total += 1
                best, bj = 0.0, None
                for j, c in enumerate(fk):
                    if j in used or c.cls != b.cls:
                        continue
                    v = iou(b.box, c.box)
                    if v > best:
                        best, bj = v, j
                if bj is not None and best >= 0.9:
                    matched += 1
                    used.add(bj)
                    worst_iou = min(worst_iou, best)
                    score_diff = max(score_diff, abs(b.score - fk[bj].score))
            extra += len(fk) - len(used)
        report["per_engine"][k] = {"engine": engines[k].engine, "people_per_frame": people,
                                   "detections_total": sum(len(f) for f in dets[k]),
                                   "same_classes_as_cpu_every_frame": all_cls == [sorted(x.cls for x in f) for f in dets[base]],
                                   "cpu_boxes_matched_iou>=0.9": f"{matched}/{total}",
                                   "unmatched_extra_boxes": extra,
                                   "worst_matched_iou": round(worst_iou, 4),
                                   "max_score_difference": round(score_diff, 4)}
        r = report["per_engine"][k]
        print(f"{k:9s} [{r['engine']}] people/frame {people}  boxes {r['detections_total']}  "
              f"matched {r['cpu_boxes_matched_iou>=0.9']}  extra {extra}  worst IoU {r['worst_matched_iou']}  "
              f"max score diff {r['max_score_difference']}  same classes {r['same_classes_as_cpu_every_frame']}")
    print("saved", save("frames_parity", report))


def stages(directory: str, passes: int = 3) -> None:
    """Offline replay of the analysis pass on real frames, per stage, per engine.
    Pre / infer / post are timed inside the production detector's own steps."""
    import cv2
    from vision import PERSON, Appearance, Tracker, Yolo26Detector
    reid = os.path.join(ROOT, 'tools', 'security_vision', 'models', 'person_reid_youtu_2021nov.onnx')
    imgs = [cv2.imread(f) for f in sorted(glob.glob(os.path.join(directory, "*.jpg")))]
    imgs = [i for i in imgs if i is not None]
    res = {}
    for e, env in (("ort-cpu", "onnxruntime"), ("ov-CPU", "openvino"), ("dml-auto", "gpu")):
        os.environ["SMARTLAB_DETECTOR"] = env
        d = Yolo26Detector(MODEL, conf=0.35, size=640, threads=8)
        tr, app = Tracker(), Appearance(reid if os.path.isfile(reid) else None)
        pre, inf, post, trk, total = [], [], [], [], []
        for im in imgs[:3]:
            d.detect(im)
        for _ in range(passes):
            for n, im in enumerate(imgs):
                t0 = time.perf_counter()
                h, w = im.shape[:2]
                r = min(d.size / h, d.size / w)
                nw, nh = int(round(w * r)), int(round(h * r))
                pad = np.full((d.size, d.size, 3), 114, np.uint8)
                pad[:nh, :nw] = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
                blob = pad[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
                t1 = time.perf_counter()
                d._infer(blob)
                t2 = time.perf_counter()
                dets = d.detect(im)                  # full production call; post = its time minus pre+infer
                t3 = time.perf_counter()
                people = [x.box for x in dets if x.cls == PERSON]       # as the live service does
                tnow = time.time() + n * 0.2
                tr.update(people, tnow, app.looks(im, people, tnow))     # tracker + appearance / re-id
                t4 = time.perf_counter()
                pre.append((t1 - t0) * 1000)
                inf.append((t2 - t1) * 1000)
                post.append(max(0.0, (t3 - t2) * 1000 - (t1 - t0) * 1000 - (t2 - t1) * 1000))
                trk.append((t4 - t3) * 1000)
                total.append((t1 - t0 + t3 - t2 + t4 - t3) * 1000)
        res[e] = {"engine": d.engine, "preprocess": stats(pre), "inference": stats(inf),
                  "postprocess_nms": stats(post), "tracker_and_reid": stats(trk), "analysis_pass": stats(total)}
        R = res[e]
        print(f"{e:9s} [{d.engine}] pre {R['preprocess']['median']:6.2f} | infer {R['inference']['median']:7.2f} "
              f"(p95 {R['inference']['p95']:6.1f}) | post+NMS {R['postprocess_nms']['median']:5.2f} | "
              f"tracker+re-id {R['tracker_and_reid']['median']:6.2f} (p95 {R['tracker_and_reid']['p95']:6.1f}) | pass {R['analysis_pass']['median']:7.2f} ms "
              f"-> max {1000 / R['analysis_pass']['median']:.1f} passes/s")
    os.environ.pop("SMARTLAB_DETECTOR", None)
    print("saved", save("stages_offline", res))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "synthetic"
    if cmd == "_child":
        print(json.dumps(child_synthetic(sys.argv[2], warmup=10, iters=100)))
    elif cmd == "synthetic":
        synthetic()
    elif cmd == "placement":
        placement()
    elif cmd == "frames":
        frames(sys.argv[2])
    elif cmd == "stages":
        stages(sys.argv[2])
    else:
        raise SystemExit(__doc__)

```
