# Final evidence index - 23 Nov 2026

| Claim | Evidence | Where | Kind |
|---|---|---|---|
| d023e98 = 40 findings; 23 verified by tests | test names and results | `D023E98_FIX_VERIFICATION.md` | tested |
| K1 and B-11 were broken; now fixed | failing-then-passing tests; regex bytes `\x08` | `ADDITIONAL_BUGS_FOUND_AND_FIXED.md` C-01, C-02 | tested |
| "What time…" 40.7 s → 0.14 s | live `/ask` timings | `AI_PERFORMANCE_BEFORE_AFTER.md`; script `tools/perf/kb_latency_bench.py` | live-verified |
| Device-status answer was wrong; now redirected | live answer "ONLINE" vs `devices.is_online=false` (SELECT), ping fails | `AI_PERFORMANCE_BEFORE_AFTER.md`, C-06 | live-verified |
| V-F9 cuts pose CPU from 3.3 to about 1.2 cores | offline runs on 17 Nov recordings, under load | `V_F9_CPU_POSE_BENCHMARK.md`; script `tools/perf/vf9_pose_bench.py` | measured offline |
| Pose cannot run fully on DirectML | onnxruntime error with CPU fallback disabled | same | measured |
| All five ESP32s offline at home | `devices` SELECT (last seen 22 Nov 16:28); ping of .150-.154 fails; Ethernet link down | `ADDITIONAL_OPEN_BUGS.csv` O-01 | measured |
| n8n 27 workflows, 26 active; error handler inactive | n8n-lab MCP `search_workflows` (read-only) | `ADDITIONAL_OPEN_BUGS.csv` O-03 | measured |
| Vault 503 notes; index 457 notes, 0 broken links | `find`, `kb.py build` output | `OBSIDIAN_FAQ_AND_KNOWLEDGE_IMPROVEMENTS.md` | measured |
| First page load about 183 kB gzip; heavy chunks lazy | `vite build` output plus built `index.html` | `PORTAL_AND_SYSTEM_OPTIMIZATION_RESULTS.md` | measured |
| No undefined names in Python code | pyflakes in a throw-away venv | `ADDITIONAL_BUGS_FOUND_AND_FIXED.md` | static check |
| Test totals | command outputs | `FINAL_TEST_RESULTS.md` | tested |
| DB backup before deploy | `backups/predeploy_closure_20261123_0214.dump`, 5,694,196 bytes, 44 TABLE DATA entries in `pg_restore --list` | `GITHUB_AND_DEPLOYMENT_STATUS.md` | verified |
| Deployment identity | `/api/health` `version.id` | `GITHUB_AND_DEPLOYMENT_STATUS.md` | live-verified |
| V3 video exports and QA | ffprobe, contact sheets, privacy review | `VIDEO_V3_COMPLETION_REPORT.md` | see report |
| Research: ranked upgrades, purchases, roadmap | 25 deliverables plus 3 prototypes | `reports/smart-lab-next-generation-upgrade-research-2026-11-23/` | research (separate session) |
| Camera fixes on live streams | **none yet** | `CAMERA_OFFLINE_VALIDATION_AND_GIU_TEST_PLAN.md` | NEEDS GIU HARDWARE |
| RFID relock fix | **none yet** | `OWNER_ACTIONS_AND_HARDWARE_BLOCKERS.md` | OWNER ACTION REQUIRED |
