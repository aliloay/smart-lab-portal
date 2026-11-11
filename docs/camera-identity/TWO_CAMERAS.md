# Two security cameras - MC210 (camera 1) + MC200 1080p (camera 2)

Status: **SOFTWARE READY - camera 2 hardware not yet connected or verified.**

## Design (reuses the existing architecture)
* One service process per camera (`start_security_vision.bat [env file]`): own RTSP reader, latest-frame
  buffer (no backlog), detector, tracker, identities, zones, port. A camera that fails or disconnects
  cannot block the other (separate processes; measured below).
* Camera 1: `camera.env` (unchanged; port 5100 by default). Camera 2: `camera2.env` (copy of
  `camera2.env.example`): `DEVICE=SECCAM_LAB02`, `PORT=5101`, `SOURCE=` from the Mercusys app.
  All `camera*.env` files are git-ignored (fixed today - camera2.env was NOT ignored before).
* The backend reaches each camera at the port it reports (`component_state.port`); the portal's
  "All cameras" tab lists each security camera with its own online / source / fps status.
  Credentials stay in the env files and the process environment - never on the command line, in logs
  (`_safe` / `masked`) or in API responses.
* Per-camera files: `anchors/<DEVICE>*.npz` (looks, home, view), `recordings/identity_log_<DEVICE>.jsonl`.
* `launch.bat` starts camera 2 only when `camera2.env` exists; `stop_all.bat` closes both.

## Identity across cameras - limitation (honest)
Each camera names people **independently** with its own evidence (door entry, face, look, desk guess).
There is **no cross-camera merging**: track 3 on camera 1 and track 3 on camera 2 are unrelated, and the same
person may be named by one camera and Unknown on the other. Merging needs calibrated shared floor
coordinates (both views mapped to the room plan) plus appearance agreement - possible after camera 2 is
mounted and calibrated; not built, so nothing is ever merged by guess.

## Measured (simulated, 2026-10-14) - NOT hardware proof
| | camera 1 live alone | camera 1 + simulated camera 2 (recording, 2nd process) |
|---|---|---|
| analysis passes/s | 7.0 | 6.74 (cam 2: 6.95) |
| pass p50 / p95 | 85 / 106 ms | 102 / 143 ms (cam 2: 106 / 139) |
| GPU / VRAM | 36 % / 289 MB | 69 % / 578 MB |
Dead camera 2 (`rtsp://127.0.0.1:9/...`): service stays up, `camera:false fps:0`, retries every 3 s,
threads stable (62 -> 59), `open_failures` counted; camera 1 unaffected (7 fps, 0 errors).

