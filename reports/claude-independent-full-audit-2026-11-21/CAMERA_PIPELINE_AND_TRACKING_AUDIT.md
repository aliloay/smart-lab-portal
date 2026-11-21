# Camera pipeline and tracking audit

## Live state: 2026-11-21 19:09 (LIVE-VERIFIED)

| | SECCAM_LAB01 (:5100) | SECCAM_LAB02 (:5101) |
|---|---|---|
| Process | `python.exe` 30172, Py 3.14, `--det-fps 6` | `python.exe` 19844, Py 3.14, `--det-fps 6` |
| `/health` status | "ok" (but `camera:false`) | "ok" (but `camera:false`) |
| Stream | **OFFLINE**, 317 fails in a row, "could not open the stream", since 11,886 s (launcher 15:50) | same |
| fps / frame_age / analysis_age | 0.0 / null / null | 0.0 / null / null |
| Zones | 17 | 13 |
| Portal state | DEGRADED ("service running, no picture"); alert 1107 open | DEGRADED; alert 1108 open |
| GPU | context only; 0 % util (918 MiB total including the face server) | |

- **Cause (evidence-based):** the IP cameras are physically at GIU. The services retry with backoff (`retry_in_s` up to 25.6 s).
- **Consequence:** no live capture FPS, analysis FPS, frame age, latency, ID switch, false positive or false negative figures can be produced today. All metrics below are **VERIFIED FROM CODE** or **SIMULATED**.
- **Tests:** `py -3.14 -m pytest -q tools/security_vision` gave **396 passed** (91 s). TESTED – PASSED, offline logic only.

## A. Pipeline trace

Main code: `tools/security_vision/security_vision.py` (1,767 lines) and `vision.py` (2,401 lines).

1. **Capture:** an OpenCV RTSP reader thread per camera. The URL comes from the git-ignored `camera.env` / `camera2.env` and was not printed. Reconnect with backoff; state machine `LIVE` → `OFFLINE`; `fails_in_row`, `retry_in_s`. Test: `test_camera_reconnect.py`.
2. **Buffering:** latest-frame semantics, so frames are dropped rather than queued. Analysis runs at `--det-fps 6`.
3. **Detection:**
   - Model: `models/yolo26s_544x960.onnx` (or `yolo26s.onnx` / `_416`), through ONNX Runtime DirectML on the GTX 1650.
   - Fallbacks: OpenVINO, ORT CPU, cv2.dnn (`vision.py:112-160`).
   - YOLOX is kept as a legacy option.
   - Classes shown: person, monitor, laptop, keyboard, mouse.
4. **Tracking (`vision.py` Tracker, :683-760):**
   - IoU plus appearance cost: `MIN_IOU 0.25`, `APPEAR_W 0.6`, `APPEAR_GATE 0.35`.
   - A track is confirmed after `CONFIRM_HITS 3`.
   - A track is lost after `MAX_MISS_S 2.0` while moving, or `MAX_MISS_STILL_S 6.0` while still (speed < 0.3 box heights/s).
   - A gap is any absence > 0.6 s. `REACQ_UNLIKE 0.65` means "someone else" after a gap.
5. **Re-ID:**
   - Model: `person_reid_youtu_2021nov.onnx` (128×256), through the DirectML → ORT-CPU → cv2.dnn chain.
   - Deep features at least every 2 s per person, and every frame while people are near each other (`NEAR_HOLD_S 2`).
   - People under 80 px tall get colour features only.
6. **Naming (Labeler, `vision.py:1029-1060, 1360-1362, 1682-1684`):**
   - Names come only from evidence: a door entry match within 25 s, or face votes (2 within 10 s).
   - Re-acquisition requires look distance ≤ 0.18 and a margin of 0.10 over everyone else in view.
   - A face-named look is remembered for 15 min.
   - A lost name waits 60 s for handback (place-only for 20 s, walk prediction 4 s).
   - A veto drops a name after 12 checks (about 3 s) at distance ≥ 0.65 on a full-body view.
   - **Design intent satisfied in code:** an uncertain person stays Unknown rather than inheriting a name (`false_names` must be 0 in `scenario_bench.py`).
7. **Cross-camera (`crosscam.py`, `labmap.py`):**
   - Floor-plane mapping (`floorcal.py`, `FloorMap`).
   - A look-based handoff when the feet are hidden.
   - One lab-wide person number across both cameras.
