# Complete project and Markdown inventory

Data files in this folder:
- `markdown_inventory.csv`: 853 Markdown files with path, bytes, date, git state and class. Titles of local-only files are withheld because the repo is public.
- `source_inventory.csv`: tracked first-party files per top-level folder and file type.

Scope: main checkout C:\Projects\smart-lab-portal, including its untracked folders. The release tree differs only by
the reports added on this branch. Excluded: .git, node_modules, venvs, dist/build, caches and camera recordings.
Evidence class: STATIC INSPECTION. Classification is by path and title: a first pass by the Haiku intake agent, which
I spot-checked.

## Markdown by class (853 files)
| Class | Files |
|---|---|
| historical test/report snapshot | 324 |
| generated agent report / agent skill docs | 299 |
| current runbook / spec | 116 |
| hardware / firmware | 36 |
| stale / contradictory | 36 |
| local-only / sensitive | 31 |
| thesis / research | 11 |

Git state: 510 tracked, 342 untracked (the owner's local reports and agent skill folders), 1 ignored.

## First-party projects (2,180 tracked files in the release tree)
- backend/: FastAPI, 826 tests
- frontend/: React 18 + Vite 6
- firmware/: 7 ESP32 sketches, the face_server Flask service and a door audio test
- tools/: security_vision, robot_monitor, ur5e_control, pc_agent, relay, knowledge, voice, opcua, ops, lan_presence, mcp_server, deploy, benchmarks, vision_train
- lab_usb_kit/
- automation/n8n: copies of the 26 workflows
- scripts/
- docker-compose.yml: db, backend, frontend, n8n, backup

## Named documents
| Document | Location |
|---|---|
| NODE_LCD_AND_UNIT_MAPPING.md | docs/hardware/ (current) |
| DEVICE_KEY_MIGRATION.md | docs/hardware/ (current) |
| SMART_LAB_CONTINUATION_REPORT_2026-11-12.md | docs/reports/local-only-final-2026-11-12/ (local-only, historical) |
| FULL_CONCURRENT_SYSTEM_TEST.md | docs/reports/local-only-2026-11-17/ (local-only, historical) |
| ARGON_*.md (12 files) + raw/ | reports/final-optimization-2026-11-17/ (agent report, historical; committed via the Argon merge) |
| CLAUDE_OPTIMIZATION_REPORT.md / (1).md | not in any worktree; supplied as chat attachments only |
| Door enclosure component dimensions.md, LAB_SESSION_FINAL_REPORT.md, CAMERA_AND_VISION_LIVE_RESULTS.md, SMART_LAB_POWERSHELL_PC_DEPLOYMENT_GUIDE.md | not found under these names in the repo or worktrees; supplied as attachments |

## Rules applied
Historical reports were NOT edited. This folder is the current source of truth for the release candidate. Older
RESUME and handoff notes are superseded wherever they disagree with it (model names, health stamp, incident API).
