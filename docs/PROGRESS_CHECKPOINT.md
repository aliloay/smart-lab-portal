# Progress checkpoint - Smart Lab master completion mission

Latest checkpoint: 2026-10-14 ~03:20 (local). Branch `offline-router-door-photos`. Nothing pushed.
Resume = read this file, `git status`, `git log --oneline -6`, then continue at "Next".

## Done (with evidence)
| Item | Evidence |
|---|---|
| UR5e collector: frozen RTDE data never shown live; NaN rejected (422, was 500); rtde_check.py | d4e5685; 22 robot tests; new tests fail on old code |
| Camera: strict DirectML detector, engines in /metrics + portal chip | d4e5685; camera tests |
| Camera re-ID fell to CPU at a busy start-up (seen live 03:00) -> re-measure before fallback, logged | uncommitted; regression test fails on old code, passes now; 102 camera tests |
| Camera password: not on the command line any more (env), masked in logs | uncommitted; test_masking.py |
| Visual foundation (intro, /welcome, manifest, photo folder) | 5b47851; browser checks on dev and **live** |
| n8n 01/03/05/07: owner versions recovered byte-exact, then option (b) repo = live (owner delegated) | docs/N8N_RECOVERY_2026-10-14.md; backups/n8n-recovery-20261014/ |
| Portal deployed (owner approved) | /api/health ok; DB dump backups/smartlab_before_deploy_20261014-0158.dump |
| Agent warm-up (2 h keep-alive) | portal: first word 9.1 s (was 14.3 s), done 12.2 s |
| Native knowledge graph (graph.py), used by investigate | 418 nodes / 2,186 edges, 2 s build; 4 graph tests; 40 knowledge tests; re-ID question now reads vision.py |
| Test DB isolation: advisory lock, concurrent runs wait instead of deadlocking | two parallel runs: second waited, both 11 passed |
| Claude Code toolkit audit | docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md (measured baseline: ~506 k tokens re-read per request) |

## Running / pending
* Full backend suite (serial, current code, one-off container) - result goes in the final report.
* Knowledge service runs as Claude's background task (127.0.0.1:5199). After Claude's session ends,
  start it again with `launch.bat` (window "Smart Lab - Knowledge").

## Waiting for the owner / hardware
* At the lab: start the camera window (loads re-ID fix + masking) -> check `re-id on directml-gpu1`.
* UR5e: IP / RTDE from the pendant -> docs/LAB_TEST_2026-10-15.md section A.
* Photos -> frontend/public/lab + labVisuals.ts.
* Approvals: commit the uncommitted work; CodeBurn `npx` run; project CLAUDE.md; Ponytail trial (optional).