8. **Activity (`activity.py`):** posture from the box shape (standing, seated, bending, lying, moving), the nearest mapped object ("near" / "most likely at"), and the upper-body colour.
9. **Seat/PC presence (`vision.py:1848-1930`, `deskmap.py`):**
   - Seat box IoU 0.3, or seat cover 0.6.
   - IN_USE after 5 s; grace period 3 s; robot work area hold 20 s.
10. **Equipment moved (`equipwatch.py`):** reference patches with `CHANGE_AT 0.45`, motion thresholds and a settle time. A robot at rest in a new pose is logged as a pose change, not raised as an alert.
11. **Backend:**
    - Heartbeat plus `component_state` (`source_ok`, metrics, activity, `pose_visibility`) to `/api/security/...`.
    - The backend validates `pose_visibility` states (`routes/security.py:745-775`).
12. **Recording:** `recorder.py` writes to `recordings/`. Playback goes through the signed link (see F-01 for the token bug). Uploads are archived daily without retention (F-09).

### Where latency accumulates (from code)

- RTSP decode, then detector inference (DirectML), then re-ID crops. The re-ID cost is about 100 ms per person per the code comment, which is why it is capped at once every 2 s per person except in crowd moments.
- Then the Labeler and crosscam, then the HTTP report to the backend.
- Each camera runs its own process. The two processes share the GPU through `GPU_LOCK` only inside a process, so the two cameras contend at the driver level.
- **Repeated work:** each camera computes re-ID independently. The cross-camera matcher compares stored looks, so it does not recompute crops. That is efficient.

## B. Dead-zone recovery

**Not measured live; the analysis is from code.** In simulation only, `scenario_bench.py` and `bench_tracking.py` exist.

| Gap length | What the code does | Expected outcome (code reading, unmeasured) |
|---|---|---|
| < 0.6 s | same track continues (IoU/appearance) | no break |
| 0.6–2 s moving / 0.6–6 s still | track kept; re-matched with look check (`REACQ_UNLIKE`) | same ID if the look is not too different |
| 2 s / 6 s – 60 s | new track; the name returns by handback if place/walk-prediction plus look margin agree | **name returns after re-acquisition, with ≥ 3 confirmation hits (about 0.5 s at 6 fps) plus the look checks** |
| > 60 s | name only through re-acquisition (≤ 0.18 distance, 0.10 margin) or a face match | may stay Unknown, by design |

- **Measurement still needed:** time-to-correct-name after gaps of 1, 3, 10 and 30 s, with 1 and 2 people and similar clothing. See the plan file.
- **Do not call recovery "instant".**

## C. Pose and limbs (VERIFIED FROM CODE)

- **There is no keypoint or pose model** in the camera pipeline.
- `activity.py:51-90` `pose_visibility()`:
  - Places head, shoulders, torso, elbows, wrists, hips, knees and ankles at canonical body proportions inside the person box.
  - Marks each part **PREDICTED** (confidence 0.5, basis `box_geometry`), or **OUT_OF_FRAME** / **OCCLUDED** (xy=None) when the box is clipped or crowded.
  - **Never OBSERVED.** It does not invent coordinates for hidden parts, which is correct.
- **Sitting, standing, bending and lying** come from the box aspect ratio and its changes. **Reaching and leaning are not supported as measured behaviour.**
- **Verdict:** head and limb values are not measurements and must not be presented as pose estimation (F-16).

## D. Two cameras as one system

See TWO_CAMERA_ARCHITECTURE_AND_BENCHMARK_PLAN.md.

- The current design is already "independent inference + shared global identity": crosscam plus labmap.

## E. Live metrics

Unavailable today (streams offline). Historical numbers in the repo, from the checkpoints and the 19 Oct GPU test ("camera 1 7.0 → ~5 analyses/s with the AI on the GPU"), are **HISTORICAL** and were not re-measured.

## Findings

- **F-04 (P1):** cameras offline at home. All camera claims need GIU measurement.
- **F-16 (P2):** pose wording.
- **F-22 (P3):** `/health` returns "ok" while the stream is OFFLINE.
- The tracking thresholds are conservative and consistent with "never inherit a wrong name". This is a good design choice for a thesis.
