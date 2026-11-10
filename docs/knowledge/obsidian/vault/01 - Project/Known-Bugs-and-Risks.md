---
type: risks
updated: "2026-10-14"
---
# Known bugs and risks

| Risk | Evidence | Status |
|---|---|---|
| Demo accounts with public passwords (admin included) still log in | `backend/seed.py` lines 50–85 (get_or_create, runs on every start), README / docs/DEMO.md / How_To_Run_System.md | **open** — [[Pending-Approvals]] #1 |
| Re-ID used wrong embeddings when the crowd size changed (cv2.dnn batch bug) | `docs/benchmarks/REID_GPU_AUDIT_2026-10-13.md` §A, old-vs-new test | fixed in code (8b48ae1); live camera still on old code |
| Live identity accuracy not proven (thresholds tuned while embeddings were wrong) | same report §D | open — lab test |
| n8n live ≠ repo for 01, 03, 05 (IF typeValidation strict) and 07 (AI step removed) | private live export, [[Workflow catalogue]] | open — decision #5 |
| n8n audit: 76 generic HTTP nodes, outdated instance notice | `data/n8n_audit.json` (private) | noted, no change |
| Load-cell zero jumped ~3.5 g once on the consumables bin (mechanical) | 2026-10-13 session, recalibration note in the bin | watch; check mounting screws |
| Raw transcripts / share page contain unredacted data | `~/.claude/projects`, `SmartLabKnowledge/inbox_raw` | private, never indexed |
