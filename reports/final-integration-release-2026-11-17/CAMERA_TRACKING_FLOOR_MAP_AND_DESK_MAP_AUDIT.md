# Camera tracking, floor map and desk map audit

**No live two-camera test was run in this integration.** Both camera services (:5100, :5101) were down at home and
the GIU LAN was not available. Every live item below is BLOCKED (on campus only). No claim of perfect tracking is
made: there is no labelled ground truth.

## Argon changes: verified line by line (STATIC INSPECTION) and by tests (UNIT TEST)
| Change | Verdict |
|---|---|
| crosscam: two tracks with different confirmed labels are never cross-paired when either identity is visible separately; links between conflicting confirmed labels are dropped | Stricter only. Never merges more. Kept. |
| crosscam: same confirmed label on both cameras may pair within GATE_WIDE_M (UR5e perspective gap 0.7-1.3 m), unless the appearance check vetoes it | Pairs only identical confirmed identities. Kept. |
| labmap: no lab-number merge across different confirmed names; a confirmed name reuses its stored number | Stricter / consistent. Kept. |
| labmap: the two register passes (number assignment + names by number) merged into one locked read-write | Behaviour-equivalent: the early return precedes both passes. One fewer locked JSON write per update (Argon bench 11.8 -> 8.6 ms/write, HISTORICAL REPLAY). |
| vision: a desk name is kept for a person the face camera already named | Kept (desk names stay hints elsewhere) |
| security_vision: identical CROSSCAM_CONFLICT log notes throttled to 1 per 30 s | Diagnostic notes only; identity decisions unchanged |
| activity: bottom-clipped boxes read "upper body in view" instead of "lying down / bending"; per-part visibility | Kept, **with the integration fix below** |

## Integration fixes (this release)
1. **No OBSERVED body parts.** The cameras run a person-box detector with no keypoint model. Argon's first version reported body parts as OBSERVED at 0.85 with coordinates taken from body proportions. They are now PREDICTED (confidence 0.5, basis "box_geometry"). Parts out of frame or likely hidden by a neighbour get xy=None (OUT_OF_FRAME / OCCLUDED). +1 test.
2. **Register lock under two processes.** On Windows, creating the lock file while the other camera deletes it raises PermissionError ("delete pending"). That escaped `_lock()` and made the whole lab-number pass fail; the camera loop caught it and skipped numbering for that frame. It is now retried like a held lock. Two-writer test: 13/15 passes before, 25/25 after. +1 deterministic test.
3. **Portal contract.** The new `partial` / `pose_visibility` keys are accepted by the backend and not stored (posture text already says "upper body in view"). A test pins this.

## Acceptance tests (prompt section 7)
| # | Test | Status |
|---|---|---|
| 1 | Both feeds at once, unique listener each, fresh frames | BLOCKED (on campus). launch.bat now refuses a second camera-2 copy (port 5101 check). |
| 2 | One person visible in both cameras -> one global track | UNIT TEST (test_crosscam); live BLOCKED |
| 3 | Camera 1 -> Camera 2 keeps the global ID | SIMULATED (Argon scenario bench 17/17; 1 ID switch + 1 fragment after a 25 s dead zone, 1 each after 3 min); live BLOCKED |
| 4 | Two confirmed people near the UR5e never cross-pair | UNIT TEST (new veto tests) + HISTORICAL REPLAY (17 Nov: 35 false links -> 0) |
| 5 | Feet occluded -> no fabricated floor coordinate | STATIC INSPECTION: crosscam.feet_floor() returns None for bottom-cut boxes; UNIT TEST |
| 6 | 25 s / 3 min disappearance | SIMULATED only (see 3). Remaining switches not reduced further: doing so without labelled data would risk false merges. |
| 7 | Similar clothing does not merge | UNIT TEST (look veto); clothing is shown only as a cautious description |
| 8 | Restart does not inflate "Person N" | UNIT TEST (register persistence); live BLOCKED |
| 9 | Bottom-clipped is not "lying down" | UNIT TEST (test_activity) |
| 10 | Desk map never names the wrong person (Hemaly) | UNIT TEST: desk guess on one person only, shown as "Eng. Hemaly?" and never confirmed; desk_map.json not changed |
| 11 | Face / door provenance distinct from desk / cross-camera inference | STATIC INSPECTION: sources face / door / operator / peer / desk / look; only face / door / operator / peer are kept as confirmed |
| 12 | Offline / stale / connecting shown in portal | UNIT TEST (camera list, source_ok); live BLOCKED |
| 13 | Auditable reason / confidence | identity_log notes with kind + detail; throttled duplicates only |

security_vision suite: **363 passed, 22 skipped, 0 failed** (UNIT TEST).

## Physical calibration still needed (BLOCKED, next lab visit)
Camera 1 `UR5e_front` floor anchor has a 0.50 m leave-one-out residual (HISTORICAL). Add a floor point near
(x=1.4, y=3.2) when it is unobstructed, re-run the calibration, then live tests 1-3, 6 and 8.
