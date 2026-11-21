# cli-anything-smartlab

`smartlab` is a read-only, agent-native command line for the **Smart Research Lab**. It shows devices and ESP32 boards,
security cameras, robots, lab PCs, local AI, the knowledge vault, n8n workflow definitions, firmware versions, logs,
reports and git state. Every command takes `--json`.

It was built with the CLI-Anything methodology (HKUDS) and adapted to a distributed web + hardware system. See
`../../SMARTLAB.md` for the architecture and the deviations from the GUI-app template.

## Install
- Requirements: Python ≥ 3.10 and Click. prompt-toolkit is only used by the REPL.
```powershell
# on the lab laptop (dedicated tool venv, not the portal's)
C:\Projects\external-tools\venvs\clihub\Scripts\python -m pip install C:\Projects\smart-lab-portal\tools\smartlab_cli\agent-harness
# PATH shims: C:\Projects\external-tools\bin\smartlab.cmd and cli-anything-smartlab.cmd (bin is on the user PATH)
```
- **Uninstall:** `...\clihub\Scripts\python -m pip uninstall cli-anything-smartlab`.
- **Update:** re-run the install line after pulling.

## Configure (no secrets in config)
| Setting | Env var | `~/.smartlab/config.json` | Default |
|---|---|---|---|
| Repo path | `SMARTLAB_REPO` | `repo` | the first parent of the current folder that contains `docker-compose.yml` + `backend/app` |
| Portal API | `SMARTLAB_API` | `api` | `http://localhost:8000/api` |
| Master serial log | `SMARTLAB_SERIAL_LOG` | `serial_log` | none |
| Request timeout (s) | `SMARTLAB_TIMEOUT` | `timeout` | 8 |
| Stale after (s) | `SMARTLAB_STALE_AFTER_S` | `stale_after_s` | 300 |

**Keys:**
- The knowledge service key and the camera device key are read from where the Smart Lab keeps them
  (`tools/knowledge/config.json`, `.env`) and are never printed.
- `smartlab auth login` signs in to the portal (it asks for the password; `SMARTLAB_PASSWORD` is also accepted) and
  keeps the 8-hour token in `~/.smartlab/token.json`.
- Each sign-in is recorded in the portal's audit log.

## Use
```text
smartlab                      # REPL
smartlab status               # overview
smartlab --json doctor        # every check: PASS / WARN / FAIL / SKIP
smartlab --json devices offline
smartlab --json esp32 firmware
smartlab --json cameras status
smartlab --json ai status
smartlab --json knowledge search relock guard PN532
smartlab --json automation inspect "Daily lab report"
smartlab --json logs recent master_serial_20261120.log -n 30 --errors
smartlab --json github status
```
The full command reference is in `skills/SKILL.md` (agent skill) and
`reports/cli-anything-smartlab-integration/SMARTLAB_CLI_COMMAND_REFERENCE.md`.

## Tests
```powershell
cd tools\smartlab_cli\agent-harness
$env:PATH = "C:\Projects\external-tools\venvs\clihub\Scripts;$env:PATH"
$env:CLI_ANYTHING_FORCE_INSTALLED = "1"                   # test the installed command, not a fallback
python -m pytest -q cli_anything/smartlab/tests            # unit + safety + E2E against a fake portal
$env:SMARTLAB_LIVE = "1"; python -m pytest -q cli_anything/smartlab/tests/test_full_e2e.py   # + live read-only
```

## Safety
- The command tree has no group that can act on the lab.
- `utils/api_client.py` refuses every request outside its allow-list before opening a socket:
  - portal: GET only on listed paths, plus the sign-in POST;
  - knowledge: status/search, with search forced to `route=lookup`;
  - Ollama: version/tags/ps;
  - local health URLs.
- No shell, `eval` or `exec`. Output is redacted for keys, tokens, passwords, RTSP credentials and door QR tokens.
- `tests/test_safety.py` enforces all of this.
