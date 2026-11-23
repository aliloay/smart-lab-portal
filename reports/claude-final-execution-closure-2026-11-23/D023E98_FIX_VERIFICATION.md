# d023e98 fix verification - 23 Nov 2026

**What was checked:** every one of the 40 findings in `d023e98` (`fix/pre-lab-hardening`, local, 1 commit ahead of `origin/fix/pre-lab-hardening`, not pushed). Checked on 23 Nov 01:25-02:30.

**How:**
1. The code change is present in the commit.
2. The named regression test exists in the commit and passes.
3. For fixes that had no test: a new test was written and run. Where possible, it was also run with the fix removed, to prove it catches the bug.

Work location: worktree `C:\Projects\smart-lab-claude-closure`, branch `claude/final-closure-2026-11-23`, base `d023e98`.

## Summary
| Result | Count |
|---|---|
| Verified by an existing regression test | 23 |
| Live-verified (K10 opening hours) | 1 |
| Had no test, test added on 23 Nov and proven to fail without the fix | 2 (V-F10, V-F12) |
| **Claimed fixed but actually broken - repaired on 23 Nov** | **2** (K1 question-word check, B-11 double approval). See `ADDITIONAL_BUGS_FOUND_AND_FIXED.md`, C-01 and C-02 |
| Code present, covered only by the full suite or code inspection (no dedicated test) | 9 (V-F4, V-F11, K6, B-04, B-06, FE-2, FE-3, FE-4, FE-5) |
| Measured separately | 1 (V-F9, see `V_F9_CPU_POSE_BENCHMARK.md`) |
| Measured, no change needed | 1 (B-12) |
| Owner decision, unchanged | 1 (B-01) |

The two broken claims are the main result of this check. Both K1 and B-11 had passing tests, but the tests passed for the wrong reason:
- **K1:** the question-word regex contained real backspace characters (0x08) instead of `\b`. It never matched any question, so the check was dead code. The K1 tests still passed through the word-coverage rule.
- **B-11:** the "locked" re-read of a face submission returned the stale in-memory copy. Two simultaneous approvals could both pass the PENDING check.

