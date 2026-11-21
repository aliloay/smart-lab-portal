# CLI-Hub: registry evaluation

## Installation
- **Package:** `cli-anything-hub` **0.4.1** from PyPI. License MIT; it requires only `click` and `requests`.
- **Environment:** a dedicated venv, `C:\Projects\external-tools\venvs\clihub` (Python 3.12). It is not the portal's
  `backend/.venv` and not a system Python.
- **Analytics off:** `CLI_HUB_NO_ANALYTICS=1`, set as a user environment variable and inside every `.cmd` shim.
- **On PATH:** through `C:\Projects\external-tools\bin\cli-hub.cmd`.
  - `cli-hub list --json`, `cli-hub search`, `cli-hub info` and `cli-hub previews inspect` all ran.
  - `cli-hub` is the consumer (discover, install, launch, inspect previews). The Claude plugin is the producer (generate
    and refine harnesses).

## Registry snapshot (21 Nov 2026)
- **103 entries** (`cli-hub list --json`), from the harness registry and public CLIs.
- **Categories:** 3d, ai, audio, automation, communication, data-science, database, debugging, design, devops, devtools,
  diagrams, finance, game, gamedev, generation, graphics, image, knowledge, knowledge-management, mobile, music, network,
  office, osint, productivity, project-management, science, scientific, search, storage, streaming, testing, video, web.

## Evaluation method
For each candidate:
- read the registry entry, the upstream `agent-harness/setup.py` (dependencies) and the `*_cli.py` command list;
- grep the backend for network calls (`requests.post/delete/put`, external URLs) and `subprocess` use;
- check whether the **real application** is installed on this laptop.

The full table, with requirement, installed?, use, what it can change and decision, is in
`RELEVANT_HARNESS_RECOMMENDATIONS.csv`.

## Installed (3) and why
| Harness | Smart Lab use | Verification (real backend) |
|---|---|---|
| **blender** (1.0.0) | Enclosure and lab renders, thesis figures, preview bundles | Scene built through the harness, then **real Blender 5.1** rendered it: a 320×240 PNG (62 KB, PNG magic OK). `preview capture --recipe quick` ran Blender and wrote `hero.png` + `workbench.png`, and `cli-hub previews inspect` read the bundle (`preview-bundle/v1`, status ok) |
| **ollama** (1.0.1) | Model inspection for the two assistants | `server status` ("Ollama is running") and `model list` returned the real installed models |
| **3mf** (1.0.0) | 3D-printing mesh checks: watertight, volume, holes, repair | `info` on a real mesh (FANUC LR Mate link 2, STL converted to 3MF in scratch): 2,539 vertices, 5,074 faces, bounding box |

All three were installed from the inspected local clone (`pip install ./CLI-Anything/<name>/agent-harness`), so the
code that runs is the code that was read.

## Not installed, with reasons (selection)
| Harness | Reason |
|---|---|
| **n8n** | It can activate, execute and edit live workflows; the project forbids that. `smartlab automation` reads the repo definitions instead |
| **obsidian** (+ obsidian-cli, obsidian-agent-cli) | Needs the Local REST API plugin and writes to the live vault. Changing the vault needs a separately reviewed plan |
| **mermaid** | Renders by sending the diagram to `mermaid.ink` (online), which breaks the local-only rule |
| **freecad, libreoffice, inkscape, gimp, drawio, obs-studio, krita, shotcut/kdenlive (melt), audacity (sox)** | The application is not installed. The rule is no duplicate or unrelated installs. libreoffice, inkscape and drawio are worth adding **if** the owner installs those apps |
| **videocaptioner, openscreen** | The video pipeline (ffmpeg + Piper + Whisper, `montage_v2.py`) already covers this; videocaptioner may call online LLMs |
| **chromadb, wiremock** | Not part of this stack (the knowledge index is not ChromaDB; the tests use a stdlib fake portal) |

## Usage on this laptop
```powershell
cli-hub search "3d" --json
cli-anything-blender --json scene new -n test -o C:\tmp\t.blend-cli.json
cli-anything-blender --json --project C:\tmp\t.blend-cli.json preview capture --recipe quick
cli-hub previews inspect <bundle_dir>
cli-anything-ollama --json model list
cli-anything-3mf --json info part.3mf
```
