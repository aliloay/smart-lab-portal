---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/BACKLOG.md"
source_hash: "b93c0d8f34516613ecfd84ae6dd038e716ca8fb8ac1207ccc7788910cd40639f"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/BACKLOG.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs

# Improvement backlog (from findings, 2026-10-18)

Order (from the reliability brief):
1. safety / security;
2. data integrity;
3. critical service failures;
4. wrong health / alerts;
5. recovery and backups;
6. performance;
7. repeated operator work;
8. maintainability.

Scored 1-5 on impact (I), likelihood (L), effort (E, 5 = large) and implementation risk (R).

Status values: **open**, **done 2026-10-18**, **approval** (needs the owner / IT / an operator).

| # | Item | Class | I | L | E | R | Status / next step |
|---|---|---|---|---|---|---|---|
| 1 | Admin still on the published seed password | security | 5 | 4 | 1 | 1 | **approval**: change it in the portal; tests read it from the environment |
| 2 | Redirect HTTP -> HTTPS on the LAN (CA on lab browsers first) | security | 4 | 3 | 1 | 2 | **approval**: nginx change after the CA import |
| 3 | Resolved camera alert broke the next camera event (event lost) | data integrity | 5 | 4 | 2 | 2 | **done 2026-10-18** (fingerprint grouping + regression test) |
| 4 | STOP latch cleared by a backend restart | safety | 5 | 2 | 2 | 2 | **done 2026-10-18** (rebuilt from the audit log) |
| 5 | Stale "offline" incidents for devices that report again | wrong health | 4 | 5 | 1 | 1 | **done 2026-10-18** |
| 6 | Cross-camera names never shared (state names mismatch) | wrong function | 4 | 5 | 1 | 1 | **done 2026-10-18** (and simulated bench) |
| 7 | Tracker gave a stale track (and its name) to a runner | identity | 5 | 2 | 2 | 2 | **done 2026-10-18** (staged association, 180 simulated runs: 0 false names) |
| 8 | AI generation starved the camera analysis (above-normal runner, all cores) | performance / safety of monitoring | 4 | 4 | 1 | 1 | **done 2026-10-18** (4 threads, one answer at a time, cameras above normal priority, instant status answers) |
| 9 | Laptop RAM commit at 95 % with everything open | stability | 4 | 3 | 1 | 1 | **approval**: close unused apps; optionally cap WSL memory (`.wslconfig`) |
| 10 | Laptop clock drifts ~55 ms/h (Windows Time service stopped) | data quality | 3 | 5 | 1 | 1 | **approval**: enable time sync (Settings > Time) |
| 11 | ESP32 nodes have no clock and no offline queue: data during a Wi-Fi gap is lost | data integrity | 4 | 3 | 4 | 3 | open: firmware queue + `captured_at`, then flash on the bench (**approval**) |
| 12 | One backend process (~20 req/s): several live viewers slow the API | performance | 3 | 3 | 4 | 3 | open: serve camera frames from nginx directly, or multiple workers with shared state |
| 13 | Python CVE scan not available (pip-audit not installed) | security | 3 | 2 | 1 | 1 | **approval**: install pip-audit (dev only) |
| 14 | Camera services still run the old code until restarted | camera | 3 | 5 | 1 | 1 | open: restart at the lab start (`launch.bat`) - the new code loads |
| 15 | `/equipment` is the slowest read (p95 149 ms single user; N+1 queries) | performance | 2 | 5 | 2 | 2 | open: batch the per-device lookups |
| 16 | Drill databases accumulate (one per drill, ~30 MB) | capacity | 2 | 3 | 1 | 1 | open: the owner may drop old `smartlab_drill_*` copies (never `smartlab_restore_drill`) |
| 17 | FANUC remote interface not chosen / configured | robots | 4 | - | 4 | 4 | **approval**: interface decision with the qualified operator (ROBOT_CONTROL.md) |
| 18 | Student-PC agent pilot | PCs | 3 | - | 2 | 2 | **approval**: university IT |
| 19 | Real-world identity accuracy is unmeasured (only simulated) | camera | 4 | - | 3 | 1 | open: run LAB_GO_NOGO section 1 and score with the bench's metrics |