## Matrix
| ID | Fix present | Evidence | Status |
|---|---|---|---|
| V-F1 | `withdraw_stale_tracks()` | `test_stale_stream_withdraws_published_people` | TESTED - PASSED (offline) |
| V-F2 | seq analysed once, STALE_S cut-off | `test_analyse_never_runs_twice_on_the_same_frame` | TESTED - PASSED (offline) |
| V-F3 | look-only -> "Name ? (look)" | `test_look_only_return_is_a_guess_not_a_confirmed_name` | TESTED - PASSED (offline) |
| V-F4 | `post_state` iterates a snapshot | full camera suite | CODE-INSPECTED |
| V-F5 | `supervised()` + `/health` `thread_restarts` | `test_supervisor_restarts_a_crashing_loop`; live `/health` shows `thread_restarts: {}` | TESTED - PASSED; field live-verified |
| V-F6 | per-pass `copy.copy` snapshot | `test_published_tracks_are_a_copy_of_the_pass` | TESTED - PASSED |
| V-F7 | unmatched track loses joints | `test_pose_unmatched_track_loses_its_old_joints` | TESTED - PASSED |
| V-F8 | best-overlap-first pose match | `test_pose_matching_is_best_overlap_first`, `test_pose_crowded_track_gets_no_pose` | TESTED - PASSED |
| V-F9 | `SMARTLAB_POSE_THREADS` (2), GPU lock only for DirectML | `V_F9_CPU_POSE_BENCHMARK.md` | see benchmark |
| V-F10 | name handed back once per pass | **new** `test_one_name_is_never_handed_back_to_two_new_people_in_one_pass` (fails with the fix removed) | FIXED AND VERIFIED (offline) |
| V-F11 | keyed full-rate render only | code inspection | CODE-INSPECTED |
| V-F12 | `mismatch_reported`, `_unlike`, `_note_seen` pruned | **new** `test_veto_counters_of_gone_tracks_are_dropped` (fails with the fix removed) | FIXED AND VERIFIED (offline) |
| V-F13 | OUT_OF_FRAME joints | `test_pose_joint_outside_the_frame_is_out_of_frame_not_observed` | TESTED - PASSED |
| K1 | question word / negation / coverage | **was broken (0x08 in regex) - repaired as C-02**; new `test_what_time_is_asked_as_when` | FIXED AND VERIFIED, live-verified 23 Nov |
| K2 | robot model ≠ AI model | `test_robot_model_question_is_not_answered_with_the_ai_model`, `test_ai_model_question_still_answered` | TESTED - PASSED |
| K3 | lock only around the model | `test_model_lock_only_around_the_model`; live: FAQ answers in 0.12-0.17 s while the model is busy elsewhere | TESTED - PASSED |
| K4 | `done: failed` on exception | frontend `kbstream.test.ts` | TESTED - PASSED (client side) |
| K5 | guard always runs | `test_forced_route_still_runs_the_guard` | TESTED - PASSED |
| K6 | cached answer replays `sources` | code inspection (`serve.py` lines 159-193) | CODE-INSPECTED |
| K7 | FAQ "Historical", FAQ/guard not cached | `test_faq_live_answers_hold_no_frozen_numbers` | TESTED - PASSED |
| K8 | `kb.answer_model()`, model in cache keys | `test_answer_model_single_source` | TESTED - PASSED |
| K9 | Ollama `{error}` -> failed | `test_ollama_error_inside_stream_is_a_failure` | TESTED - PASSED |
| K10 | opening-hours FAQ | live: 0.17 s FAQ answer; "what time ... close" fixed 23 Nov (40 s -> 1.9 s) | LIVE-VERIFIED |
| B-01 | - | owner decision 22 Nov | OWNER DECISION |
| B-02 | `device_lab_scope` | `test_own_key_cannot_raise_smoke_in_another_lab`, `test_shared_key_unchanged` | TESTED - PASSED |
| B-03 | checkout row lock, bin items 409 | `test_student_cannot_check_out_a_smart_bin_item_by_hand`, `test_plain_asset_checkout_still_works` | TESTED - PASSED |
| B-04 | emergency row lock; expiry bump `populate_existing` | code inspection: `act`/`back_to_normal` take the lock as the first load of the row, so no stale copy | CODE-INSPECTED |
| B-05 | swap needs mass increase | `test_rescanning_an_item_already_in_the_bin_does_not_close_someone_elses_loan` | TESTED - PASSED |
| B-06 | notification insert under a savepoint | code inspection | CODE-INSPECTED |
| B-07 | `manager.update_rights()` | `test_role_change_updates_open_socket_rights` | TESTED - PASSED |
| B-08 | `core/csvsafe.py` | `test_csv_cells_cannot_run_as_formulas` | TESTED - PASSED |
| B-09 | meta validation -> 422 | `test_malformed_camera_event_meta_is_422_not_500` (2 cases) | TESTED - PASSED |
| B-10 | COMPLETED booking locked | `test_completed_booking_cannot_be_reconfirmed_or_cancelled` | TESTED - PASSED |
| B-11 | approval row lock | **was ineffective (stale identity-map copy) - repaired as C-01**; new `test_locked_reread_sees_an_approval_committed_meanwhile` (fails before, passes after) | FIXED AND VERIFIED |
| B-12 | - | 0.37 ms index scan measured 22 Nov | NOT REQUIRED |
| FE-1 | `lib/kbstream.ts` | `kbstream.test.ts` (6 tests) | TESTED - PASSED |
| FE-2 | `wsTicket` via `send()` | tsc + build | CODE-INSPECTED |
| FE-3 | `/report` in `LiveProvider` | tsc + build | CODE-INSPECTED |
| FE-4 | stale lab reply ignored | tsc + build | CODE-INSPECTED |
| FE-5 | `useDebounced` 400 ms | tsc + build | CODE-INSPECTED |

All camera items are **tested offline only**. The camera streams are not reachable from this network (both services report `no_picture`). Live validation needs the GIU run in `CAMERA_OFFLINE_VALIDATION_AND_GIU_TEST_PLAN.md`.
