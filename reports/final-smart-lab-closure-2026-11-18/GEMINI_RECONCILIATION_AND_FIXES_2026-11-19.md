# Gemini Argon findings checked against the real system - 19 Nov 2026

Gemini's inspection (`C:\Projects\smart-lab-argon\reports\gemini-full-inspection-2026-11-19\`, 30 items) was run on
worktree `7619717`, before the `ecbb167` deploy. Claude checked every P0/P1 item and the code-level P2 items against the
current code, the live database (read-only SELECTs) and the running containers.

Work location: worktree `C:\Projects\smart-lab-claude-final`, branch `claude/final-closure-2026-11-19` (from `6e09864`).
**Nothing committed, nothing pushed, nothing deployed** from this worktree. The running portal is still `ecbb167`.

## Verdict per item

| ID | Gemini claim | Checked result | Status |
|---|---|---|---|
| B-01 | Live containers unstamped / pre-merge | Out of date: `/api/health` and `/version.json` both return `ecbb167-20261118231702` (JSON, not the SPA page) | NOT REQUIRED (already done) |
| B-02 | admin@ / ramy@ use the published default password | Not re-tested (would need a login with the default password); owner decision 18 Nov stands | OPERATOR ACTION REQUIRED |
| B-03 | Hemaly's PC on .100 clashes with FANUC .100 | Router/PC setting; cannot be fixed from software | OPERATOR ACTION REQUIRED |
| B-04/B-05 | Thesis LaTeX pin tables / door relay text outdated | Thesis source is the owner's (OneDrive); not edited | OPERATOR ACTION REQUIRED (writing week) |
| B-06 | Daily summary sums PC hours as robot hours | **Confirmed** in `robotics_watch.daily()` | FIXED - DEPLOYMENT NOT VERIFIED |
| B-07 | Daily false "offline" for `_SIM` robots and `TEST -` PCs | **Confirmed** in `robotics_watch._offline()` | FIXED - DEPLOYMENT NOT VERIFIED |
| B-08 | Retired cards still counted / shown | **Confirmed** on `/api/summary`, `/api/devices`, `/api/labs/{id}`, Lab Health Score, `/scan/markers`, `/api/opcua/snapshot` | FIXED - DEPLOYMENT NOT VERIFIED |
| B-09/B-10 | Firmware not flashed; VERIFY constants unmeasured | True; the nodes are at home | NEEDS HARDWARE |
| B-11 | Six thesis numbers have no measurement | True | OPERATOR ACTION REQUIRED |
| B-12 | Tracked raw report holds Windows user names | **Not confirmed** for the tracked files: `device_inventory_live.json` fields are uid/ip/firmware/state/notes/evidence, no user names. The untracked Gemini `raw/` folder is now git-ignored | FIXED (ignore rule) |
| B-13 | OA-5 names the wrong PC for agent 0.9 | **Confirmed** (live DB: `PC_GIULAB20-PC13`, card PC-10, is on 0.9; PC-13 is on 1.0). Corrected in OA-5, scorecard, executive report, OI-08 | FIXED AND VERIFIED (docs) |
| B-14 | Backup container stopped | **Confirmed** (Exited 137 since ~17:50); started with `docker compose up -d --no-deps backup`, now Up | FIXED AND VERIFIED (live) |
| B-15 | Duplicate offline / exam notifications | Not changed (n8n design; live workflows must not be edited) | UNVERIFIED / open P2 |
| B-16 | No retries on two GET nodes (04, 05) | **Confirmed** in the repo copies; `retryOnFail` 5 tries / 5 s added to `Get Offline Devices`, `Get Issue Context`, `Get Maintenance Digest`. Live n8n not touched | FIXED in repo copy only |
| B-17 | 3 knowledge workflows not in the repo | **Confirmed**; copied to `automation/n8n/json/knowledge/` (credential name only, no values) + README | FIXED |
| B-18 | 322 orphan mirror notes in the vault | Not changed: removing them is a deletion (rule: never delete) | OPERATOR ACTION REQUIRED (owner may delete) |
| B-19 | `kb.py health` crashes on a missing source | **Confirmed** by reading the code; a missing file is now reported as stale instead of `open()` failing | FIXED - knowledge suite 64 passed |
| B-21 | Unreachable code after `return out` in `scan.py ask()` | **Confirmed**; 9 dead lines removed | FIXED - DEPLOYMENT NOT VERIFIED |
| B-22 | Map GIU PCs to the `student-pc` marker art | **Rejected**: every art picture has its own QR baked into it (`marker_pack.ART` + `docs/markers_2026-10-27`); the GIU PCs would print PC_01's QR. GIU PCs correctly keep the generated pack card | NOT REQUIRED (would be a bug) |
| B-23 | OPC UA `online` is None for FACESRV / entry camera | **Confirmed**; OPC UA now uses the same state as the portal card (`device_out`), None only while a device has never reported | FIXED - DEPLOYMENT NOT VERIFIED |
| B-26 | Camera box names visible in the film | Still visible on purpose; owner decision | OPERATOR ACTION REQUIRED (decide) |
| B-27 | PC-11 sticker unconfirmed | True | NEEDS HARDWARE (lab visit) |
| B-20, B-24, B-25, B-28-B-30 | Lab re-measure, missing clips, thesis admin, doc drift, repo size | Not changed in this pass | open, see Gemini backlog |

