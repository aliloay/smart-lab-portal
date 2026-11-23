# V-F9 CPU pose benchmark - 23 Nov 2026 (offline)

## Conditions (stated honestly)
| Item | Value |
|---|---|
| When | 23 Nov 2026, about 06:10 |
| Hardware | Dell G3 3590: 6 cores / 12 threads, 32 GB, GTX 1650 4 GB |
| Model | `yolov8n-pose.onnx` (`tools/security_vision/models`), onnxruntime CPU EP, 640×640 letterbox |
| Code | `pose.PoseModel.infer` from the main checkout (identical to `d023e98`) |
| Footage | recorded `SECCAM_LAB01_2026-11-17_10-08-29.mp4` and `SECCAM_LAB02_...mp4`, 60 frames each, spread over the file. Only timings were kept; no frames were saved |
| Load | **heavy**: the V3 video re-render was running at the same time (about 90% total CPU, 12 render processes). Absolute times are therefore pessimistic. The **ratios** between settings are what this benchmark shows |
| Camera services | running but idle (`no_picture`), so no pose work of their own |

Script: `tools/perf/vf9_pose_bench.py` (a copy of the scratch script is listed in the evidence index).

## Results
| Setting | Frames | p50 ms | p90 ms | p95 ms | Mean ms | Cores used (CPU time / wall) | Poses per frame |
|---|---|---|---|---|---|---|---|
| CPU, `SMARTLAB_POSE_THREADS=2` (the V-F9 default), camera 1 footage | 60 | 351.7 | 510.0 | 584.3 | 359.9 | **1.14** | 1.23 |
| CPU, onnxruntime default threads (before V-F9), camera 1 footage | 60 | 260.4 | 421.6 | 535.7 | 285.0 | **3.26** | 1.23 |
| Two processes at once, 2 threads each (both cameras): camera 1 | 60 | 245.8 | 583.6 | 618.0 | 306.2 | 1.28 | 1.23 |
| Two processes at once, 2 threads each (both cameras): camera 2 | 60 | 275.2 | 466.7 | 508.8 | 305.6 | 1.28 | 2.07 |
| DirectML (GPU) with CPU fallback disabled, as `PoseModel.load` tries first | - | - | - | - | - | - | **fails**: the graph has nodes DirectML cannot run, so the service falls back to CPU |

## What this shows
1. **V-F9 does what it claims.** One pose session drops from about 3.3 cores to about 1.1-1.3 cores. Two camera processes together use about 2.6 cores instead of up to 6.5, so they no longer fight each other or the detector for every core.
2. **The cost:** a single pose pass is about 25-35% slower at the median under heavy load (352 vs 260 ms). The p95 values are close (584 vs 536 ms). Pose runs once a second per camera (the 21 Nov measurement), so this fits inside the 1 s budget even under this load.
3. **Pose runs on the CPU in practice.** The DirectML attempt with fallback disabled fails for this model, and the service then uses the CPU path. The GPU stays free for the person detector, which matches the "cameras first" rule. The `GPU_LOCK` around pose therefore never applies on this laptop.
4. **The 21 Nov figure of 62 ms per pass** was measured with an idle CPU. It cannot be compared with this loaded run. Repeat at GIU with both live streams and nothing else running (step 10 of the GIU plan).

## Status
- **V-F9: TESTED - PASSED (offline, under load).** Core-use reduction confirmed.
- Live latency: **NEEDS GIU HARDWARE**.
