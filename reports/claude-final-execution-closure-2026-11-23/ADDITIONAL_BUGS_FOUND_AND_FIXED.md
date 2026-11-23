# Additional bugs found and fixed - 23 Nov 2026

Worktree `C:\Projects\smart-lab-claude-closure`, branch `claude/final-closure-2026-11-23`, base `d023e98`. **Not committed**: committing needs the owner's OK.

## C-01 (P1) - Double face approval still possible (B-11 fix ineffective)
- **Root cause:** `face_submissions.approve()` first loads the submission (`db.get`), then calls `_waiting_or_409()`, which re-reads it with `with_for_update=True`. SQLAlchemy emits the `SELECT ... FOR UPDATE`, but it does not overwrite attributes of an object already in the session's identity map. If a second Approve was waiting on the lock, it saw its own stale `status == "PENDING"` copy after the first request committed `APPROVED`. It then sent the photos to the face server and enrolled the person a second time.
- **Fix:** `db.get(FaceSubmission, sid, with_for_update=True, populate_existing=True)` in `backend/app/api/routes/face_submissions.py::_waiting_or_409`. This is the same pattern already used in `services/emergency.py`.
- **Test:** `backend/tests/test_closure_2026_11_23.py::test_locked_reread_sees_an_approval_committed_meanwhile`. Before the fix: **FAILED** (did not raise 409). After: passed, together with the 19 face-submission tests (20 passed).
- **Same pattern elsewhere:** every other `with_for_update` in `backend/app` is the first load of its row in the request (asset checkout/return, emergency act/normal) or already uses `populate_existing`. Not affected.
- **Deployment:** see `GITHUB_AND_DEPLOYMENT_STATUS.md`.

## C-02 (P1) - FAQ question-word and negation checks were dead code (K1 fix ineffective)
- **Root cause:** in `tools/knowledge/agent.py`, `_QWORD` and `_NEG` contained five literal backspace characters (0x08) where `\b` word boundaries were meant. The 22 Nov edit script passed `\b` through a shell heredoc, which turned it into the control character. So the patterns could never match: `_faq_qword()` returned `None` for every question, and `_faq_neg()` was always `False`. The K1 tests still passed, because the word-coverage rule (≥ 0.8) happened to reject their cases. A question like "When is X open?" against an FAQ "Where is X?" was protected only by coverage, not by the question-word rule.
- **Fix:** the control characters were replaced with `\b`. The whole repository was then scanned for control characters in every file changed since `9378f20`. Only `agent.py` (code) and one Windows path in `docs/PROGRESS_CHECKPOINT.md` (`\a` became BEL) were affected; both were repaired.
- **Test:** `_faq_qword("Where is the Robotics Lab?")` now gives `where` (was `None`), and "Why doesn't the door open?" gives `why` with negation `True`. Knowledge suite: 81 passed.

## C-03 (P2) - "What time does the lab close?" missed the opening-hours FAQ (40 s model answer)
- **Root cause:** "what time" was read as the question word `what`, while the FAQ is phrased with `when`. The word coverage was also only 3/4.
- **Fix:** `_faq_norm()` reads "what time / which time / at what time" as `when`. Three hour variants were added to the FAQ entry (`docs/faq/lab-and-access.md`).
- **Test:** `tools/knowledge/test_agent.py::test_what_time_is_asked_as_when`, which also asserts that "Where is the Robotics Lab?" does **not** get the hours.
- **Live-verified 23 Nov:**

| Question | Before | After |
|---|---|---|
| "What time does the robotics lab close?" | 40.7 s, model route | 1.89 s, `faq` route |
| "When is the Robotics Lab open?" | - | 0.17 s, `faq` route |
| "Where is the Robotics Lab?" | - | 0.12 s, `faq` route (still the location) |

## C-04 (P2) - Live portal build carries no version stamp
- **Finding:** `/api/health` returns `version.id = "unstamped"`. The 22 Nov deploy used plain `docker build`, not `tools/deploy/build_images.ps1`, so the running portal cannot be traced to a commit.
- **Fix:** redeploy through `tools/deploy/build_images.ps1`. The result is in `GITHUB_AND_DEPLOYMENT_STATUS.md`.

## C-05 (P3) - Two camera fixes without a regression test
V-F10 and V-F12 now have tests in `tools/security_vision/test_ultracode_2026_11_22.py`. Both were proven to fail with the fix temporarily removed, then restored with `git checkout`.

## C-06 (P1) - Knowledge assistant answered a live device-status question from old documents
- **Found by:** the 23 Nov benchmark. "Is the environment node online?" was answered "The environment node is reported as ONLINE" (10.8 s, model route, 3 citations). In fact `ENV_LAB01` has been offline since 22 Nov 16:28 (`devices.is_online = false`; ping fails).
- **Root cause:** the "live" guard covered sensor readings ("temperature right now") but not yes/no questions about a device's current state. Those went to RAG, and the documents contain old "ONLINE" text. This is static data presented as live, the same class as K7.
- **Fix:** `GUARD_STATUS` in `tools/knowledge/agent.py` covers "is/are/was/were <device> online|offline|connected|up|down|reachable|running…" and "when … last seen/heartbeat". It returns the live guard, which points to "Ask the lab" or the Devices page (database-backed). A device noun is required, so "Is the system usable offline?" and "How does the portal decide a node is offline?" still go to the documents.
- **Test:** `test_current_device_status_is_live_data_not_documents` (4 must-guard and 4 must-not-guard questions). Knowledge suite 82 passed.
- **Live-verified 23 Nov:** "Is the environment node online?" now gives the guard answer in 0.05 s; "When was the consumables bin last seen?" in 0.02 s.

## Static check
`pyflakes` was run in a throw-away venv (owner allowed installs) over `backend/app` and all of `tools/`. It found no undefined names, no wrong call signatures and no unreachable-name errors. The only finding is a harmless `"\."` escape warning in `tools/vision_train/build_r5_pseudo.py` (an offline training helper).
