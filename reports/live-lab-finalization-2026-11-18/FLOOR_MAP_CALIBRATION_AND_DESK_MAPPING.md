# FLOOR_MAP_CALIBRATION_AND_DESK_MAPPING.md

- **Evidence Class**: `LIVE_PHYSICAL` (calibrated on-site at GIU on 18 Nov using 8 new two-camera standing pairs + 16 recorded PC/robot seats) + `STATIC_INSPECTION`.

---

## 1. Floor Map Coordinate Frame & Homography Residuals (`LIVE_PHYSICAL`)

### 1.1 Coordinate Convention
- **Image Coordinates (`px`)**: Normalized `[x, y]` in `[0.0, 1.0] x [0.0, 1.0]` where `(0, 0)` is top-left of the `960x540` analysis frame and `feet` are projected from `(box_x + box_w / 2, box_y + box_h)` when `box_y + box_h < frame_h - 3`.
- **Floor Coordinates (`floor`)**: Room metres `[x_m, y_m]` inside `ROOM_M = (-1.0, 8.0, 0.0, 12.0)` (based on `0.61 m` floor tiles in `LAB_01`).

### 1.2 Before vs After 18 Nov On-Site Refit (`SECCAM_LAB01_floor.json` & `SECCAM_LAB02_floor.json`)

Today at GIU (commit `6606ed5`), 8 new two-camera standing pairs (`pair14..pair21` covering the UR5e, whiteboard, FANUC, and `PC-12/13` aisle) were captured and refit:

| Camera Floor Map | Total Points (`Unique`) | Fit Median Error (`m`) | Fit p90 Error (`m`) | Fit Max Error (`m`) | Leave-One-Out (LOO) Median (`m`) | LOO p90 (`m`) | LOO Max (`m`) | Within `0.70 m` Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **`SECCAM_LAB01` (17 Nov Baseline)** | `7` (`7`) | `0.080 m` | `0.290 m` | `0.360 m` | `0.240 m` | `0.450 m` | **`0.500 m`** (`UR5e_front`) | `1 / 8` today's spots before refit |
| **`SECCAM_LAB01` (18 Nov Refit — Live)** | `37` (`29`) | **`0.164 m`** | **`0.304 m`** | **`0.395 m`** | **`0.197 m`** | **`0.331 m`** | **`0.419 m`** (`pair17`) | **`7 / 8` (`100% < 0.42 m` LOO)** |
| **`SECCAM_LAB02` (18 Nov Refit — Live)** | `31` (`26`) | **`0.173 m`** | **`0.352 m`** | **`0.411 m`** | **`0.214 m`** | **`0.429 m`** | **`0.625 m`** (`mark 5`) | **`100% < 0.70 m` gate** |

- **Audit Note on Duplicate Tape-Mark Weighting**: In both `SECCAM_LAB01_floor.json` (`marks 2..5, A, C, D, E` repeated twice = 8 duplicate rows) and `SECCAM_LAB02_floor.json` (`marks 2..5, A` repeated twice = 5 duplicate rows), `floor_refit.py` intentionally duplicated the physical tape-mark anchors so `cv2.findHomography(..., method=0)` weights physical tape marks `2x` relative to single-frame person-pair captures. Leave-one-out (`LOO`) residuals above were computed **excluding all duplicate rows of the held-out point** so the LOO error is never artificially lowered by a duplicate row.

---

## 2. Desk Map & Recorded Seat Calibration Audit (`LIVE_PHYSICAL` + `STATIC_INSPECTION`)

### 2.1 Recorded Seats (`anchors/SECCAM_LAB01_seats.json` & `SECCAM_LAB02_seats.json`)
Today on-site at GIU (`14:22–15:14`), `seat_capture.py` recorded 10-sample bounding boxes for:
- **Camera 1 (`SECCAM_LAB01_seats.json` — 16 spots)**: `UR5E`, `UR5E@STAND`, `FANUC`, `PC-01`, `PC-02`, `PC-04`, `PC-05`, `PC-06`, `PC-07`, `PC-09`, `PC-10`, `PC-11`, `PC-12`, `PC-13`, `PC-14`, `PC-15`.
- **Camera 2 (`SECCAM_LAB02_seats.json` — 11 spots)**: `UR5E`, `UR5E@STAND`, `FANUC`, `PC-06`, `PC-07`, `PC-08`, `PC-09`, `PC-10`, `PC-11`, `PC-12`, `PC-13`.
- **Cross-Camera Desk Link (`anchors/desk_map.json`)**: Links `PC-05` through `PC-13` between `SECCAM_LAB01` and `SECCAM_LAB02`.

### 2.2 Desk Mapping Protections Verified
1. **Best-Fitting Seat Rule (`vision.py:1937-1940`, commit `610279e`)**: On Camera 1, far-away seats (`PC-13`, `PC-14`, `PC-15`) partially overlap in perspective. Each seated person now activates **at most one** recorded seat (`max(iou(s, p))`), preventing one seated student from marking 3 adjacent PCs `IN_USE`.
2. **Closer-Camera Deferral (`security_vision.py:887-916`, commit `610279e`)**: When both cameras are live (`peer_at < 3.0 s`) and the other camera's recorded seat height is `>= 1.5x` (`DEFER_RATIO`) taller (e.g., Camera 2 sees `PC-06..PC-13` close up at `h = 0.18..0.38` while Camera 1 sees them far away at `h = 0.05..0.15`), Camera 1 sets `z["defer"] = True` and defers `IN_USE` judgment for those desks to Camera 2.
3. **One Person Per Desk Guess (`vision.py:1552-1575`)**: `desk_hints()` assigns `"Eng. Hemaly?"` (`HOME_DESKS = {"USER5": ["PC-04", "PC-01"]}`) to at most **one** unnamed seated person (closest center in desk widths), and suppresses the hint whenever `Eng. Hemaly` is already named anywhere in the frame.
4. **Advisory Finding on `PC-01` vs `PC-04` Seat Boxes on Camera 1**: In `SECCAM_LAB01_seats.json`, `PC-01` (`[0.5964, 0.4818, 0.0202, 0.0308]`) and `PC-04` (`[0.5964, 0.4844, 0.0196, 0.0285]`) were both captured at `15:14` on nearly the same `2% x 3%` head region behind the far monitor row (`IoU = 0.85`). Because both `PC-01` and `PC-04` belong to `Eng. Hemaly` (`HOME_DESKS["USER5"]`), this does not mis-attribute another person's desk, but `PC-01` and `PC-04` should be re-captured separately when someone sits at each individual monitor.
