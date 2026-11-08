# Smart Lab - instructions for every AI agent (Claude Code, Gemini CLI / Antigravity, others)

**Read `CLAUDE.md` first - it is the single source of truth** for the project map, the "Never" rules, tests and
working style. This file only adds how two agents share the work. Current status: top entry of
`docs/PROGRESS_CHECKPOINT.md`.

## Roles (owner decision 2026-11-02)
| Agent | Role | Where it works | May edit |
|---|---|---|---|
| Claude Code | primary implementation engineer | `smart-lab-portal/` (main worktree) | code, tests, docs |
| Gemini (CLI / Antigravity) | independent research, architecture and code review | `smart-lab-review/` (worktree, branch `review/gemini`) | ONLY `docs/reviews/*.md` |

- Gemini never edits application code, firmware, `docker-compose.yml`, `.env*`, models or data. Findings go in
  `docs/reviews/YYYY-MM-DD-<topic>.md` (what, where with file:line, why, suggested fix, confidence). The owner or
  Claude decides what to apply; Claude implements it in the main worktree.
- Two worktrees = two folders on disk, so the agents can never write the same file at the same time. Gemini refreshes
  its view with `git merge --ff-only offline-router-door-photos` (read-only of Claude's work) before each review.
- Neither agent pushes to GitHub, merges branches or rewrites history; the owner does.

## Hard safety rules (repeated from CLAUDE.md - non-negotiable for every agent)
- Never send anything that moves a robot (UR5e / FANUC); robots are monitoring-only.
- Never open the door from anything but the Master ESP32; never touch door firmware, auth or credentials.
- Never reset, truncate or delete the live `smartlab` database, logs or backups; tests use `smartlab_test` only.
- Never run, edit, publish or unpublish live n8n workflows.
- Never commit or print secrets (`.env`, `camera.env`, `robot.env`, tokens, API keys) or photos of people.
- Never run an agent with permission prompts disabled (`--dangerously-skip-permissions`, `--approval-mode yolo`).
- Lab PCs: only what GIU IT has approved in writing.
