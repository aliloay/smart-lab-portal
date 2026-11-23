# Changed files and diff summary - 23 Nov 2026

**Base:** `d023e98` (`fix/pre-lab-hardening`). **Work:** worktree `C:\Projects\smart-lab-claude-closure`, branch `claude/final-closure-2026-11-23`. **Not committed** (the owner controls commits). Diff: 7 files, +62 / -9 lines, plus 1 new test file.

| File | What changed | Why | Function | Test | Result | Deployed |
|---|---|---|---|---|---|---|
| `backend/app/api/routes/face_submissions.py` | `populate_existing=True` on the locked re-read | C-01: double approval could enrol twice | `_waiting_or_409` | `test_locked_reread_sees_an_approval_committed_meanwhile` | failed before, passes after; 20/20 face tests | see `GITHUB_AND_DEPLOYMENT_STATUS.md` |
| `backend/tests/test_closure_2026_11_23.py` (new) | regression test for C-01 | - | - | itself | passed | n/a |
| `tools/knowledge/agent.py` | 5 backspace characters → `\b`; `_faq_norm()` reads "what time" as "when" | C-02 (K1 check was dead), C-03 (40 s answer) | `_QWORD`, `_NEG`, `_faq_norm`, `_faq_words`, `_faq_qword` | `test_what_time_is_asked_as_when` + K1 tests | 81/81 | **yes**: copied to the main checkout, service restarted 23 Nov, live-verified |
| `tools/knowledge/agent.py` (2nd change) | `GUARD_STATUS` + `_DEVICE`; live guard text mentions device status | C-06: "Is the environment node online?" answered "ONLINE" from old docs | `guard()` | `test_current_device_status_is_live_data_not_documents` | 82/82 | **yes**, live-verified 0.05 s |
| `tools/knowledge/test_agent.py` | +2 tests | C-03, C-06 | - | itself | passed | n/a |
| `tools/perf/vf9_pose_bench.py` (new) | offline pose benchmark | V-F9 was never measured | - | run 23 Nov | results in `V_F9_CPU_POSE_BENCHMARK.md` | tool only |
| `tools/perf/kb_latency_bench.py` (new) | assistant latency benchmark | repeatable AI numbers | - | run 23 Nov | results in `AI_PERFORMANCE_BEFORE_AFTER.md` | tool only |
| `docs/faq/lab-and-access.md` | +3 "Also asked" hour variants | C-03 coverage | - | live check | FAQ route 0.17-1.89 s | **yes**, index rebuilt |
| `tools/security_vision/test_ultracode_2026_11_22.py` | +2 tests (V-F10, V-F12) | the fixes had no test | - | both proven to fail with the fix removed | 413 passed / 2 skipped (main checkout, with models) | test only |
| `docs/PROGRESS_CHECKPOINT.md` | two Windows paths repaired (`\f` and `\a` had become control characters) | docs integrity | - | control-character scan | clean | docs only |

## How the main checkout relates
`C:\Projects\smart-lab-portal` (`d023e98`) holds uncommitted copies of these 4 files, put there for the live knowledge service:
- `tools/knowledge/agent.py`
- `tools/knowledge/test_agent.py`
- `docs/faq/lab-and-access.md`
- `tools/security_vision/test_ultracode_2026_11_22.py`

The backend fix goes live through an image built from the worktree. Its file is also copied to the main checkout, so the main checkout matches what runs. The owner's untracked reports and videos were not touched.
