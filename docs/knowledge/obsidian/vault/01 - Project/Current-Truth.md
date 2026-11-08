---
type: current-truth
as_of: "2026-10-13 ~23:30 (+03:00)"
updated: "2026-10-14"
---
# Current truth (as of 2026-10-13 evening)

> Every line was checked directly at the time shown. It is **not** live: re-check before relying on it.

| Area | State | How verified |
|---|---|---|
| Repository | branch `offline-router-door-photos`, HEAD `4087c29`, 214 commits, not on the remote | `git` |
| Docker | backend, db, frontend, n8n, backup running | `docker compose ps` |
| n8n (local) | v2.40.7, **23/23 workflows active**; 4 differ from repo files (01, 03, 05 IF strict; 07 AI step removed) | n8n CLI read-only export — [[Workflow catalogue]] |
| n8n.cloud | trial expired, 12 old copies paused — **not connected** to the Smart Lab | owner screenshot |
| SecurityCam | GPU code committed (YOLO26s + re-ID on GTX 1650); the **running** camera process still uses the old code until restarted | process start time vs commit |
| Recorded-frame benchmark | analysis pass median 65–70 ms (p95 ~101–104), detector 35 ms, re-ID 12 ms/person, 495 MB GPU | `tools/benchmarks/audit_engines.py stages`, 2026-10-13 |
| Live identity accuracy | **unproven** — supervised test planned | [[LAB_TEST_2026-10-14.md]] |
| Demo accounts | 4 seeded accounts with public passwords; still valid | `backend/seed.py`, README — [[Known-Bugs-and-Risks]] |
| Local AI | Ollama 0.40.3; qwen2.5:3b (CPU) in use; nomic-embed-text downloaded, **not used** (approval pending) | `ollama list` |
| Obsidian | installed; its default vault is in OneDrive; this vault not yet opened by the owner | `%APPDATA%\obsidian\obsidian.json` |


## 2026-10-14 night - state (sources: commits d4e5685..0a73c6a, docs/PROGRESS_CHECKPOINT.md)
- Portal LIVE with tonight's backend + frontend (deployed ~02:05, health ok). New: /welcome, post-login intro, camera GPU chips, robot sample age.
- UR5e: collector marks frozen RTDE data stale; NaN telemetry refused (422). **Live robot: UNVERIFIED** (IP/RTDE unknown).
- Camera: detector verified on GTX 1650 (24 ms, strict DirectML). Re-ID fell to CPU at a busy start-up -> fixed in code, loads at next camera start. **Live latency / identity accuracy: UNVERIFIED.**
- Knowledge: hybrid search (nomic-embed-text), native graph (422 files, 2,214 edges), agent first word ~7-9 s.
- Tests: backend 436/436, camera 103, robot 22, knowledge 40, tsc + build clean.
