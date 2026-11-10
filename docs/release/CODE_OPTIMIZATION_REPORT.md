# Code optimization and maintenance report (release of 9 November 2026)

Scope: consolidation and maintenance only, with no new product features. The changes split into two groups: work done in this release, and earlier uncommitted improvements (3-8 Nov) that this release commits after re-testing.

## Done in this release

| Problem | Root cause | Change | Files | Tests | Effect | Regression risk |
|---|---|---|---|---|---|---|
| No single documented start command for a fresh PC; `launch.bat` also starts the face server, Ollama and camera helpers | The launcher grew with the lab PC | Added `launch.ps1` (prerequisites, `.env` validation, `docker compose up -d`, health wait, URLs) and `stop.ps1` (`docker compose stop`, keeps volumes). `launch.bat` unchanged | `launch.ps1`, `stop.ps1` | PowerShell parser: 0 errors; health URL returns 200 on the running stack | One command for the core stack | Low: new files, nothing replaced |
| A PC install kit with `enroll.key` could be committed by `git add -A` | `lab_usb_kit/` not ignored | Ignored, plus local tooling, debug captures, CAD build outputs and zips, training datasets, generated reports | `.gitignore` | `git add -A --dry-run` reviewed | Secrets and about 2 GB of derived data stay out of the public repo | None |
| 18 SolidWorks lock files tracked in git | Committed while SolidWorks had the parts open | Deleted from the index; `~$*` ignored | `tools/cad/door_enclosure/out/~$*` | - | Cleaner tree | None |
| n8n workflows undocumented in one place | Docs spread over AUTOMATION.md and the export folder | Generated reference of all 23 workflows (trigger, steps, endpoints, purpose); every endpoint checked against `automation.py` | `docs/automation/workflow-inventory.md` | Endpoint cross-check: 0 missing | Reviewable automation | None |

## Earlier improvements committed by this release (re-tested 9 Nov)

These were made during 3-8 Nov (lab day, Gemini audit rounds, door repair) and were in the working tree uncommitted. Details are in docs/PROGRESS_CHECKPOINT.md, docs/MORNING_REPORT_2026-11-04.md and docs/reviews/.

| Area | Summary |
|---|---|
| Door firmware | Relay drive level set before `pinMode` and `pinMode` removed from `setRelay`, so the lock no longer pulses open at boot (hardware-verified by the owner, 8 Nov) |
| PC accounts | Per-PC agent keys (`pc_account_keys` migration, `test_pc_keys.py`), signed agent bundle and update path |
| Detection | Lab-wide 12-class detector next to the bin model; overlap suppression keeps a small box inside a larger one |
| Network | PC agent and presence scanner prefer the Smart Lab 192.168.1.x address on dual-NIC PCs |
| Frontend | Visibility-aware polling helper (`lib/visibleInterval.ts`) so hidden tabs stop polling; deferred mount of the 3D robot twin (`RobotTwinPanel.tsx`) |

## Inspected, no change made

| Item | Finding |
|---|---|
| Frontend bundle size | Vite warns about chunks over 500 kB (3D twin, charts). Already code-split by route; further splitting would change loading behaviour, so it is left as a recommendation |
| Database indexes and slow queries | No slow-query evidence collected in this release; earlier perf reports in docs/reports (local) |
| Memory on the dev laptop | Documented in docs/SMART_LAB_RESOURCE_BUDGET.md; unchanged |

No runtime behaviour of the access sequence, door lock, robot monitoring (read-only) or n8n workflows was changed.
