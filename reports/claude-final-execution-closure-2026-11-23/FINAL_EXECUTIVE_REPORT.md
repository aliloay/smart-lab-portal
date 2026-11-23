# Final executive report - Smart Lab closure, 23 Nov 2026

## In short
- **Verified** all 40 findings of `d023e98`. **Two "fixed" claims were broken** and are now repaired:
  - **K1:** the FAQ question-word check was dead code; backspace characters had been written into its regex.
  - **B-11:** double face approval was still possible; the locked re-read used a stale in-memory copy.
- **Found and fixed four more bugs**, each with a regression test:
  - **C-03:** "what time" questions went to the slow model. 40.7 s → 0.14 s.
  - **C-06:** "Is the environment node online?" was answered **"ONLINE" from old documents**, but the node is offline.
  - **C-04:** the live build was unstamped.
  - **C-05:** two camera fixes had no tests.
- **Tests on the final code:**

  | Suite | Result |
  |---|---|
  | Backend | 903 passed, 3 skipped, 0 failed |
  | Cameras | 413 passed, 2 skipped |
  | Knowledge | 82 passed |
  | Robot monitor | 43 passed, 1 skipped |
  | PC agent | 40 passed |
  | Relay | 6 passed |
  | Face server | 21 passed, 1 skipped |
  | Frontend | tsc 0 errors, 16 unit tests, build OK |

- **Deployed and live-verified:**
  - Portal stamped `d023e98-dirty-20261123063157`, with rollback tag `pre-closure-20261123` and a pre-deploy DB dump.
  - Knowledge service restarted on the new code; fixes checked with live questions.
- **Benchmarks:**
  - AI: FAQ 0.12-0.14 s median, guard ≤ 0.05 s, RAG 9.6-11.9 s under load.
  - V-F9 pose: about 1.2 cores per camera instead of 3.3 (offline, under load).
- **V3 video:** 4 exports done. Two narration fact errors were found and corrected. QA passed (format, loudness, no gaps, privacy).
- **Upgrade research** (separate session): 25 reports and 3 prototypes, with a ranked plan split into free software, moderate development and purchases. See `reports/smart-lab-next-generation-upgrade-research-2026-11-23/`.
- **Not committed, not pushed:** owner decision.

## What is genuinely finished
The portal (backend, frontend, DB) with tests and deployment; the assistant fixes, live; the 22 Nov camera fixes with offline tests; the V3 video; the research plan; the 17 closure reports in this folder.

## What still needs the owner (details in `OWNER_ACTIONS_AND_HARDWARE_BLOCKERS.md`)
1. **Reconnect the Smart_Lab network at home.** All five ESP32 boards have been offline since 22 Nov 16:28; the Ethernet link is down.
2. **GIU camera validation** (11 steps, about 30 min): the only way to prove V-F1..V-F13 live.
3. **1N4007 diode + 20-relock test:** the RFID relock fault stays open until then.
4. **Commit and push.**
5. Approve or decline `ahmed`; UR5e commissioning sign-off; F-02/F-03 subnet decision; F-21 face re-enrolment; PC-10 agent update; room 224; slot 2-4 times; activate the n8n error handler.

## Strongest next steps
- **Software:**
  - the research plan's #1, a WH fast router as step 0 in both assistants;
  - a held-out AI evaluation set;
  - a frontend query cache.
- **Hardware:** only the diode now. A GPU desktop for cameras + AI is the one purchase worth considering later (research report S15).

## Note on the research report
Its S10 ("camera per-pass snapshot, V-F6") is already done in `d023e98` (`test_published_tracks_are_a_copy_of_the_pass`). Treat that item as finished.

## Files in this folder
- `FINAL_EXECUTIVE_REPORT.md`
- `FINAL_SYSTEM_READINESS_SCORECARD.md`
- `D023E98_FIX_VERIFICATION.md`
- `ADDITIONAL_BUGS_FOUND_AND_FIXED.md`
- `ADDITIONAL_OPEN_BUGS.csv`
- `CHANGED_FILES_AND_DIFF_SUMMARY.md`
- `FINAL_TEST_RESULTS.md`
- `AI_PERFORMANCE_BEFORE_AFTER.md`
- `CAMERA_OFFLINE_VALIDATION_AND_GIU_TEST_PLAN.md`
- `V_F9_CPU_POSE_BENCHMARK.md`
- `OBSIDIAN_FAQ_AND_KNOWLEDGE_IMPROVEMENTS.md`
- `PORTAL_AND_SYSTEM_OPTIMIZATION_RESULTS.md`
- `GITHUB_AND_DEPLOYMENT_STATUS.md`
- `VIDEO_V3_COMPLETION_REPORT.md`
- `OWNER_ACTIONS_AND_HARDWARE_BLOCKERS.md`
- `FINAL_RELEASE_AND_ROLLBACK_RUNBOOK.md`
- `FINAL_EVIDENCE_INDEX.md`