## New finding (not in Gemini's list): film privacy
Checking the exported film frame by frame showed that **lab Windows account names were readable** in v1 at 48–54 s,
54–60 s and 168–175 s. A third person's name with clothing and position was also readable at 175–180 s, left over from the
"who is in the lab" answer. The earlier report said these were blurred or cut. Fixed in film v2 (details in
`VIDEO_EDITING_AND_CLIP_SELECTION_LOG.md`). v1 is kept at `D:\SmartLabData\showcase_2026-11-19\build\`.
v2 replaced the file at `C:\Projects\smart-lab-portal\reports\final-smart-lab-closure-2026-11-18\SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4`.

## Code changes (worktree, uncommitted)
| File | Function | Change |
|---|---|---|
| `backend/app/services/devices.py` | `is_retired()`, `is_simulated()` (new) | One shared rule: name starts `TEST -` / uid ends `_SIM` or source SIMULATION |
| `backend/app/services/robotics_watch.py` | `_offline()`, `daily()` | Skip retired + simulated devices; daily hours from non-sim robot sessions only |
| `backend/app/api/routes/admin.py` | `summary`, `list_devices` | KPI counts leave out retired + simulated rows; device list hides retired rows unless `?include_retired=true` |
| `backend/app/services/health_score.py` | `score_labs` | Retired rows no longer lower the device part |
| `backend/app/api/routes/labs.py` | lab status | Retired rows not in the lab's device list |
| `backend/app/services/scan.py` | `registry` | No marker for retired rows |
| `backend/app/api/routes/opcua.py` | `snapshot` | Retired rows left out; `online` from `device_out` (B-23) |
| `backend/app/api/routes/scan.py` | `ask` | Dead code removed (B-21) |
| `tools/knowledge/kb.py` | `health` | Missing source no longer crashes (B-19) |
| `backend/tests/test_retired_devices.py` | new | 4 regression tests (watch rules, daily hours, summary/list/lab/health/markers, OPC UA) |
| `automation/n8n/json/04-*.json`, `05-*.json` | repo copies | retries on the GET nodes |
| `automation/n8n/json/knowledge/` | new | 3 knowledge workflows + README |
| `.gitignore` | | `reports/gemini-*/raw/`, `*.bak-*` |

Nothing was deleted from the database: retired rows and their history stay, they are only left out of counts and lists.

## Tests (run 19 Nov from the worktree)
| Command | Result |
|---|---|
| `tools\ops\test_backend_fast.ps1 tests/test_retired_devices.py tests/test_robotics_watch.py tests/test_opcua_feed.py tests/test_scan.py tests/test_device_keys.py` | 33 passed |
| `tools\ops\test_backend_fast.ps1` (full suite, in-memory test DB) | **846 passed, 3 skipped** (460 s) |
| `py -m pytest -q tools/knowledge` | 64 passed |
| Frontend | not changed, not re-run |

## To make the fixes live (owner OK needed)
```powershell
cd C:\Projects\smart-lab-claude-final
git add -A; git commit -m "Retired/sim devices out of counts, alerts, markers, OPC UA; daily robot hours; kb health; n8n repo copies"
cd C:\Projects\smart-lab-portal
git merge --no-ff claude/final-closure-2026-11-19
powershell -ExecutionPolicy Bypass -File tools\deploy\build_images.ps1
docker compose up -d --no-deps backend
curl.exe -sk https://127.0.0.1/api/health   # check the new commit id
```
Rollback: `docker tag smart-lab-portal-backend:<previous id> smart-lab-portal-backend:latest` and
`docker compose up -d --no-deps backend` (the current image is `034e51c2a97b`, build `ecbb167`).
