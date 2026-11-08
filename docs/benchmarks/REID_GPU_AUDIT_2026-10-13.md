# Person re-identification on the GPU — audit 2026-10-13

Measured on this laptop 2026-10-13 02:58–03:25 with `tools/benchmarks/reid_audit.py` and
`tools/benchmarks/audit_engines.py stages`, on 60 raw frames sampled from the 2026-10-12 lab
recordings (166 person crops, 0–5 people per frame; frames kept outside git). Raw JSON in
`tools/benchmarks/results/` (git-ignored). Snapshot branch before the change:
`snapshot/before-reid-gpu-20261013-0258`.

## A. Baseline — and a production bug

* Model `person_reid_youtu_2021nov.onnx`: input `input` [batch, 3, 256, 128] float32 (RGB,
  /255, ImageNet mean/std), output [batch, 768, 1, 1]; L2-normalised; used as 60 % of
  `look_distance` (colour histograms 40 %). Runs every 2 s, and every frame while people are
  close / just apart (`Appearance.wants_deep`).
* Production ran it with **cv2.dnn (OpenCV 4.10), all crops of a frame in one batch.**
* **Bug found**: cv2.dnn returns correct embeddings only for the FIRST batch size it ever runs.
  With a fresh network and batches in the order 1,2,3,5: batch 1 cosine +1.000 vs ONNX
  Runtime, batches 2/3/5 −0.08 / −0.10 / −0.15 (unrelated vectors); same for any order. ONNX
  Runtime gives identical embeddings at every batch size (cosine 1.000). In the live camera the
  number of people changes all the time, so most deep embeddings were wrong — on real crops,
  163 of 166 nearest neighbours differ from the correct ones. This can explain identity
  mix-ups seen in the lab.
* The earlier audit's "134 ms re-ID" was tracker + colours + re-ID together. Separated
  (re-ID every frame, median ms per frame): colours 1.5, crops 4.3, **inference 218**
  (p95 418), L2 0.1; tracker alone 0.36.

## B. Compatibility

DirectML loads the model on both adapters with CPU fallback DISABLED (every node on DirectML).
Standalone inference, synthetic input, 10 warm-up + 100 timed, median ms:

| Engine | batch 1 | 2 | 3 | 5 | 8 |
|---|---|---|---|---|---|
| cv2.dnn CPU (production) | 64.4 | 127.7 | 211.9 | 313.0 | 479.5 |
| ONNX Runtime CPU | 29.8 | 57.0 | 85.4 | 141.6 | 221.3 |
| DirectML UHD 630 | 99.1 | 199.9 | 227.3 | 316.7 | 415.8 |
| **DirectML GTX 1650** | **9.0** | 32.1 | 37.8 | 48.9 | 58.8 |

On the GTX 1650 one crop at a time (9 ms each) beats batching up to 5 people, and batch 1 is
also the only size cv2.dnn handles correctly — so every engine now runs one crop at a time.

## C. Performance (same 60 frames, offline replay of the analysis pass, median ms)

| | Before (detector on GPU, re-ID cv2.dnn batched) | After (both on GTX 1650) |
|---|---|---|
| YOLO26s inference | 25.0 | 24.5 |
| Tracker + appearance + re-ID | 134.0 (p95 376) | **23.4 (p95 56)** |
| Whole analysis pass | 179.3 | **63.2** |
| Max passes / s | 5.6 | 15.8 |

Speed-up of the whole pass: 179.3 / 63.2 = **2.8x** (measured). Re-ID every frame, sustained
1,200 passes: detector 32–33 ms with or without re-ID (no contention), appearance + re-ID
24–26 ms median (p95 ~53), RSS flat ~483 MB, VRAM 508 MB of 4,096 MB. CPU fallbacks
measured too: ONNX Runtime CPU re-ID ~30 ms a crop.

## D. Correctness

* All engines in the new code agree (tests: cosine > 0.999 between DirectML, ONNX Runtime CPU
  and cv2.dnn-at-batch-1); embedding unchanged when the crowd size changes (the regression test).
* Preprocessing, embedding size, `look_distance`, thresholds (0.35 / 0.45 / 0.65, swap 0.05)
  unchanged.
* **Behaviour will change — on purpose**: decisions are now made with correct embeddings
  instead of mostly random ones. The thresholds were set while embeddings were partly wrong,
  so identity behaviour must be re-checked live (two people, crossing, sitting). Not
  measurable offline without labelled identities.

## E. Implementation

* `tools/security_vision/vision.py` — `Appearance`: engine order DirectML (fastest adapter by
  a 7-run median timing, must beat 25 ms a crop) -> ONNX Runtime CPU -> cv2.dnn; one crop at a
  time; a failed crop keeps its colour look and tracking continues; engine logged at start
  (`[vision] re-id on ...`). `SMARTLAB_REID=cpu|opencv` forces a fallback.
* `tools/security_vision/test_reid.py` — 8 tests (crowd-size regression on 3 engines, engine
  agreement, GPU unavailable -> CPU, inference failure, no model / no people, tiny boxes).
* `tools/benchmarks/reid_audit.py` — this audit.
* Tests: `tools/security_vision` 93 passed. Detector code unchanged.

## F. Recommendation

Keep it: correct embeddings (bug fix) and a 2.8x faster pass. Batching does not help on this
GPU; the CPU-side work left (colours, crops) is ~6 ms.

## G. Production status

Live camera process not restarted (still the old code), camera settings, credentials, door,
robots, live database and Docker untouched. Nothing pushed.

## H. Rollout (owner)

Restart the Security camera window (or `launch.bat`); expect `[detector] YOLO26 on
directml-gpu1` and `[vision] re-id on directml-gpu1`. Then test identity live with two people
(walk past each other, sit, stand): names must stay on the right person.
Rollback (verified 2026-10-13, not executed): fastest, no code change - add `set SMARTLAB_REID=cpu`
to `tools/security_vision/camera.env` and restart the camera window (re-ID on ONNX Runtime CPU,
correct embeddings). Code rollback: `git checkout snapshot/before-reid-gpu-20261013-0258 --
tools/security_vision/vision.py` (re-ID code only; it brings the batch bug back), undone with
`git checkout HEAD -- tools/security_vision/vision.py`.

## I. Pre-rollout verification (2026-10-13, later)

* Old code from the snapshot vs HEAD, real model, same person seen alone, then in a crowd of 6,
  then alone again: OLD cosine -0.1324 / -0.0984 (wrong even after the crowd left), NEW +1.0000 / +1.0000.
* 7 more tests in `test_reid.py` (15 re-ID tests): crop-to-embedding correspondence in any order,
  crowd 1->2->6->3->0->1, one failed person (others keep embeddings, no stale vector),
  model loaded once and always batch 1, tiny crop does not shift the others, DirectML start-up
  failure -> CPU, real model 6 people vs one at a time on all three engines.
  `tools/security_vision`: 100 passed.
* Full pass repeated: 61.0 / 60.9 ms (DirectML detector + re-ID), re-ID chose the GTX 1650 every time.
* Live acceptance procedure with pass/fail criteria: `docs/LAB_TEST_2026-10-14.md` section 1.
