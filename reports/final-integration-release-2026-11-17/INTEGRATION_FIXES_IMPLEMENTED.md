# Integration fixes implemented

Each fix lists: symptom, evidence, root cause, change, test, before/after, risk and rollback.

## F1 (P1): pose parts claimed OBSERVED without a keypoint model (commit 35f8cb4)
- **Symptom:** Argon's `pose_visibility` returned head, elbows, wrists and other parts as OBSERVED (0.85) with xy coordinates.
- **Root cause:** the coordinates are fixed body proportions inside the person box. The cameras run a box detector only (no pose model in tools/security_vision).
- **Change:** in-box parts are PREDICTED (0.5, basis "box_geometry"); cut-off or hidden parts get xy=None. Files: tools/security_vision/activity.py, test_activity.py.
- **Test:** +1 test (a full standing box is never OBSERVED); Argon's test updated.
- **Risk:** none. No consumer used the field, and the backend does not store it.
- **Rollback:** revert 35f8cb4.

## F2 (P2): lab-number register lock failed under two camera processes (35f8cb4)
- **Symptom:** intermittent `test_two_processes_writing_at_once_never_share_a_number` (20 of 40 numbers) and a PermissionError on `lab_people_*.json.lock`.
- **Root cause:** on Windows, O_CREAT|O_EXCL on a file the other process is deleting raises PermissionError. `_lock()` caught only FileExistsError, so the whole `assign()` pass raised. The camera loop caught it and skipped numbering for that frame.
- **Change:** PermissionError is retried like a held lock. File: tools/security_vision/labmap.py.
- **Test:** +1 deterministic test. Before: 13/15 passes. After: 25/25.
- **Risk:** low. The 0.5 s bound is unchanged.

## F3 (P3, test-only): face-server auto-enrol tests failed outside their folder (35f8cb4)
- **Root cause:** ENGINE fell back to LBPH (model paths are relative to the working directory; the models are git-ignored), so the endpoint answered 501.
- **Change:** the fixture pins ENGINE=sface. Service code is unchanged.
- **Result:** 14 passed / 1 skipped, from the repo root and from the folder.

## F4 (P1): /api/health reported a stale build; deploy.py could not build (bdc41aa)
- **Symptom:** health showed 1be41ab (28 Oct) after newer builds, or "unstamped".
- **Root cause:** a git-ignored app/build_info.json was baked in by `COPY . .`, and `docker compose build` is a no-op since Compose v5.
- **Change:**
  - Dockerfile ARG/ENV stamp; `_build_info()` prefers it; the stamp file is in .dockerignore.
  - deploy.py uses `docker build`.
  - New tools/deploy/build_images.ps1.
  - Frontend /version.json, served by nginx with no-store.
- **Test:** +4 tests.
- **Live result:** health and /version.json both report df3407f-20261118094636.
- **Rollback:** previous images are tagged pre-rc-20261118.

## F5 (P2): incidents payload and server work on every 20 s poll (b685a43)
- **Change:**
  - SQL-side state and lab filters with exactly state()'s meaning.
  - Only page rows are built.
  - `view=summary`.
  - Keyset cursor `limit` / `before` / `next_cursor` (URL-safe digits).
  - The old default contract is kept.
  - Portal: summary rows, "N of total shown", "Load older incidents". warm.ts path updated.
- **Test:** +3 tests (lean summary with the default unchanged; cursor pages complete with no duplicates; state/lab SQL rules incl. a stale RESOLVED column).
- **After (live, same run):** 134,418 -> 81,353 B raw, 11,685 -> 6,961 B gzip, p50 23.4 -> 20.0 ms.
- **Found during testing:** a first cursor format containing an ISO "+" broke unencoded clients, and was replaced by epoch microseconds.

## F6 (P2): camera activity contract (b685a43)
Test pinning that the backend accepts and drops `partial` / `pose_visibility`. The allow-list is unchanged (the portal
does not need these keys).

## Integrated from the prior branches (verified, kept)
- **Claude:** LazyMotion (motion chunk 26.3 kB gzip); incident cap after filters.
- **Argon:** cross-camera veto; same-identity wide gate; labmap no-merge of different names; desk-name keep; conflict-log throttle; bottom-clip posture; GPU gate STREAMING; knowledge /health + qwen2.5:1.5b defaults; relay fallback bind with the ACL kept; USB kit EOL-safe manifest; watchdog health probes; camera-2 singleton guard in launch.bat; firmware source fixes (consumables HTTP backoff, ESP-CAM non-blocking reconnect, reusable WiFi.setSleep(false) after reconnect).

## Not changed on purpose
- **Live n8n workflows** (agents may not edit them): recommendation in N8N_AND_OBSIDIAN_INTEGRATION_AUDIT.md.
- **Account passwords** (owner only): P0 in SECURITY_RBAC_AND_PRIVACY_AUDIT.md.
- **Door firmware:** not changed.
- **sensor_evaluation index:** P3.
