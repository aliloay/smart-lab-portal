# Two-camera architecture and benchmark plan

**Status:** analysis plus a plan. Nothing here was benchmarked live: both streams were OFFLINE during the audit, because the cameras are at GIU.

## Current architecture (VERIFIED FROM CODE)

- Two processes (`security_vision.py --device SECCAM_LAB01 --port 5100` and `... LAB02 --port 5101`).
- Each process has its own capture, YOLO26s detection (DirectML), tracker and re-ID.
- **Identity is already global:**
  - `crosscam.py` uses floor-plane mapping (`floorcal.py`) plus a look-based handoff.
  - `labmap.py` gives one person number across both cameras.
- The camera-first GPU gate (`tools/knowledge/gpu_gate.py`) moves the LLM to the CPU while any camera analyses at more than 0.5/s.

## Options

| Option | Expected benefit | Expected cost / risk | Verdict before measurement |
|---|---|---|---|
| A. Independent inference + shared global tracker (current) | Simple; a fault in one camera does not stop the other; already tested (396 tests, `test_two_cameras.py`, `test_crosscam*.py`) | Two detector sessions on one GPU contend; re-ID per process | **Keep as the baseline** |
| B. Synchronised paired-frame processing | Consistent timestamps for handoff | Waits for the slower stream, so frame age rises; the RTSP clocks are not synced (`cam_clock.py` exists) | Only if handoff errors trace to time skew |
| C. Batched inference (one session, batch=2) | Fewer kernel launches; possibly higher total throughput on the GTX 1650 | Needs one process, or IPC to share frames; the model must have a dynamic batch dimension or be re-exported; a single point of failure | **The only candidate worth benchmarking** |
| D. Composite side-by-side image (stitching) | One inference per pair | The 544×960 input must shrink each view to about half width, so small or seated people get fewer pixels and recall drops; boxes crossing the seam; no real latency saving versus batching | **Not recommended** |
| E. Shared re-ID feature service | Avoids loading two re-ID sessions | Re-ID already runs ≤ 1 per 2 s per person; small gain | Low priority |
| F. Centralised global tracker process | Cleaner design | Rewrite risk before the defense | Not before the defense |

## Benchmark plan for GIU

Run in a quiet window, after Gemini's tests, with no other heavy GPU job. Record the conditions.

1. **Baseline (A).** Both services as launched (`--det-fps 6`). Sample for 10 minutes:
   - `/health` and `/metrics` every 1 s: `input_fps`, analysis rate, `frame_age_s`.
   - `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 1`
   - `typeperf` CPU and RAM.
   - Report p50 and p95 frame age, analysis FPS per camera, and dropped frames (input minus analysed).
2. **Load.** 1, 2 and 4 people walking, sitting and crossing.
   - Count ID switches, false names (must be 0), name switches and fragments from the annotated recording. `scenario_bench.py` metrics apply to the ground-truth annotations.
3. **Dead-zone recovery.**
   - One person leaves both views, or stands in the blind spot, for 1, 3, 10 and 30 s. Repeat 5 times each.
   - Measure the time from re-appearance until the correct name is shown, and whether a wrong name ever appears.
4. **Handoff.**
   - A person walks camera 1 → camera 2 with feet visible, then with feet hidden.
   - Measure handoff success and latency.
5. **AI contention.** Ask 5 assistant questions during the baseline. Confirm the gate keeps the LLM on the CPU and the analysis FPS does not drop.
6. **Option C prototype.** Only in a separate worktree, offline on recorded clips (`recordings/`, `pair_capture.py`):
   - batch=2 on the same ONNX with a dynamic batch.
   - Compare ms per pair, GPU memory, and recall on the annotated frames.
   - Production stays untouched.

**Decision rule:** adopt C only if it cuts p95 frame age or raises analysis FPS by a measured margin, without lowering recall or raising ID switches.

## Answer to Q16/Q17

- **Stitching:** not recommended.
- **Global identity:** a shared global tracker already exists and should stay.
- **Batching:** the only change worth testing.
- **Best measured architecture:** none has been measured live on this hardware yet. Keep the current architecture until the GIU benchmark is done.
