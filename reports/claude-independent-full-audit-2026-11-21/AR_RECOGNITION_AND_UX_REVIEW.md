# AR recognition and UX review

## Active models (VERIFIED FROM CODE)

### `backend/data/models/detectors.json` → `lab_detector.onnx` (37.9 MB, 17 Nov 23:16)

- **Version:** **v8 "ft_y11s"**: YOLO11s, the v7 model fine-tuned for 40 epochs on lab_v8.
- **The brief's "v7" is outdated.** v8 replaced it on 17 Nov; a v7 backup is kept at `D:/SmartLabData/model_backups/2026-11-17_before_v8/`.
- **Recorded results (HISTORICAL; owner/Colab measurements, not re-run):**
  - single 178/183, multi 222/238, camera 240/240.
  - 17 Nov photos 34/35; 17 Nov camera 283/290; 23 extra boxes.

### 12 classes, with confidence threshold and database mapping

| Index | Class | Conf | Maps to | Max instances |
|---|---|---|---|---|
| 0 | reusable_bin | 0.5 | `SLAB:D:REUSE_BIN_1` | 1 |
| 1 | consumables_node | 0.5 | `SLAB:D:BIN_NODE_1` | 1 |
| 2 | environment_node | 0.5 | `SLAB:D:ENV_LAB01` | 1 |
| 3 | master_node | 0.5 | `SLAB:D:MASTER_LAB01` | 1 |
| 4 | network_switch | 0.25 | (none) | 1 |
| 5 | network_router | 0.7 | (none) | 1 |
| 6 | ur5e_robot | 0.5 | `UR5E_01` | 1 |
| 7 | ur5e_teach_pendant | 0.5 | (none) | 1 |
| 8 | fanuc_robot | 0.28 | `FANUC_01` | 1 |
| 9 | fanuc_teach_pendant | 0.5 | (none) | 1 |
| 10 | lab_pc | 0.5 | **(none)** | **16** |
| 11 | lab_door | 0.5 | (none) | 1 |

### Bin detector

- `bin_detector.onnx` (YOLO11n) is **not run while `lab_detector.onnx` is loaded**, because the lab detector answers for the bin. See the note in `detectors.json` and `services/bin_detector.py`.
- So the "separate bin detector round 4" is effectively inactive in AR.
- The `CONF 0.45` comment in `bin_detector.py` mentions round 5.

## Pipeline (VERIFIED FROM CODE)

### Phone (`frontend/src/pages/Scan.tsx`, 1,033 lines)

- **Camera:** `getUserMedia`, only when `window.isSecureContext`. The portal is served over HTTPS (:443/:8443), so the secure-origin rule is met. On plain HTTP the page explains the problem (line 200).
- **QR / marker decoding:** client-side jsQR in a worker (`qrWorker`, 131 KB). Runs every 250 ms (`DECODE_EVERY_MS`), slowed from 120 ms because phones heated up.
- **Object detection:** server-side through `POST /api/scan/identify`. Runs **every 3 s with no marker in view, every 6 s with markers in view** (lines 585-596).
- **Pins:** smoothed position (`0.5` blend within a 1.5 s hold).
- **Cards:** refreshed every 5 s; the selected robot every 1 s; others every 3 s. Each card shows its own timestamp.
- **iPhone handling:** a video watchdog (700 ms) and voice integration.

### Server (`backend/app/services/scan.py`, `bin_detector.py`)

- ONNX Runtime on the CPU in the backend container. Historical figure: about 162 ms per image on the CPU.

## Does the overlay correspond to the right equipment, with fresh values?

- **Robots and nodes:** yes, by construction. Each class maps 1:1 to a single device (one UR5e, one FANUC, one of each node), and cards come from the live device API with their timestamps.
  - At home today, both robots are OFFLINE with last data from 18 Nov. The robot card must and does show stale or offline (`robotLive.tsx effective()`).
- **Lab PCs: no.** `lab_pc` has no code mapping. A box says "lab PC" but cannot tell which PC (10 look alike). A specific PC's live data needs its QR marker. **The thesis should state this.**
- **Switch, router, pendants and door:** labels only, with no live data.

## Issues

1. **Detection delay:** a 3–6 s server cadence plus about 160 ms of inference, so boxes lag phone motion. There is no client-side tracking between detections.
2. **Box stability:** the only smoothing is on marker pins. Object boxes jump at every server answer.
3. **False labels:** the per-class thresholds are tuned (switch 0.25, FANUC 0.28, router 0.7). The low switch and FANUC thresholds increase false-positive risk. Recorded extra boxes: 23 on the evaluation set (historical).
4. **Phone performance:** unmeasured in this audit. No measured end-to-end figure (frame capture → box shown) exists in the repo that I could verify.
5. **Unsupported devices:** handled by the secure-context check. Older browsers without `getUserMedia`: there is a message.

## Prioritised AR upgrade proposal (no change made)

| Priority | Change | Why | Effort |
|---|---|---|---|
| 1 | Measure first: log `t_capture → t_response → t_draw` for 50 detections on the owner's phone at GIU | No latency claim exists today | S |
| 2 | Client-side box tracking between server detections: optical flow, or a constant-velocity IoU tracker on the canvas, with boxes faded after 1.5 s without confirmation | Smooth boxes without more server load | M |
| 3 | Adaptive cadence: 1–1.5 s while the phone is still (the existing motion thumbnail `STILL_MAD` logic), 3 s while moving | Faster first box | S |
| 4 | PC identity: show "Lab PC – scan its QR for live data" on a `lab_pc` box, or map by the camera-calibrated seat map when the phone is at a known spot | Prevents a wrong PC card | S |
| 5 | False-positive suppression: require 2 consecutive detections before drawing switch or FANUC boxes (thresholds below 0.3) | Fewer phantom labels | S |
| 6 | Model size: try YOLO11n v8-fine-tune or int8 quantisation offline and compare against the recorded evaluation sets (`tools/vision_train/eval_detector_sets.py`) | Lower server latency | M |
| 7 | Remove the unused `bin_detector` path or document that it is a fallback | Clarity | XS |

**I do not claim any recognition performance numbers here.** The table numbers above are historical records from `detectors.json`.