## Hardware checklist (after the MC200 arrives)
1. Mount it diagonally opposite camera 1 (above Hemaly's drawer), 2.2-2.5 m, tilted down; power it.
2. Mercusys app: add the camera to the **Smart_Lab** Wi-Fi; turn OFF pan, auto-tracking, privacy mode.
3. App -> camera -> Advanced -> **Camera Account**: create user + password (keep them private).
4. Find its real IP (app device info or router client list). On the laptop:
   `ping -n 4 -S 192.168.1.200 <IP>` and `Test-NetConnection <IP> -Port 554` (TcpTestSucceeded True).
   Ask Claude to check the address is not already used before making it fixed in the router.
5. Copy `tools\security_vision\camera2.env.example` to `camera2.env`; put
   `rtsp://USER:<password>@<IP>:554/stream2` after `set SOURCE=` (URL codes for @ : in the password).
6. Double-click `tools\security_vision\start_security_vision.bat camera2.env` - window title
   "Smart Lab - Security camera SECCAM_LAB02"; expect `[detector] YOLO26 on directml-gpu1`,
   `[vision] re-id on directml-gpu1`, `[camera] streaming from rtsp://***@<IP>...`.
7. Portal -> Security camera -> All cameras: both live; draw camera 2's boxes (PCs, door) on its own picture.
8. `curl http://127.0.0.1:5101/health` and `:5100/health`: both `camera:true`, fps ~7.
9. Tests: empty room; one person; several; someone visible in both views; crossing between views;
   unplug camera 2's power 30 s (camera 1 keeps working, camera 2 shows offline, then recovers).
10. Ask Claude to read both `/metrics` (fps, pass p95, frame age, GPU) - compare with the table above.

## Update 2026-10-15 - camera 2 connected, identity lock, cross-camera names
**Camera 2 (MC200, firmware 1.0.2) - SOFTWARE VERIFIED at home:** Smart_Lab Wi-Fi, static 192.168.1.156 /
255.255.255.0 / gw+DNS 192.168.1.1 (address checked free first), MAC 08-8A-F1-40-55-A9. Local RTSP works
with the Camera Account (user name is case-sensitive: `Labcamera_2`): stream2 1280x720 and stream1
1920x1080, ~19.5 fps each. `camera2.env` (git-ignored) holds the address. Service SECCAM_LAB02 on port
5101 registered in the portal (DB dump taken first). Measured alone, live: analysis 6.6 passes/s, pass p50
110 ms / p95 165 ms (detect 54 + zoom 52), capture 14.8 fps, 0 reconnects, frame age at the portal p50 143 ms.
NOT yet: mounted in the lab, both cameras live together, calibration, crossing tests.

**Identity lock (vision.py, test_identity_lock.py - simulated):**
* Root cause 1 - the tracker matched boxes to tracks best-pair-first: two people side by side could lose
  a track (new id, name gone) or swap. Now one optimal assignment per frame (`assign_max`, Hungarian).
* Root cause 2 - names were also given by *elimination* (one free name, one unnamed person) and *by place*
  (a small box where a named person vanished). Both are guesses: off (`ALLOW_ELIMINATION`,
  `HANDBACK_BY_PLACE`). Unknown until the door, the face or a clear look-plus-face match says who.
* Kept: face needs score >= 0.50 AND 0.08 over the next person, 2 agreeing votes; a door name is never
  overwritten by one face; looks are frozen while people touch; one name on one person.

**Cross-camera names (crosscam.py, test_crosscam.py - simulated):** a CONFIRMED door/face name on one
camera moves to the unnamed person standing on the SAME floor spot (within 0.7 m) in the other camera,
after 4 passes in a row, never onto someone crowded / already named / whose own face says otherwise;
disagreements are logged, nothing changes. Needs each camera's floor map; without it nothing is shared.

**Speed (security_vision.py):** plain picture encoded only when asked for (was every frame); the
"two people in one box" zoom only for boxes 0.7-1.6 wide and every 2nd pass (a 2.2-wide box zoomed
every pass). Effect to be measured after the next restart (`/metrics`).

## Lab day - steps
1. Mount camera 2 diagonally OPPOSITE camera 1, 2.2-2.5 m high, tilted down; both on Smart_Lab.
2. Start both: `launch.bat` (or each `start_security_vision.bat [camera2.env]`). Check
   `/health` on 5100 and 5101: `camera:true`, fps ~7.
3. Room coordinates: pick ONE floor corner as (0, 0), x along one wall, y along the other, in metres.
   Put 6 tape marks on the floor that BOTH cameras see, spread out (not in a line); measure each (x, y).
4. `py floorcal.py camera.env` - click each mark, type its x y, press s. Same with `camera2.env`.
   "worst fit" should be under ~0.15 m. Restart both services (they print "floor map loaded").
5. Tests (ask Claude to read `/identity` and both `/metrics` after each):
   a. two named people shoulder to shoulder, 1 min;  b. they cross and swap places, 5 times;
   c. one turns their back to camera 1;  d. one walks behind the other;  e. one leaves, a stranger
   enters the same spot;  f. unplug camera 2 for 30 s - camera 1 keeps working, names stay;
   g. similar clothes if possible. Count wrong names (must be 0) and Unknown time.

## Update 2026-10-19 - both cameras live together, floor maps, cross-camera names (LIVE-VERIFIED)
* Both services on the GTX 1650 at 7.0 analyses/s each (pass p50 73 / 44 ms, GPU ~35 %, 578 MB). The AI
  assistants moved back to the CPU (OLLAMA_CPU_ONLY=true, knowledge llm_on_cpu): on the GPU an answer cut
  camera 1 to ~5/s (min 4.0); on the CPU (4 threads) both stayed at 7.0.
* Floor maps (anchors/SECCAM_LAB0x_floor.json): 5 tape marks on 0.61 m tiles, each confirmed by the owner
  standing on it; camera 1 +3 spots measured through camera 2. Fit <= 0.15 m, leave-one-out <= 0.36 m.
  Same person seen by both cameras: 0.27 m apart. Camera 1's face name appeared on camera 2 (live).
* Camera 2 boxes: UR5e, Fanuc (robot, no motion alert), PC-B..PC-L provisional (mapping to camera 1's
  PC-01..11 still to be given by the owner; PC-L half outside the picture flickers "changed").
* Box labels no longer overlap (vision.zone_tags, test_zone_tags.py). Camera clock: set at start, but the
  camera shows UTC+2 while Egypt is on UTC+3 until 2026-10-29.

## Update 2026-10-20 - wrong names found in the logs, fixed; coverage and appearance re-measured
Evidence: `recordings/identity_log_SECCAM_LAB0x.jsonl` and `crosscam_obs_*.jsonl` of 2026-10-19 (git-ignored).
Unit tests are TESTED OFFLINE; the cameras run the new code since 2026-10-19 23:40 but were off the lab
network, so nothing below is LIVE-VERIFIED yet.

**1. The desk rule named the wrong person (USER1/USER5 conflict - root cause).** In 4 episodes (16:14, 16:15,
17:02, 18:36) camera 1 named whoever sat at PC-09/PC-10 "USER5" (Hemaly) from a door entry hours old, while
camera 2's face matches said USER1 (Ali): 243 CROSSCAM_CONFLICT lines, 24 NAME_ON_TWO_PEOPLE. 546 of camera 1's
547 USER5 confirmations came from the desk. Fix (`Labeler.home_desk`): the desk only *continues* evidence - the
name was on a track within 120 s (`DESK_CHAIN_GAP_S`), or the door / face / other camera placed the person in
the lab within 10 min (`DESK_FRESH_S`); otherwise `DESK_NOT_USED` is logged and nobody is named.
`test_desk_evidence_2026_10_19.py` replays the 18:36 case (fails on the old code).

**2. Seated-person flicker.** The labeler only saw tracks detected in the last 0.6 s, while the tracker keeps a
still person's track for 6 s: every short detector miss behind a monitor logged NAME_LOST and let the desk give
the same name to a second track. Now tracks the tracker still keeps are passed as `coasting`: their names stay in
use and are reported lost only when the tracker lets go. Hand-back counts from when the person was last seen;
a walking person's name is looked for along their path (segment, not one spot), the look must still agree.

**3. Name kept on the wrong person after a crossing (camera 2, 19:05).** Nour's name was handed to camera 2
correctly (appearance 0.26 to camera 1's Nour, 0.67 to Ali); after Ali and Nour touched, camera 2's track carried
"USER6" while camera 2's own face matches said USER1 - the name stayed (by design: "not switched"). Now a name
that was only carried over (other camera, desk) is dropped when this camera's agreeing face matches (2) say
someone else and nobody touches; the face then names the person. Door names keep the mismatch flag (card
sharing). `test_face_overrides_carried_name.py` (fails on the old code). Face thresholds unchanged.

**4. Appearance between the cameras (observe mode) - corrected.** The 2026-10-19 report counted 4
different-person pairs; 2 of them (0.28, 0.38) used camera 1's desk-guessed "USER5" that camera 2's face called
USER1 - most likely the same person mislabelled. Clean data: same person n=119, median 0.30, p90 0.44, max 0.73;
different people n=2 (0.67, 0.70). Conclusion: not "appearance is unreliable" but "not enough different-person
data" - appearance stays OBSERVE-only. Needed: a recorded session with 2+ named people walking both views.

**5. Floor positions of the same person in both cameras:** median 0.41 m apart, p90 0.86 m (gate 0.7 m) - about
1 pair in 7 is rejected. Not widened (no different-person distances to check the risk); re-verify instead (below).

**6. Coverage from the two floor maps** (homographies projected on a 0.3 m grid; occlusion by desks / the FANUC
cell is NOT modelled; areas outside the calibrated points are extrapolated): both cameras see the floor across
the middle of the room (y about 3.5-8 m in the tile coordinates), camera 1 alone the far end (y > ~8 m), camera 2
alone the near end (y < ~3.5 m); about 1 % of the floor in neither. The 19:05 walk test matches: the name crossed
to camera 2 within 4 s of entering; the Unknown time (35 s on camera 2 after 19:05:23) was a track break where
only camera 2 saw the person and camera 1 had no floor position for him - not an unseen area.

**Physical steps (owner, at the lab):**
1. Before changing anything: copy `anchors/SECCAM_LAB01_floor.json` and `SECCAM_LAB02_floor.json`
   (rollback = put the copies back and restart the two camera windows).
2. Walk-test without moving the cameras: one person walks door -> desks -> FANUC -> UR5e -> door, slowly, twice;
   then two people (door entries each) cross and walk side by side. Ask Claude to read both identity logs and the
   obs logs: handover time, Unknown seconds, wrong names (must be 0), floor gaps per area.
3. Only if the walk shows an area where camera 2 alone sees people for long stretches: tilt camera 2 so that its
   view also contains the path into that area as seen by camera 1 (the overlap must include where people walk,
   not only where they sit), then re-click the 5 tape marks with `py floorcal.py camera2.env` (fit <= 0.15 m)
   and re-run step 2. Keep the old file if the new fit is worse.
