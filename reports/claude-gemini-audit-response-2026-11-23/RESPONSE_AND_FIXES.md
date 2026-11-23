# Response to the Gemini independent audit of 23 Nov 2026

Audit: `reports/gemini-independent-claude-closure-audit-2026-11-23/` (22 files, read-only review of `d023e98`).
Every claim was checked against the code at `f73a81c` before anything was changed. Labels: verified / tested offline /
live-verified / not applied (with the reason).

## Already fixed before this pass (closure session, commits 39964a0 and f73a81c)
- K1 (FAQ question-word regex was dead code), B-11 (locked re-read without `populate_existing`), "what time" = when.
- GAP-01 (embeddings out of sync with the index): `embeddings.npy` and `index.json` were both rebuilt at 06:01 on 23 Nov.
- GAP-04 (unstamped images): deployed 06:35 with `tools/deploy/build_images.ps1`.
- Video V3: all four cuts were finished (`reports/final-smart-lab-closure-2026-11-18/*V3*`).

## Fixed in this pass
| ID | Verdict on the claim | Change | Test |
|---|---|---|---|
| V-F1 | correct | `CrossCam.peer_live()`: the peer must have a fresh `frame_t` (2 s), not only a fresh reply. It is used by `_handoff`, `_share_live`, the labmap peer tracks and the seat deferral; `watch_zones` uses `STALE_S` instead of 5 s | `test_gemini_2026_11_23.py` (3 tests), tested offline |
| V-F3 | partly correct (the display was already "uncertain") | a look-guess is logged as a re-acquire, not `PERSON_IDENTITY_CONFIRMED`; a look-guess is not given to someone who is neither checked in nor face-named (it was wiped one pass later) | `test_look_guess_is_a_reacquire_not_a_confirmation` (fails without the fix) |
| V-F5 | correct | `Camera._run` restarts the capture loop after an exception (`capture_restarts`) | `test_capture_loop_restarts_after_an_exception` |
| V-F7 | correct | `pose.FRESH_S` 1.5 -> 2.0 s; a crowded track shows no old joints | 2 tests |
| V-F9 | correct | DirectML pose session created under `GPU_LOCK`; a pose pass is skipped when every person is crowded | camera suite |
| V-F12 | correct | `ambiguous_noted`, `_guess_said`, `hsaid` and `elim_said` are pruned to live tracks above 200 entries | camera suite |
| B-01 sub-issue | correct | students no longer get camera `named`/`activity` or PC `os_user`/`foreground_app` in `GET /api/labs/{id}`; device IPs stay visible (owner decision) | backend suite |
| B-02 | partly wrong: the heartbeat does **not** rewrite `device.lab_id` | `device_lab_scope` added to `/access/heartbeat`, `/equipment/state` and `/robots/telemetry` (only the master, ENV_LAB01 and PC_01 have their own keys, all in LAB_01) | backend suite |
| B-03 | correct | row locks on smart-bin checkout, scan, complete and the swap lookup | backend suite |
| B-08 | partly wrong: the "4 missing CSV routes" do not exist | leading spaces and line breaks are now trimmed before the formula check | `test_csv_leading_space_formula_is_neutralised` |
| B-09 | correct | event meta: bool refused, counts 0..10000, zone id within 32 bits -> 422 instead of 500 | backend suite |
| B-10 | correct | confirm / cancel refused once the booking's end time has passed | backend suite |
| ROB-2/3 | correct | robot fusion checks every fresh camera of the lab, not `.limit(1)` | backend suite |
| K2 | correct | "Which model runs in the portal?" is answered by the live model answer | backend suite |
| K5 / K10 | correct | new `services/agent_guard.py`, first in `_instant` for staff and students: control requests and secrets get a fixed answer; opening hours are answered exactly | `tests/test_gemini_2026_11_23.py` (22 cases) |
| K7 | correct | `robots-and-pcs.md` "Live." entry is now Historical; the test catches "Live." too | knowledge suite |
| K9 | correct | an Ollama `{"error"}` line in the portal stream is a failure, not "No answer was produced." | backend suite |
| PERF-1 | correct | `faq_direct`: the same FAQ rules over every FAQ entry in memory, **before** the search. Measured 2.6-4.6 ms, previously up to 1.9 s. Route eval is unchanged at 52/60 and hold-out 16/20, with 0 wrong FAQ answers | `test_faq_direct_answers_without_any_search` |
| FE-4 | correct | the stale-lab check moved into `load()` itself (the live-message reload called it unguarded) | tsc + build |
| GAP-18 | correct | `reports/**/*.mp4` in `.gitignore` | `git check-ignore` |
| Vault | mostly wrong: `01 - Project` is not in the index (0 of 13,385 chunks), there is no "+0.8 vault boost", and there are no 7 broken runbook links (1 broken link in total) | two 13 Oct notes are marked "Historical" (backups in `SmartLabKnowledge/backup_20261123`) | - |

## Not applied, with reasons
- **B-02 `_door_scope`**: CLAUDE.md forbids changing door auth. This is an owner decision.
- **B-05 same-kind swap filter**: it breaks the intended rule (`test_returning_the_other_identical_item_closes_the_open_checkout`). Any bin item may stand in, and the swap already needs a mass increase. The owner also asked for no bin changes.
- **B-10 automatic COMPLETED status**: it changes the booking history and analytics semantics. The end-time check already closes the door-token risk.
- **FE-3 single LiveProvider**: not needed. Every branch has `<LiveProvider>` as its root element, so React keeps the same provider and WebSocket across routes.
- **Relay idle timeout**: a per-direction timeout would cut off one-way transfers, and the relay runs on Hemaly's PC (GIU).
- **N8N-2 error handler inactive**: n8n runs workflows that use an Error Trigger without activating them. Live n8n edits stay with the owner.
- **B-12**: already a plain `def`.
- **AR-1/2, homography, Wi-Fi config over Serial, single Ollama model**: these are NEXT/FUTURE upgrades, not bugs.

## Tests (23 Nov, after the last change)
- Cameras: 421 passed, 2 skipped.
- Knowledge: 86 passed.
- Route eval: 52/60 and hold-out 16/20, with 0 wrong FAQ answers.
- Frontend: tsc 0 errors, unit tests and vite build OK.
- Backend: full run 923 passed, 2 failed:
  - the bin kind filter (reverted);
  - `test_esp32_boards_together` (time-dependent; passes on re-run).
- Affected backend files re-run after the revert: 67 passed.
- Final full run: see `docs/PROGRESS_CHECKPOINT.md`.

Needs GIU hardware: the camera fixes (V-F1, V-F3, V-F7) must be checked on live streams. Follow steps 5, 9 and 10 of `reports/gemini-independent-claude-closure-audit-2026-11-23/CAMERA_FIXES_AND_GIU_VALIDATION_PLAN.md`.
