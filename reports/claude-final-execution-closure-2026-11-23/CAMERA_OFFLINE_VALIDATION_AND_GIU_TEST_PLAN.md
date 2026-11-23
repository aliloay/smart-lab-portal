# Camera offline validation and GIU test plan

## Where it stands (23 Nov)
- **Services:**
  - `SECCAM_LAB01` (port 5100) and `SECCAM_LAB02` (port 5101) run the `d023e98` code. Both were started 23 Nov as independent processes.
  - Both `/health` return 200 with `status: no_picture` and `stream.state: CONNECTING`. The new `thread_restarts: {}` field shows no worker has crashed.
- **Streams:** not reachable from this network, so the camera fixes are **tested offline only**.
- **Offline tests:** 414 camera tests pass (412 before, plus 2 new tests added on 23 Nov for V-F10 and V-F12).

| Fix | Offline evidence | Live evidence |
|---|---|---|
| V-F1 dead stream withdraws people | unit test | needs GIU step 3-5 |
| V-F2 frame analysed once, stale cut-off 2 s | unit test | needs GIU step 1 (fps vs analysis rate) |
| V-F3 look-only name is a guess | unit test | needs GIU step 7-9 |
| V-F5 thread supervisor | unit test; `/health` field live | GIU: `thread_restarts` stays `{}` for the run |
| V-F6 / V-F10 / V-F12 identity bookkeeping | unit tests | GIU step 9 |
| V-F7 / V-F8 / V-F13 pose | unit tests | GIU step 10 (screenshot of the skeleton overlay) |
| V-F9 pose CPU threads | `V_F9_CPU_POSE_BENCHMARK.md` (offline) | GIU step 10 |

## GIU run (owner present, about 30 min, both cameras)
**Before:** run `launch.bat` on the engineer laptop at GIU. Open the portal at Security → Live with both cameras in split view. Open a PowerShell window for the checks.

The `/peer` endpoint needs the device key in the `X-Device-Key` header (from `camera.env`). Don't paste it into reports.

| # | Step | Expected | Pass if |
|---|---|---|---|
| 1 | Check both feeds | Both tiles show "live"; `/health` on 5100 and 5101 has `status: ok`, `fps > 0`, `stream.frame_age_s < 2` | both true for 1 min |
| 2 | One person stands in camera 2's view only | Camera 2 shows a box, "Person N" or their name | box within 2 s |
| 3 | **Owner** pulls camera 2's network cable for 10 s | - | - |
| 4 | Watch camera 1 and the portal | Camera 1 names nobody new from camera 2's area; `/peer` on 5101 returns `tracks: []` within about 2 s (STALE_S) | no name appears on camera 1 because of camera 2 |
| 5 | Watch camera 2's status | Tile turns "no picture"; `/health` 5101 `status: no_picture`; the person disappears from the live bar | within 5 s |
| 6 | Plug camera 2 back in | `stream.state` goes CONNECTING → OK; the tile shows "live" again | within 30 s, `thread_restarts` still `{}` |
| 7 | A known person leaves; a similarly dressed person enters within 2 min, face turned away | Shown as "Name ? (look)" at most | never a confirmed name without a face |
| 8 | The newcomer faces the camera | The guess is replaced by their own name (face), or Unknown | the original person's name is never confirmed on them |
| 9 | Two people cross paths in front of camera 1 | Each keeps their own label, or one becomes Unknown | no swap of names; never one name on two boxes |
| 10 | Measure load: Task Manager CPU %, and the pose ms lines in each camera console window | Pose about 60 ms/pass at 1 pass/s (21 Nov measurement); total CPU not pinned at 100% | record CPU %, pose ms p50/p95 for 5 min |
| 11 | Leave it running for 10 min | No crash; `thread_restarts` `{}`; analysis fps steady | all true |

**Record:**
- screenshots of steps 4, 5, 7 and 9;
- the `/health` JSON of both cameras before, during and after the cable pull;
- the text of both camera console windows (copy it from the window; the services log to their console).

Save them under `reports\giu-camera-validation-<date>\` and blur faces before sharing.

**If step 4 or 8 fails:** stop the run, keep the logs, and note the time. A wrong name is a release blocker for the camera identity feature. Hand-back by place alone is already off (`HANDBACK_BY_PLACE = False` in `vision.py`), so the next safe fallback is to stop look-based re-acquire and rely on face naming only (owner decision, code change).
