# Progress checkpoint - Smart Lab master completion mission

Latest checkpoint: 2026-10-14 ~16:30 (local, at the lab). Branch `offline-router-door-photos`. Nothing pushed.
Resume = read this file, `git status`, `git log --oneline -6`, then continue at "Next".

## Done (with evidence)
| Item | Evidence |
|---|---|
| UR5e collector: frozen RTDE data never shown live; NaN rejected (422, was 500); rtde_check.py | d4e5685; 22 robot tests; new tests fail on old code |
| Camera: strict DirectML detector, engines in /metrics + portal chip | d4e5685; camera tests |
| Camera re-ID fell to CPU at a busy start-up (seen live 03:00) -> re-measure before fallback, logged | d1aaa17; regression test fails on old code, passes now; 103 camera tests |
| Camera password: not on the command line any more (env), masked in logs | d1aaa17; test_masking.py; **live-checked 07:40: no process shows the camera address** |
| Visual foundation (intro, /welcome, manifest, photo folder) | 5b47851; browser checks on dev and **live** |
| n8n 01/03/05/07: owner versions recovered byte-exact, then option (b) repo = live (owner delegated) | docs/N8N_RECOVERY_2026-10-14.md; backups/n8n-recovery-20261014/ |
| Portal deployed (owner approved) | /api/health ok; DB dump backups/smartlab_before_deploy_20261014-0158.dump |
| Agent warm-up (2 h keep-alive) | portal: first word 9.1 s (was 14.3 s), done 12.2 s |
| Native knowledge graph (graph.py), used by investigate | 418 nodes / 2,186 edges, 2 s build; 4 graph tests; 40 knowledge tests; re-ID question now reads vision.py |
| Test DB isolation: advisory lock, concurrent runs wait instead of deadlocking | two parallel runs: second waited, both 11 passed |
| Claude Code toolkit audit | docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md (measured baseline: ~506 k tokens re-read per request) |

## 07:33 laptop reboot - recovered
`launch.bat` restarted everything: portal health ok, n8n 26 workflows / 0 drift, knowledge service up, Ollama
models on CPU (0 VRAM). Camera service started with the new code: **detector directml-gpu1 (24 ms), re-ID
directml-gpu1 (12 ms/crop)** - the busy-start-up fix verified live (the camera itself is at the lab: camera false).

## Running / pending
* Full backend suite: 436 passed (434 + the 2 AI-local tests after pinning OLLAMA_CPU_ONLY in conftest).
* Knowledge service runs in its own window "Smart Lab - Knowledge" (current code, restarted 07:13).

## At the lab 2026-10-14 (all recorded in docs/LAB_TEST_2026-10-15.md)
* UR5e LIVE_VERIFIED (192.168.1.102, RTDE 48 Hz, J1-J6 mapping, stale 2.0 s on cable pull, auto-recovery).
* Camera LIVE: GPU detector + re-ID; driver-crash root cause fixed (shared GPU session + GPU lock);
  analysis 7 passes/s (pass p50 85 ms, p95 106 ms); zoom finds people seated behind others.
* Identity: door naming via TEST entries (`tools/door_test_entry.py --watch-face`, window
  "Smart Lab - Door test entries"); home desk USER5 -> PC-09/PC-10; face outranks look; hand-back while
  touching. Decisions persisted in tools/security_vision/recordings/identity_log.jsonl (git-ignored).
* Scripts: stop_all.bat / restart_all.bat.

## Waiting for the owner / hardware
* At the lab: start the camera window (loads re-ID fix + masking) -> check `re-id on directml-gpu1`.
* UR5e: **LIVE_VERIFIED** - telemetry 48 Hz, J1-J6 mapping/direction, stale in 2.0 s on cable pull, auto-recovery (docs/LAB_TEST_2026-10-15.md). Next: camera.
* Photos -> frontend/public/lab + labVisuals.ts.
* Optional (owner): CodeBurn `npx` run, Ponytail lite trial; TikTok effect needs a screen recording. All work committed (c4390ae), nothing pushed.
