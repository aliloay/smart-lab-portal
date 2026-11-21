# CLI-Anything × Smart Research Lab: final integration summary (21 Nov 2026)

## Answers
| # | Question | Result | Evidence |
|---|---|---|---|
| 1 | Is the official CLI-Anything plugin installed? | **INSTALLED AND VERIFIED** | `claude plugin list` → `cli-anything@cli-anything`, user scope, enabled; marketplace `cli-anything` added |
| 2 | Are its Claude commands available? | **OWNER ACTION REQUIRED** | They load at session start. Restart Claude Code, then `/cli-anything`, `:refine`, `:test`, `:validate`, `:list`. Validation was done manually from the local `validate.md` |
| 3 | Is Windows shell compatibility working? | **INSTALLED AND VERIFIED** | Git bash, `cygpath`, py 3.12/3.14, pip, pytest, Click; `.cmd` shims on the user PATH; no new Python or WSL |
| 4 | Is CLI-Hub installed and working? | **INSTALLED AND VERIFIED** | `cli-anything-hub` 0.4.1 in its own venv, analytics off; `list` (103 entries), `search`, `info`, `previews inspect` ran |
| 5 | Which harnesses are useful for the Smart Lab? | **Evaluated** | blender, ollama and 3mf now; libreoffice, inkscape and drawio if those apps are installed. 19 rows in `RELEVANT_HARNESS_RECOMMENDATIONS.csv` |
| 6 | Which were installed, and why? | **INSTALLED AND VERIFIED** | **blender** (real Blender 5.1 render + preview bundle), **ollama** (live model list), **3mf** (real mesh info). Not installed: n8n (runs/edits live workflows), obsidian (writes the vault, needs a plugin), mermaid (online renderer), apps that are not installed |
| 7 | Was a dedicated Smart Lab CLI built? | **IMPLEMENTED AND VERIFIED** | `cli-anything-smartlab` 0.1.0: 16 groups, about 50 commands, REPL. Source in `tools/smartlab_cli/` on branch `feat/smartlab-cli` (worktree `C:\Projects\smart-lab-cli`) |
| 8 | Does it use the real Smart Lab APIs? | **IMPLEMENTED AND VERIFIED** | Portal FastAPI (`/api/health`, `/api/devices`, …), knowledge service, Ollama, camera services, repo files, git, docker ps. No parallel database |
| 9 | Is the JSON output safe? | **TESTED: PASSED** | One envelope on every command (source, timestamp, freshness, labels); redaction tested with fake secrets |
| 10 | Does it work as an installed command? | **TESTED: PASSED** | `where smartlab` → `C:\Projects\external-tools\bin\smartlab.cmd`; runs from `C:\`; tests forced the installed command |
| 11 | Are the unit tests passing? | **TESTED: PASSED** | 49 unit + 36 safety |
| 12 | Are the subprocess and integration tests passing? | **TESTED: PASSED** | 14 against a fake portal (real HTTP) + 8 live read-only against the real services. Total **107/107** |
| 13 | Are prohibited operations blocked? | **TESTED: PASSED** | No action commands exist; 19 side-effect endpoints and the Ollama/knowledge/camera mutations are refused before any socket; no shell |
| 14 | Was a reusable SKILL.md generated? | **IMPLEMENTED AND VERIFIED** | Canonical + packaged + active in `.claude/skills` (it appeared in this session's skill list) |
| 15 | Can the local AI assistant benefit? | **PARTIALLY IMPLEMENTED (proposal)** | Two real live-status gaps were found (lab count, bin status). The design is in `AI_ASSISTANT_INTEGRATION_PROPOSAL.md`; not built yet (needs owner approval); no before/after benchmark yet |
| 16 | What remains? | see below | |

## What remains
1. **Owner:**
   - Restart Claude Code. Run `/cli-anything:validate` and `/cli-anything:test` on `tools/smartlab_cli` once.
   - Run `smartlab auth login`, then `smartlab devices list` / `esp32 list` to see real device data in the CLI.
   - Ideally, create a dedicated read-only staff account for agents.
2. **Owner decision:** commit and merge `feat/smartlab-cli`. Nothing is committed: `git -C C:\Projects\smart-lab-cli status`
   shows the new files. Afterwards, reinstall from the main repo path.
3. **Owner decision:** approve the AI-assistant live-intent proposal. Then implement it and benchmark it against the 86.5 %
   baseline.
4. **Optional:** install LibreOffice / Inkscape / draw.io if wanted, then add their harnesses.
5. **Upstream issues worth reporting (not done; no external posting):**
   - blender `render execute` does not run Blender;
   - blender writes its script in a non-UTF-8 encoding on Windows;
   - 3MF misses the networkx/lxml dependencies.

## Integrity check
- **Main checkout** `C:\Projects\smart-lab-portal`:
  - **Unchanged by the CLI work**, except for the local, git-ignored `.claude/skills/cli-anything-smartlab/`.
  - Its earlier commits that day (the AI model) are separate and documented.
- **Untouched:** no `.env`, credentials, recordings or database files were copied into the tooling.
- **No physical actuation**, no n8n execution, no database write, no GitHub push.
- **Restarts:** none for the CLI work. The backend container and the knowledge service were restarted earlier for the AI
  model deployment the owner asked for.
- **Outside the repo:** `C:\Projects\external-tools\` (upstream clone, venv, bin shims), `~/.smartlab/config.json`, the
  user PATH entry and `CLI_HUB_NO_ANALYTICS=1`.
