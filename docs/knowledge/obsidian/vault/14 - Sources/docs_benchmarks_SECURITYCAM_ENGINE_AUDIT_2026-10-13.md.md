---
type: "source-mirror"
source_kind: "benchmark-report"
source_path: "docs/benchmarks/SECURITYCAM_ENGINE_AUDIT_2026-10-13.md"
source_hash: "bd33b5a95531329adf50584ca4c5f2bee1178b658ffe869670ad47ebfae398df"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/benchmarks/SECURITYCAM_ENGINE_AUDIT_2026-10-13.md` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_benchmarks_benchmark_vision_engines.py]] - mentioned by docs
- [[tools_benchmarks_audit_engines.py]] - mentioned by docs
- [[tools_security_vision_test_engines.py]] - mentioned by docs

# SecurityCam detector engine audit — 2026-10-13

All numbers below were measured on this laptop on 2026-10-13 between 02:20 and 02:50.
Raw outputs (JSON / text) are in `tools/benchmarks/results/` (git-ignored). No camera
footage, frame, credential or personal image is part of this report or of git.

## A. Verdict

**Use ONNX Runtime + DirectML on the NVIDIA GTX 1650** (`directml-gpu1`), with OpenVINO CPU and
ONNX Runtime CPU as automatic fallbacks — this is what `vision.Yolo26Detector` does since
commit ed56b8d. Evidence: 4.4–4.9x faster inference than either CPU engine, every model node
verified on DirectML, identical detections to the CPU baseline on 60 real lab frames
(1,044 detections), and no drift or memory growth over 2,000 inferences.
Confidence: high for speed and for parity with the current CPU engine. Absolute accuracy
against hand-made ground truth was **not** measured (no labelled set exists).

## B. Environment verified

| Item | Value |
|---|---|
| CPU / GPUs | i7-9750H; Intel UHD 630; NVIDIA GTX 1650 4 GB (driver 616.92) |
| Python | 3.14.7 (`pythoncore-3.14-64`) |
| ONNX Runtime | 1.24.4 (`onnxruntime-directml`), providers: DmlExecutionProvider, CPUExecutionProvider |
| OpenVINO | 2026.4.1, devices CPU, GPU.0 (UHD 630), GPU.1 (GTX 1650) |
| OpenCV / NumPy | 4.10.0 / 2.5.3 |
| Not installed | torch, ultralytics, tensorrt, onnx, pynvml |
| Model | `tools/security_vision/models/yolo26s.onnx`, 38,279,479 bytes, input `images` [1,3,640,640] float32, output [1,84,8400] |
| Production settings | 640 px letterbox (pad 114), RGB, /255, conf 0.35, NMS 0.45 (cv2.dnn.NMSBoxesBatched), 8 CPU threads, det-fps 5, analysis width 960 |

## C. Inference benchmark (synthetic tensor, 10 warm-up + 100 timed, ms)

Each engine in its own process (a crashing driver cannot affect the others), 3 rounds:

| Engine / device | Setup | Median (3 rounds) | p90 | p95 | min–max | Inferences/s | Status |
|---|---|---|---|---|---|---|---|
| DirectML · GTX 1650 | 1.06–1.13 s | 24.67 / 24.91 / 24.74 | ~25.7 | ~25.9 | 23.7–27.1 | ~40 | OK |
| DirectML · UHD 630 | 0.52–0.59 s | 148.8 / 150.9 / 152.0 | 156–163 | 159–176 | 140–199 | ~6.6 | OK |
| OpenVINO CPU (8 threads) | 0.98–1.07 s | 100.5 / 113.4 / 131.8 | 134–163 | 137–174 | 80–222 | 7.6–9.9 | OK, noisy |
| ONNX Runtime CPU (8 threads) | 0.30–0.34 s | 108.3 / 121.0 / 120.6 | 120–163 | 125–174 | 102–324 | 8.3–9.2 | OK |
| OpenVINO GPU.1 (GTX 1650, OpenCL) | 2.66–2.83 s | 297.8 / 294.1 / 294.2 | ~297 | ~299 | 290–303 | 3.4 | OK, slowest |
| OpenVINO GPU.0 (UHD 630) | — | — | — | — | — | — | **FAILED**: process crash 0xC0000005 every round |
| TensorRT | — | — | — | — | — | — | not tested (not installed; see F) |

The owner's interleaved script (`tools/benchmarks/benchmark_vision_engines.py`, 3 runs) gave
DirectML 52–58 ms median: it does not pin a DirectML device and interleaves CPU engines, so
it is a mixed measurement; with the GTX 1650 pinned and isolated the median is 24.7 ms.
GPU work is complete at each timing point (results are copied back to host NumPy arrays).
Peak VRAM in use with the detector loaded: 372 MB of 4,096 MB (whole GPU, other apps included).

**GPU execution verified**: with `session.disable_cpu_ep_fallback=1` the DirectML session
still loads on both adapters, i.e. ONNX Runtime assigned every node to DirectML (no silent
CPU fallback).

## D. Correctness

* Raw output vs DirectML (synthetic input): max |difference| 0.0029 (OpenVINO CPU), 0.0032 (ORT CPU).
* **Real frames, production pre/post-processing** (60 raw frames sampled evenly from the
  2026-10-12 16:02 and 17:02 recordings, resized to 960 px as the live analysis does; 0–5
  people per frame): all three engines produced **the same 1,044 detections** — same class in
  every frame, every CPU box matched (IoU ≥ 0.9; measured max coordinate difference < 0.001 px),
  no extra boxes, max score difference 3.5e-6.
* This is **parity with the current engine, not an accuracy measurement.** No labelled
  ground truth exists, so precision / recall / mAP were not computed. Not covered by the
  sample: empty lab at night, lighting changes, edge-of-frame and very small people as
  separate labelled cases.

## E. Real-time performance

Offline replay of the analysis pass on the same 60 frames (production code, 3 passes, ms median):

| Stage | ORT CPU | OpenVINO CPU | DirectML GTX 1650 |
|---|---|---|---|
| Pre-processing | 7.8 | 6.7 | 6.6 |
| Inference | 114.3 (p95 179) | 112.7 (p95 151) | **25.0 (p95 37)** |
| Post-processing + NMS | 2.8 | 2.2 | 1.8 |
| Tracker + appearance / re-ID | 158.1 (p95 417) | 141.1 (p95 380) | 134.0 (p95 376) |
| Whole analysis pass | 294.1 | 269.7 | **179.3** |

Sustained: 2,000 real-frame detections on DirectML, median 31.5–33.1 ms per 400-block,
p95 34–38 ms, process RSS flat at 458 MB, VRAM flat at 372 MB — no leak, no slow-down.

**Next bottleneck**: the body re-identification model (OpenCV DNN on the CPU) now costs more
than detection. **Not measured**: live RTSP acquisition / decode, portal submission and
camera-to-browser delay — at the time of the audit the running SecurityCam process (started
00:58) had received 0 frames (capture 0 fps, read via its own read-only `/metrics`), so live
end-to-end numbers could not be taken.

## F. TensorRT

GTX 1650 (Turing, compute 7.5) supports TensorRT incl. FP16. Not installed; the main Python is
3.14 (TensorRT wheels must match the Python version — verify before any setup; Python 3.12 is
also on this laptop and could host an isolated venv). Expected value is now low: inference is
25 ms of a 179 ms pass, so even halving it saves ~12 ms per pass while re-ID costs ~134 ms.
Not recommended until re-ID is addressed; needs the owner's approval (download + venv).

## G. Recommendation

Keep DirectML on the GTX 1650 as the first choice (already the default after a restart of the
camera service), OpenVINO CPU second, ONNX Runtime CPU last. OpenVINO GPU devices: do not use
(one crashes, one is 12x slower). Highest-value next step: run the re-ID model on the GPU too.

## H. Files

* `tools/benchmarks/benchmark_vision_engines.py` — owner's script, unchanged (run with `PYTHONIOENCODING=utf-8`: its "≈" crashes the cp1252 console).
* `tools/benchmarks/audit_engines.py` — isolated per-device benchmark, DirectML placement check, real-frame parity, per-stage replay.
* `tools/security_vision/test_engines.py` — 7 tests: forced CPU engine, OpenVINO failure → ONNX Runtime, GPU unavailable → fallback, all engines on black / wide / tiny frames, missing model.
* `tools/security_vision/start_security_vision.bat` — installs the DirectML / OpenVINO engines when missing.
* Tests: `tools/security_vision` 85 passed (78 existing + 7 new).

## I. Production status

Untouched during the audit: the running SecurityCam process (not restarted), camera settings
and credentials, door system, robots, live database, Docker services. The engine CODE default
became DirectML in commit ed56b8d (owner approved); the live process still runs the code it
started with until it is restarted.

