# Final test evidence index (19 Nov 2026)

| Claim | Evidence (file / command / commit) |
|---|---|
| Backend suite on the merged code | `tools\ops\test_backend_fast.ps1` → 841 passed / 1 failed (contract test) → fixed in `ecbb167`; output saved in the session scratchpad as `backend_merged.txt`, summarised in FINAL_TEST_RESULTS.md |
| Opt branch merged | commit `fc18c99` (merge of `opt/claude-app-performance-2026-11-17` @ `0362c8d`) |
| Gemini fixes already in the lab branch | `3e4ca30` merges `7b9b91d`; `git diff HEAD opt/gemini-final-giu-capacity-2026-11-18 -- tools` shows only whitespace + HEAD-newer code |
| AI speed fix | commit `7619717`; AI_PERFORMANCE_BEFORE_AFTER.md |
| AI guard (unsafe / secret / impossible questions) | commit `b2f89e8`; AI_QUALITY_VALIDATION.md; `tools/knowledge/test_agent.py` (14 new tests) |
| Knowledge index rebuilt | `kb.py build` → 445 notes, 13,153 chunks, 0 broken links; embeddings 3,495 + 132 new; backup of the old index in `D:\SmartLabData\kb_backup_2026-11-19\` |
| Build stamp | `curl -k https://127.0.0.1/api/health` → `version.id = ecbb167-20261118231702`; `/version.json` same |
| Deployed images + rollback | `tools\deploy\build_images.ps1 -Tag pre-merge-20261119` output: backend `034e51c2a97b`, frontend `f24859878193`; rollback tags `pre-merge-20261119` |
| Pre-deploy DB backup | `D:\SmartLabData\db_dumps\predeploy_2026-11-19.dump` (pg_dump -Fc, 4.8 MB; DB 106 MB) |
| PC-11 rename | `UPDATE devices SET name='PC-11' WHERE device_uid='PC_GIULAB20-PC14'` → 1 row (id 24); live `/api/equipment` shows PC-11 |
| Old test cards hidden, not deleted | `backend/app/api/routes/equipment.py:230-232` (`Device.name.notlike("TEST -%")`); DB rows ids 14, 15, 16 kept |
| Login capacity | FINAL_TEST_RESULTS.md (25 concurrent logins, 50 parallel dashboards) |
| Camera / robot / PC / relay / voice / OPC UA suites | FINAL_TEST_RESULTS.md table (commands listed) |
| Showcase video sources and edits | VIDEO_SOURCE_INVENTORY.md, VIDEO_EDITING_AND_CLIP_SELECTION_LOG.md, `D:\SmartLabData\showcase_2026-11-19\build\timeline.json` |
| Narration (new lines) | `D:\SmartLabData\showcase_2026-11-19\narr\*.wav` + `narration.json` |
| Gemini inspection prompt (next step) | GEMINI_ARGON_FULL_INSPECTION_PROMPT.md |
