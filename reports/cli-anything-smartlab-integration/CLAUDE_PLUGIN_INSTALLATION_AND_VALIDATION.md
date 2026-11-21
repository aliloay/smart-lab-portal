# Claude Code plugin: installation and validation

## Installation (21 Nov 2026)
The `/plugin marketplace add` and `/plugin install` steps were done with the Claude Code binary's own plugin CLI, which
is the scripted equivalent:
```text
claude plugin marketplace add HKUDS/CLI-Anything
  -> ✔ Successfully added marketplace: cli-anything (declared in user settings)
claude plugin install cli-anything@cli-anything
  -> ✔ Successfully installed plugin: cli-anything@cli-anything (scope: user)
claude plugin list
  -> cli-anything@cli-anything  Version 34f519533bc1  Scope user  Status ✔ enabled
```
- **Binary:** `claude.exe` from the VS Code extension 2.1.329 (`...\anthropic.claude-code-2.1.329-win32-x64\resources\native-binary\`).
- **`claude plugin details cli-anything@cli-anything`:**
  - 5 skills: `cli-anything`, `list`, `refine`, `test`, `validate`; no agents, hooks or MCP servers.
  - About 98 tokens added to every session; about 0.8–2.8 k tokens when a skill runs.
- `HARNESS.md` ships inside the plugin cache, and the command files reference it as `./HARNESS.md`.

## Are the commands available?
- **In this session: no.** The plugin was installed while this session was running, and Claude Code loads plugin skills
  at session start.
- **To make them available:** restart Claude Code (close and reopen the VS Code panel, or start a new session). Then
  `/cli-anything`, `/cli-anything:refine`, `/cli-anything:test`, `/cli-anything:validate` and `/cli-anything:list` appear.
- **Because the command was not loaded:** validation and test were done manually, following the local
  `commands/validate.md` and `commands/test.md` (see below and `SMARTLAB_CLI_TEST_RESULTS.md`).
- **Owner action:** after the restart, run `/cli-anything:validate C:\Projects\smart-lab-portal\tools\smartlab_cli` and
  `/cli-anything:test ...` once to confirm with the official command.

## Windows shell compatibility (verified)
| Requirement | Found |
|---|---|
| Git for Windows / bash | `/usr/bin/bash`, git `/ucrt64/bin/git` |
| `cygpath` | `/usr/bin/cygpath` |
| Python | `py -3.12` (3.12) and `py -3.14`. Note: the VS Code terminal puts `backend/.venv` first on PATH as `python`, so the tools use explicit interpreters |
| pip, pytest, Click | in the dedicated venv `C:\Projects\external-tools\venvs\clihub` (Python 3.12) |
| Path translation | the bash tool runs Windows exes with `C:/...` paths; the `.cmd` shims make the tools callable from PowerShell, cmd and bash |

No new Python distribution and no WSL were installed.

## Manual validation against `commands/validate.md`
| Check group | Result | Notes |
|---|---|---|
| 1. Directory structure | PASS 5/5 | `agent-harness/cli_anything/smartlab/` exists; `cli_anything/` has no `__init__.py` (verified: the namespace package has no `__file__`); `smartlab/` has `__init__.py`; `core/`, `utils/`, `tests/` exist; `setup.py` uses `find_namespace_packages` |
| 2. Required files | PARTIAL 6/9 | Present: README.md, smartlab_cli.py, tests/TEST.md, test_core.py, test_full_e2e.py, SMARTLAB.md. **Absent by design:** core/project.py, core/session.py, core/export.py (see the deviations) |
| 3. CLI implementation | PASS 6/7 | Click; groups; `--json`; `handle_error`; REPL as the default; global state object. `--project` is replaced by `SMARTLAB_REPO` / `~/.smartlab/config.json` |
| 4. Core modules | DEVIATION | No project/session/export: the CLI does not edit documents. Modules have docstrings and type hints |
| 5. Test standards | PASS 9/9 | TEST.md part 1 + part 2; unit tests on synthetic data; E2E on real backends; `TestCLISubprocess` uses `_resolve_cli("cli-anything-smartlab")` with `CLI_ANYTHING_FORCE_INSTALLED`; no `cwd`; 107/107 pass |
| 6. Documentation | PASS 4/4 | README (install, usage, commands, examples), SMARTLAB.md (architecture, command map, rendering-gap assessment), no duplicated HARNESS.md, every command documented (generated reference) |
| 7. PyPI packaging | PASS 7/7 | `find_namespace_packages(include=["cli_anything.*"])`; name `cli-anything-smartlab`; entry point `cli-anything-smartlab=cli_anything.smartlab.smartlab_cli:main` (+ `smartlab`); imports under `cli_anything.smartlab.*`; install_requires; `python_requires>=3.10`. Not published |
| 8. Code quality | PASS 5/5 | No syntax or import errors (installed + tested); no hard-coded machine paths in the code (all via env/config); no bare `except:` |

**Overall:** all applicable checks pass. The three missing files and `--project` are a documented deviation: the Smart
Lab is a distributed API and hardware system, not a document-editing GUI app. We did not fake compliance with empty
`project.py`, `session.py` or `export.py` files.
