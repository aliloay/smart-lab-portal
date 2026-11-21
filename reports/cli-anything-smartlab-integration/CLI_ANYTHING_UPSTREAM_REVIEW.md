# CLI-Anything (HKUDS): upstream review

- **Source:** https://github.com/HKUDS/CLI-Anything, cloned to `C:\Projects\external-tools\CLI-Anything`.
  - Shallow clone, depth 50; HEAD `34f5195` (2026-09-22, merge of PR #481).
  - Kept outside the Smart Lab repo. License: MIT.

## What was read
| Area | Files |
|---|---|
| Plugin | `cli-anything-plugin/README.md`, `HARNESS.md` (747 lines, read in full: phases 1–7, principles, directory structure, preview norms), `QUICKSTART.md`, `PUBLISHING.md` |
| Plugin commands | `commands/cli-anything.md`, `refine.md`, `test.md`, `validate.md`, `list.md` |
| Code | `repl_skin.py` (copied into our package as required), `skill_generator.py` |
| Hub | `cli-hub/README.md` and `setup.py` (package `cli-anything-hub` 0.4.1), `registry.json`, `public_registry.json`, `matrix_registry.json` |
| Harnesses inspected | `blender`, `ollama`, `3MF`, `mermaid`, `n8n`, `obsidian` (source and setup.py) |

## The method in one paragraph
For each GUI application, find the real backend engine and map GUI actions to its API or CLI. Then:
- design Click command groups that work both one-shot and as a REPL (REPL by default);
- implement probe/info commands first, then mutations, with a backend module that calls the real software
  (`blender --background`, `libreoffice --headless`, and so on);
- keep session state in locked JSON with undo/redo;
- give every command `--json`;
- write `TEST.md` (plan) before the tests, then unit tests, true-backend E2E and subprocess tests of the **installed**
  command (`_resolve_cli`, `CLI_ANYTHING_FORCE_INSTALLED=1`, no `cwd`), then append the results;
- generate a self-contained `SKILL.md`;
- package as a PEP 420 namespace sub-package `cli_anything.<software>`.

## Strengths
- A clear, testable SOP. The "use the real software" rule and the installed-command tests prevent toy harnesses.
- A uniform JSON and REPL surface across tools, which agents learn once.
- A preview protocol (`preview-bundle/v1`) with a separate producer and consumer. It was verified with Blender (see the
  installation report).

## Issues found (during real use on Windows)
| Harness | Issue | Effect |
|---|---|---|
| **blender** | `render execute` only **writes** a bpy script and reports a `command`; it does not run Blender. The upstream "real backend" claim holds only for `preview capture`, which does run Blender | You must run the generated script yourself (done in our E2E check) or use `preview capture` |
| **blender** | It writes the script in the Windows ANSI code page, so `UnicodeEncodeError` on Windows | Workaround: `PYTHONUTF8=1`, set in our `.cmd` shim |
| **3MF** | `setup.py` misses `networkx` and `lxml` (needed by trimesh for 3MF) | `ModuleNotFoundError` at runtime; installed manually |
| **mermaid** | Renders by sending the diagram to `https://mermaid.ink` | Breaks the Smart Lab local-only rule; not installed |
| **n8n** | Uses the n8n REST API with an API key: can activate, run and edit workflows | Breaks a project rule; not installed |
| **validate** | The checklist requires `project.py`, `session.py` (undo), `export.py` and `--project` | It assumes a document-editing GUI app; see the deviations in `SMARTLAB_CLI_ARCHITECTURE.md` |
