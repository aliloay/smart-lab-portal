"""V-F9 offline pose benchmark (closure 2026-11-23). Frames come from a recorded camera file; only timings are kept.

usage: py tools/perf/vf9_pose_bench.py <video> <mode: cpu|dml> <threads (0 = onnxruntime default)> <n_frames> <out.json>
Needs tools/security_vision/models/yolov8n-pose.onnx (not in git). Run with nothing else heavy on the CPU, or say so.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "security_vision"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import pose  # noqa: E402

video, mode, threads, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
cap = cv2.VideoCapture(video)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1000
frames = []
for i in range(n):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / n))
    ok, f = cap.read()
    if ok:
        frames.append(f)
cap.release()
if mode == "dml":                       # exactly as PoseModel.load tries it first
    so = ort.SessionOptions()
    so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    s = ort.InferenceSession(pose.DEFAULT_PATH, so, providers=[("DmlExecutionProvider", {"device_id": 1})])
else:
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    s = ort.InferenceSession(pose.DEFAULT_PATH, so, providers=["CPUExecutionProvider"])
m = pose.PoseModel(s, s.get_inputs()[0].name, mode)
m.infer(frames[0])                      # warm-up
ms, people = [], []
t0, c0 = time.perf_counter(), time.process_time()
for f in frames:
    people.append(len(m.infer(f)))
    ms.append(m.ms[-1])
wall, cpu = time.perf_counter() - t0, time.process_time() - c0
a = np.array(ms)
r = {"video": os.path.basename(video), "mode": mode, "threads": threads, "frames": len(frames),
     "p50_ms": round(float(np.percentile(a, 50)), 1), "p90_ms": round(float(np.percentile(a, 90)), 1),
     "p95_ms": round(float(np.percentile(a, 95)), 1), "mean_ms": round(float(a.mean()), 1),
     "cores_used_avg": round(cpu / wall, 2), "poses_per_frame_avg": round(float(np.mean(people)), 2)}
json.dump(r, open(out, "w"))
print(json.dumps(r))
