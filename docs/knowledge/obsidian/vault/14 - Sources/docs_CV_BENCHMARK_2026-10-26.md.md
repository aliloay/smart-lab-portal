---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/CV_BENCHMARK_2026-10-26.md"
source_hash: "a9b4e3b27abf8ece4173013cc9102b917b2185585a9f5ff1fd057b018c85bdd2"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/CV_BENCHMARK_2026-10-26.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md]] - mentioned by docs
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs
- [[docs_SMART_LAB_COMPLETE_STATUS_REPORT_2026-10-27.md]] - mentioned by docs
- [[tools_security_vision_models_README.md]] - mentioned by docs
- [[tools_security_vision_security_vision.py]] - mentioned by docs
- [[tools_security_vision_test_tracking_2026_10_26.py]] - mentioned by docs

# Camera detector + tracker benchmark (2026-10-25/26)

Measured on this laptop (NVIDIA GTX 1650 4 GB, DirectML via onnxruntime-directml 1.24, Python 3.14), on **our own
lab recordings** (camera 1, 2026-10-12, 2304x1296 @ 15 fps) and 7 camera-2 stills. Nothing below is a vendor number.
The cameras were not reachable from home: **no live camera was tested**; everything is replayed recordings.

## Method

* **Detection set:** 123 frames (one every 75 s across 2.5 h of lab recording + camera-2 plain views), fed exactly as
  the live service sees them (960x540). Ground truth: proposals from a high-resolution ensemble (YOLO26s, YOLO11s,
  RT-DETR-L at 544x960 and RF-DETR-M on the full 2304 px frame, plus a 2x2 tiled pass), merged by votes; **every
  proposal with <= 3 votes or < 45 px was reviewed by eye** (150 crops: 27 rejected - shoes / bags / posters / hand
  fragments, 27 duplicates), and an audit of 14 frames found **no missed person**. 363 people: 227 seated/partial,
  74 occluded, 102 small (< 60 px), 109 standing in full view. Match: IoU >= 0.5.
  *Bias:* YOLO26s, YOLO11s, RT-DETR-L and RF-DETR-M helped propose the ground truth (YOLOv8/v10 did not).
* **Tracking set:** 3 continuous clips at the live analysis rate (10 frames/s): A 120 s busy (5 people), B 120 s
  (4 people, one ends visible only as a head behind the FANUC cell), C 90 s (5 people). Ground-truth tracks from
  RF-DETR-M boxes linked offline, **every identity checked by eye on crop strips**, ID switches split and merged by
  hand; 264 tangled frames (2.6 %) are not scored (identity changes across them still count). Metrics follow the
  TrackEval definitions (HOTA, AssA, DetA; IDF1; CLEAR ID switches / fragmentation), implementation self-checked.
* **Speed:** end-to-end detect() (pre-process + inference + NMS) on a real frame; then **two processes at once** at
  the live 10/s pace; then the **full camera service x 2** (tools/perf/load_simlab.py) next to simulated robots, an
  environment node, dashboard polling and - in one run - the Lab AI answering questions non-stop.

Scripts and raw results: scratch folder of the 2026-10-25/26 session (`cvbench/`: detlib, eval_det, gt_*,
run_live_tracker, run_boxmot, mot_metrics, score_tracks); frames show people and are not in the repository.

## Detection (123 frames, 363 people, conf 0.35)

| Model / input | AP50 | Precision | Recall | Seated/partial | Occluded | Small | ms / frame (1 process) |
|---|---|---|---|---|---|---|---|
| **YOLO26s 640x640 (live until today)** | 0.928 | 0.956 | 0.898 | 0.881 | 0.851 | 0.843 | 29.7 |
| YOLO26s 384x640 (same scale, no pad) | 0.928 | 0.956 | 0.895 | 0.881 | 0.851 | 0.843 | 17.4 |
| **YOLO26s 544x960 (chosen)** | 0.944 | 0.960 | 0.923 | 0.912 | 0.824 | 0.882 | 36.4 |
| YOLO11s 544x960 | 0.953 | 0.982 | 0.917 | 0.907 | 0.797 | 0.814 | 34.5 |
| YOLOv8s 544x960 | 0.942 | 0.957 | 0.923 | 0.912 | 0.784 | 0.833 | 36.7 |
| YOLOv10s 640 | 0.930 | 0.969 | 0.865 | 0.837 | 0.743 | 0.716 | 31.7 |
| YOLO26n 544x960 | 0.927 | 0.968 | 0.846 | 0.811 | 0.716 | 0.647 | 21.9 |
| YOLO11n 640 | 0.895 | 0.943 | 0.736 | 0.678 | 0.622 | 0.529 | 23.9 |
| RT-DETR-L 640 (some nodes on the CPU) | 0.965 | 0.868 | 0.964 | 0.965 | 0.919 | 0.931 | 84.3 |
| RF-DETR Nano (384) | 0.934 | 0.880 | 0.912 | 0.899 | 0.811 | 0.833 | 40.2 |
| RF-DETR Small (512) | 0.965 | 0.870 | 0.942 | 0.947 | 0.865 | 0.882 | 80.1 |
| RF-DETR Medium (576) | 0.973 | 0.903 | 0.970 | 0.969 | 0.919 | 0.941 | 113.2 |

