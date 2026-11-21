# smartlab CLI: installation guide (Windows lab laptop)

## Current install (done 21 Nov 2026)
| Item | Location |
|---|---|
| Tool venv (Python 3.12) | `C:\Projects\external-tools\venvs\clihub` (also holds cli-hub and the blender, ollama and 3mf harnesses) |
| Package | `cli-anything-smartlab 0.1.0`, installed non-editable in that venv's `site-packages` |
| Commands on PATH | `C:\Projects\external-tools\bin\smartlab.cmd`, `cli-anything-smartlab.cmd`, `cli-hub.cmd`, `cli-anything-blender.cmd`, `cli-anything-ollama.cmd`, `cli-anything-3mf.cmd`. The `bin` folder was added to the **user** PATH. Open a new terminal to pick it up |
| User config (no secrets) | `C:\Users\dell\.smartlab\config.json` → `repo`, `serial_log` |
| Agent skill | `C:\Projects\smart-lab-portal\.claude\skills\cli-anything-smartlab\SKILL.md` (local, git-ignored) + the canonical copy in the repo |
| Upstream clone | `C:\Projects\external-tools\CLI-Anything` |

The shims set `CLI_HUB_NO_ANALYTICS=1` and `PYTHONUTF8=1`; the Blender shim also adds Blender 5.1 to PATH.

## First use
```powershell
smartlab --version
smartlab doctor
smartlab auth login          # once per 8 h, for devices / esp32 / robots / pcs / system health (staff or admin)
smartlab status
```
- The sign-in is a normal portal login and appears in the audit log.
- A dedicated read-only staff account would be cleaner; creating one is an owner decision.

## Update after changing the code
```powershell
C:\Projects\external-tools\venvs\clihub\Scripts\python -m pip install C:\Projects\smart-lab-portal\tools\smartlab_cli\agent-harness
```
- Until the branch `feat/smartlab-cli` is merged, the source is at `C:\Projects\smart-lab-cli\tools\smartlab_cli\agent-harness`.

## Uninstall
```powershell
C:\Projects\external-tools\venvs\clihub\Scripts\python -m pip uninstall cli-anything-smartlab
Remove-Item C:\Projects\external-tools\bin\smartlab.cmd, C:\Projects\external-tools\bin\cli-anything-smartlab.cmd
Remove-Item -Recurse $HOME\.smartlab                # config + token
# optional: remove C:\Projects\external-tools\bin from the user PATH (System > Environment Variables)
```
- Plugin removal: `/plugin uninstall cli-anything` (or `claude plugin uninstall cli-anything@cli-anything`).

## Configuration reference (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `SMARTLAB_REPO` | auto (parent folder with `docker-compose.yml` + `backend/app`) / config `repo` | repo for firmware, n8n copies, reports, git, keys |
| `SMARTLAB_API` | `http://localhost:8000/api` | portal API base |
| `SMARTLAB_TOKEN` | none | use a token instead of `auth login` |
| `SMARTLAB_USERNAME` / `SMARTLAB_PASSWORD` | none | non-interactive login (avoid in shared shells) |
| `SMARTLAB_SERIAL_LOG` | config `serial_log` | master serial log for `logs` |
| `SMARTLAB_TIMEOUT` | 8 | seconds per request |
| `SMARTLAB_STALE_AFTER_S` | 300 | when an online device counts as STALE |
| `SMARTLAB_KB_URL` / `SMARTLAB_OLLAMA_URL` | 127.0.0.1:5199 / :11434 | local services |
| `SMARTLAB_HOME` | `~/.smartlab` | config + token folder |

## Windows notes
- The VS Code terminal puts `backend\.venv` first on PATH. The shims call the clihub venv exe directly, so this does not
  matter for `smartlab`.
- The REPL uses prompt_toolkit in a real console and plain `input()` when piped.
