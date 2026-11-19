# Showcase V2: AR quality review (frame by frame)

## Sources reviewed
| Recording | Length | Verdict |
|---|---|---|
| `D:\SmartLabData\lab_2026-11-17\ar_test\AR_scan_test_2026-11-17.mov` (phone, 384×848, 60 fps, 17 Nov 2026) | 125 s | the only usable AR take; reviewed every 0.5 s from 5 s to 113 s (contact sheets `D:\SmartLabData\showcase_2026-11-19\contact\arq1-3.jpg`) |
| `OneDrive\Desktop\Bsc\lab_qr_2026-11-03\qr_walkthrough_IMG_6269.mov` | 0.97 s | too short (two frames of a marker); not usable |

In every frame I checked:
- whether the box sits on the right object;
- whether it lags behind the camera;
- whether the label is wrong;
- whether the overlay covers the object;
- whether the assistant text belongs to the object on screen;
- whether the phone is stable;
- whether the marker → live-data step is visible.

## Timeline of the 17 Nov take

| Time (s) | What is on screen | Verdict | Reason |
|---|---|---|---|
| 5.0–7.5 | UR5e, "Motion detected" popup over the top third | **cut** | popup covers the view |
| **8.0–15.5** | UR5e box, "UR5e robot 59 % → 67 % → 60 %"; assistant: "This looks like ur5e robot - recognised from its appearance only, not confirmed" | **used** | box on the arm, stable, honest wording |
| 16.0 | fast pan, box left behind | **cut** | lag |
| 16.5–17.0 | "Motion detected" popup | **cut** | popup |
| **17.5–29.5** | UR5e marker: box 52 % → scan → "UR5e (physical) LIVE" over the marker; assistant: "connected - telemetry 0 s ago", "State STATIONARY, control RTDE …" | **used** | clean marker scan and live data |
| ~30.0 | LIVE box slips below the marker for one beat | **cut** (V2 stops at 29.5) | lag |
| 30.5–32.5 | state text continues (robot mode RUNNING, safety NORMAL) | not used | sits next to the 30.0 slip, and 29.5 already shows the scan |
| 33–36 | small "monitor - unidentified" / "Door controller" labels at the bottom edge | **cut** | stray labels |
| 36.5 | a person passes (motion blur) | **cut** | privacy |
| 37–41 | walking to the FANUC, popups | **cut** | no content |
| 41–45.5 | FANUC box 84 %, but the assistant line still shows the **UR5e** joints ("Joints: Base -138° …") | **cut** | information belongs to another robot |
| **46.0–50.0** | FANUC box "FANUC ER-4iA robot 89 %"; assistant: "This looks like fanuc robot - recognised from its appearance only, not confirmed" | **used** | correct object, stable |
| 50.5–51.0 | pan, box lags | **cut** | lag |
| 51.5–53.0 | "Motion detected" popups | **cut** | popup |
| **53.5–60.5** | FANUC marker → "FANUC ER-4iA (physical) LIVE"; assistant: "connected - telemetry 2 s ago" | **used** | clean marker → live data |
| 61–68 | box drifts, floor, popups | **cut** | lag / no content |
| 69.0–72.5 | **"person 60 %" box on the master node**; "monitor - unidentified", "laptop - unidentified" | **cut** | wrong detections |
| 73.2–77.6 | master node close-up, no boxes | used as **hardware footage only** (no AR claim) | clean prototype shot |
| 80.5–82.0 | **"Door controller (master node) 80 %" drawn on the black environment node / reusable bin** | **cut** | wrong object |
| 82.5–83.0 | door controller 82 % on the master node | not used | too short |
| 83.5–85.5 | environment / reusable labels half out of frame | **cut** | partial boxes |
| 86.0–89.0 | **"Door controller (master node) 93 %" on the black bins** | **cut** | wrong object (V1 quoted this "93 %": corrected in V2) |
| **91.0–98.0** | "Environment node 90–92 %", "Reusable items bin 82–90 %", "Consumables bin node 75–80 %", each box on its own object; assistant: "This looks like environment node - recognised from its appearance only, not confirmed" | **used** | three correct, stable detections |
| 99.0–99.5 | popups | **cut** | popup |
| 100–102.5 | "Scan its QR marker" while the camera moves; boxes lag at 101.5–102.5 | **cut** | lag |
| **103.0–107.6** | "Door controller (master node) 88–89 %" on the master node; assistant: "This looks like master node - recognised from its appearance only, not confirmed" | **used** | correct object |
| 108.0 | the box stays on the scale while the camera moves | **cut** | lag |
| 109–110.5 | **"Door controller 54 %" on the consumables scale**; "keyboard - unidentified" | **cut** | wrong object |
| 111.5–113 | "Consumables bin node 58 %" plus a keyboard label | **cut** | low confidence and a stray label |
| ~114–125 | a person's face | **cut** | privacy |

## What V2 shows
- **Clip 1** (speed 1.45×): 8.0–15.5 + 17.5–29.5. UR5e recognition, then marker scan, then LIVE telemetry.
- **Clip 2** (speed 1.5×): 46.0–50.0 + 53.5–60.5 + 91.0–98.0 + 103.0–107.6. FANUC 89 %, then FANUC marker → LIVE, then the three nodes, then the master node.
- The status bar and notification area (rows 0–116 px, where a phone number appeared) are cropped from every AR frame.
- Side labels quote only values that are visible in the chosen frames:
  - UR5e 59–67 %;
  - FANUC 89 %;
  - environment node 92 %;
  - reusable bin 90 %;
  - consumables bin 80 %;
  - master node 89 %.
- The narration says recognition is "appearance only until the marker is scanned", which is exactly what the app displays.
- No box was moved, redrawn or faked. Freeze frames were not needed.