The transformer detectors find the most half-hidden people but are 2-4x slower on this GPU (no tensor cores) and
cannot run two cameras at 10/s. RT-DETR-L cannot run fully on DirectML (the live service forbids silent CPU nodes).

## Tracking (3 clips, 310 s, 14 people; mean over clips)

| Configuration (same cached detections) | HOTA | IDF1 | ID switches | Fragments | Missed boxes | False boxes | Tracks for 14 people |
|---|---|---|---|---|---|---|---|
| **Live until today** (YOLO26s 640, conf 0.35) | 0.732 | 0.831 | 14 | 67 | 1,366 | 376 | 24 |
| + low-confidence stage 0.15 | 0.735 | 0.832 | 12 | 65 | 1,188 | 489 | 22 |
| YOLO26s 544x960 + low stage | 0.763 | 0.824 | 22 | 74 | 798 | 566 | 29 |
| + upper-body part boxes dropped | 0.766 | 0.829 | 19 | 75 | 800 | 551 | 27 |
| + new-track threshold 0.50 | 0.771 | 0.847 | 15 | 72 | 835 | 536 | 24 |
| **+ new-track threshold 0.60 (chosen)** | **0.779** | **0.874** | **12** | **66** | **1,042** | **422** | **21** |
| + new-track threshold 0.70 | 0.774 | 0.870 | 12 | 66 | 1,146 | 422 | 21 |
| YOLO11s 544x960 + low stage | 0.722 | 0.778 | 24 | 91 | 1,320 | 892 | 31 |

Published trackers on clip A (boxmot 25.0.0, defaults, 10 frames/s, same YOLO26s-640 detections; the live tracker
scores 0.744 / IDF1 0.917 there): HybridSORT 0.758 / 0.937 (135 ms per update on the CPU), BoT-SORT 0.687 / 0.830,
OC-SORT 0.688 / 0.826, ByteTrack 0.617 / 0.730, BoostTrack 0.606 / 0.665, StrongSORT 0.571 / 0.589 (91 ms),
Deep OC-SORT 0.519 / 0.585 (204 ms), SFSORT 0.268 / 0.320. Appearance-based trackers cost 90-200 ms per frame on the
CPU (OSNet x0.25) - too slow for two cameras at 10/s - and none beat the lab's own tracker, which already has
appearance gates, posture/turn handling and the still-person rules. Not run: TrackTrack (PyTorch + FastReID
research code, no packaged release), FastTracker (no public code found).

## Two cameras on one GTX 1650 (full service x 2, 120 s, simulated lab around them)

| Configuration | Analysis /s (cam 1 / cam 2) | Pass p50 | Pass p95 | Frame age p95 | GPU |
|---|---|---|---|---|---|
| Live until today, AI idle | 7.8 / 8.9 | 103-106 ms | 134-156 ms | 79 ms | 73 % |
| Live until today, AI answering | 8.2 / 8.4 | 117-119 ms | 158-165 ms | 86-89 ms | 62 % |
| New detector, zoom at 544x960, AI idle | 7.5 / 7.6 | 129-130 ms | 171-177 ms | 79 ms | 72 % |
| New detector, zoom at 544x960, AI answering | 7.1 / 7.3 | 145-152 ms | 186-221 ms | 87-89 ms | 59 % |
| **New detector + zoom model 416, AI idle (chosen)** | **9.4 / 9.9** | **84-91 ms** | **115-129 ms** | **80 ms** | n/a* |

\* the GPU sampler read 0 % during that run (nvidia-smi sample), the earlier runs show 60-73 %.
Per-stage split (p50, two cameras): main detection 58-72 ms, **zoom 64 ms -> 20-24 ms with the 416 model**,
re-ID 2-21 ms, tracker + naming ~2 ms. Zoom recovers only 1-2 of 13 hidden people the full-frame pass missed (any
input size), so its cost had to come down. With the AI answering on the CPU the system CPU reached 98 % and both
cameras slowed (row 4): the AI's CPU threads are the next limit (AI mission).

## Chosen configuration (now the service defaults)

`models/yolo26s_544x960.onnx` (input 544x960 = the analysis frame, no square letterbox), conf 0.35, low-confidence
stage 0.15 (only keeps confirmed tracks alive, never starts one, never changes a look), new-track threshold 0.60,
upper-body part boxes dropped, zoom crops through `models/yolo26s_416.onnx`. Identity rules unchanged: names only
from the door / face evidence; Unknown is preferred over a wrong name; a hand alone never makes a person or a name.

## Not verified / remaining

* Live cameras (both) - needs the lab network; cross-camera handoff accuracy was **not** measured (no synchronized
  two-camera video exists; only 6 paired stills).
* Camera-2 detection rests on 1 scored still (its other stills have the live overlay drawn in).
* The ground truth is one reviewer's judgement (this session); tangled frames are excluded.

