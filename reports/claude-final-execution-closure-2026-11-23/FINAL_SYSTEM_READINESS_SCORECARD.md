# Final system readiness scorecard - 23 Nov 2026

No readiness percentages: each row says what is proven and how. Labels: LIVE-VERIFIED, TESTED OFFLINE, CODE-INSPECTED, NEEDS GIU HARDWARE, OWNER ACTION REQUIRED.

| Subsystem | State | Proof | Open item |
|---|---|---|---|
| Portal backend | **LIVE-VERIFIED**, stamped `d023e98-dirty-20261123063157` | 903 tests passed; `/api/health` ok, DB true | commit + push (owner) |
| Portal frontend | **LIVE-VERIFIED** | tsc 0, 16 unit tests, build OK, login 200, `/version.json` stamped | robot-model chunk split (NEXT) |
| Database | **LIVE-VERIFIED** healthy, backed up | dump of 5.7 MB, 44 data tables listed | - |
| Face approval (B-11 → C-01) | **LIVE** (in the deployed image) | failing-then-passing test | - |
| Knowledge assistant | **LIVE-VERIFIED** | 82 tests; FAQ 0.12-0.17 s, guard 0.00-0.05 s, RAG 9.6-11.9 s under load | p90/p95 for the model route on an idle machine |
| Portal assistant | unchanged since the 21 Nov benchmark (`qwen2.5:1.5b`) | backend tests (K2) | - |
| Security cameras (2) | services up, new code; **no picture** | 413 tests; `/health` 200 | **GIU validation** (11-step plan) |
| Pose (V-F9) | CPU, about 1.2 cores per camera | offline benchmark | live latency at GIU |
| ESP32 boards (5) | **offline since 22 Nov 16:28** | DB SELECT plus ping | **reconnect the Smart_Lab network**; F-02/F-03 decision |
| Door / RFID relock | fault open | hardware report | **1N4007 + 20-relock test** |
| Robots (UR5e, FANUC) | read-only collectors; last data 18 Nov at GIU | DB SELECT | UR5e commissioning sign-off (owner) |
| Lab PCs (14 records) | last seen 18 Nov at GIU | DB SELECT | PC-10 agent update at GIU |
| n8n | 26 of 27 workflows active | read-only MCP | activate and attach the error handler (owner) |
| Obsidian / index | 503 notes; index 0 broken links | `kb.py build` | slot 2-4 times (owner) |
| V3 video | see `VIDEO_V3_COMPLETION_REPORT.md` | - | - |
| Upgrade plan | done (separate research session) | 25 reports + 3 prototypes | owner decisions and purchases |

**Release blockers for the thesis demo:**
1. GIU camera validation.
2. ESP32 network reconnect.
3. The push.

Everything else is either done or an optional improvement.
