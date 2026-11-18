# FIXES_AND_CHANGED_FILES.md

- **Worktree**: `C:\Projects\smart-lab-argon`
- **Branch**: `opt/gemini-live-lab-finalization-2026-11-18` (based on `fix/pre-lab-hardening` commit `610279e`, which already includes Argon's 17 Nov commit `fe126b7`).

---

## 1. Summary of New 18 Nov Live-Lab Fixes Implemented by Gemini (`opt/gemini-live-lab-finalization-2026-11-18`)

| # | Priority | Subsystem | Exact File & Lines | Symptom & Root Cause (`LIVE_PHYSICAL` / `LIVE_SERVICE`) | Fix Implemented & Verified |
|---|---|---|---|---|---|
| 1 | **`P1`** | Vision / Global Person Register | `tools/security_vision/labmap.py:158-345` | **Live symptom (`16:54:32`)**: `lab_people_LAB_01.json` accumulated 85 entries (`next: 749`), including **8 separate entries (`'3','4','5','6','9','16','22','34'`) all carrying `who.auth_subject == "USER6"`**. Camera 1 restored `"USER6"` (`nour ramy`) onto `Person 3` (at UR5e) while Camera 2 restored `"USER6"` onto `Person 4` (at `PC-09`) simultaneously; `_confirmed_back()` saw `len(gone) > 1` and refused to restore; and when `Labeler._veto()` dropped a stale look on a track, `labmap` forced the name back onto that same track every 6 s.<br>Additionally, during `LOOK_WAIT_S` (`1.5 s`), `assign()` locked and rewrote the 550 KB JSON file on every frame even when no track in `need` was ready, causing `track_ms` p95 spikes (`282.9 ms`, max `527.8 ms`). | 1. Enforced **Single-Owner Invariant** in `people`: an `auth_subject` can sit on at most one entry in `people`; writing `e["who"]` strips/deletes duplicate entries.<br>2. Deleted `merged_away` ghost numbers from `people` upon `LAB_NUMBER_MERGED` / `LAB_NUMBER_BACK`.<br>3. Guarded `names_by_number` with `peer_held_no` (never restore a name onto `t.lab_no` if the other camera holds it on a different `lab_no`) and `self.restored_once` (never restore the same `(t.id, subj)` twice onto the same `t.id`).<br>4. Deduplicated `_confirmed_back()` candidates by `auth_subject`.<br>5. Added `ready_need` pre-check so `reg.update()` is skipped when unnumbered tracks are still waiting for `LOOK_WAIT_S`. |
| 2 | **`P1`** | Vision / Identity Provenance | `tools/security_vision/identity.py:42` | **Live symptom (`16:44:16`)**: `security_vision.py:666` called `_give(..., how="came back (same look)")`, which was missing from `REACQUIRE_HOW` (`identity.py:42`), causing look-based restores to emit `PERSON_IDENTITY_CONFIRMED` at `0.80` instead of `PERSON_TRACK_REACQUIRED` at `0.65`. | Added `"came back (same look)"` to `REACQUIRE_HOW`. |
| 3 | **`P1`** | Vision / Seated PC Posture | `tools/security_vision/activity.py:121-141, 232-242` | **Live symptom (`16:54:32` on `SECCAM_LAB02`)**: `track 21` seated at `PC-09` (`y = 0.49..0.75`) had its lower body occluded by the monitor/desk in the middle of the frame (`r = h/w < 0.8`), so `activity.py` reported `"nour ramy (black top, black trousers) - lying down - at PC-09"`. | Passed `at_pc = bool(nz and nz[1] and nz[0].upper().startswith("PC-"))` to `posture()`: a person at a PC desk with `r < 2.2` reports `"seated or leaning"` (never `"lying down"`), suppresses `legs` colour when `r < 1.4` (`desk_occluded`), and marks lower-body joints `OCCLUDED` (`xy=None`). |
| 4 | **`P1`** | Robot Telemetry Collector | `tools/robot_monitor/robot_collector.py:279-307` | **Live symptom (`16:44–16:54`)**: Both `UR5E_01` (`.102:30003`) and `FANUC_01` (`.100:80`) were unreachable (`system:10060` / `ConnectTimeout`), yet `robot_collector.py` called `self.report(now)` with `snap["state"] == "UNKNOWN"` every 2–3 s, posting `/robots/telemetry` and `/equipment/state` (`state="IDLE"` because `"UNKNOWN" != "TELEMETRY_STALE"`), keeping both powered-off robots `is_online = true, state = IDLE` in DB and OPC UA! | Skip `/robots/telemetry` when `snap["state"] == "UNKNOWN"`, post `TELEMETRY_STALE` only **once** per drop (`self._stale_reported`), and only post `/equipment/state` when `snap["state"] in ("MOVING", "STATIONARY")`. |
| 5 | **`P2`** | Knowledge / RAG Query Timeout | `tools/knowledge/kb.py:508-521, 582-586` | `kb.py:embed()` used a `120 s` timeout even for single-query interactive `search()`, risking a 2-minute hang on `/ask` if Ollama was cold-loading. | Added `timeout` parameter to `embed()` and set interactive `search()` embedding timeout to `4.0 s` (`query_embed_timeout_s`) with instant fallback to BM25. |
| 6 | **`P2`** | Terminal / Docker Build Stamp | `launch.bat:239-249` | **Live symptom (`16:43:07`)**: `/api/health` returned `version.id = "unstamped"` because `launch.bat:242` ran plain `docker build` without `--build-arg BUILD_COMMIT` / `BUILD_TIME` when rebuilding at GIU. | Updated `launch.bat` to invoke `tools\deploy\build_images.ps1` so every `launch.bat` rebuild stamps `BUILD_COMMIT` and `BUILD_TIME` and tags a rollback image. |

---

## 2. Complete List of Changed Code & Test Files on `opt/gemini-live-lab-finalization-2026-11-18` (Since `610279e`)

| File Path | Change Summary |
|---|---|
| `tools/security_vision/labmap.py` | Single-owner invariant in `people`, `merged_away` ghost cleanup, `ready_need` lock guard, `peer_held_no` + `restored_once` guard, `_confirmed_back` deduplication by `auth_subject`. |
| `tools/security_vision/identity.py` | Added `"came back (same look)"` to `REACQUIRE_HOW`. |
| `tools/security_vision/activity.py` | `at_pc` seated posture rule (`"seated or leaning"` instead of `"lying down"` at a PC desk) + `desk_occluded` legs/visibility handling. |
| `tools/security_vision/test_labmap.py` | Added `test_single_owner_invariant_prevents_one_name_on_multiple_numbers` and `test_merged_number_is_removed_and_restore_does_not_loop_on_same_track`. |
| `tools/security_vision/test_activity.py` | Added `test_person_seated_at_pc_desk_with_short_occluded_box_is_never_lying_down`. |
| `tools/robot_monitor/robot_collector.py` | Prevented `UNKNOWN` / repeated `TELEMETRY_STALE` from posting `/robots/telemetry` or `/equipment/state` `IDLE`. |
| `tools/robot_monitor/test_collector.py` | Added `test_unreachable_robot_at_startup_is_not_reported_online_or_idle`. |
| `tools/knowledge/kb.py` | Added `query_embed_timeout_s = 4.0` bound on interactive `search()` embedding calls. |
| `launch.bat` | Delegated image rebuilds to `tools\deploy\build_images.ps1` so `BUILD_COMMIT` and `BUILD_TIME` are always stamped. |
