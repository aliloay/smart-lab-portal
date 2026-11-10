# Obsidian knowledge base

This folder is a copy of the project's Obsidian vault (`C:/Users/dell/SmartLabKnowledge/vault`, copied 9 Nov 2026, 322 notes). Open `vault/` as a vault in Obsidian to browse it with its graph.

## How it is built and used (verified in tools/knowledge)

| Step | Tool | What happens |
|---|---|---|
| Build | `py tools/knowledge/kb.py build` | Regenerates the notes from the repository: system notes (02 - Systems), the n8n workflow catalogue (05), the database dictionary (06), one note per source file (14 - Sources) and the Home page. Writes only to the vault's generated folders and a private data folder; never deletes |
| Index and search | `tools/knowledge/kb.py`, `graph.py` | Builds a local search index over the notes and the wikilink graph (`py tools/knowledge/graph.py related <path>`) |
| Ask | `py tools/knowledge/agent.py "<question>"`, served on port 5199 by `serve.py` | Retrieves the relevant notes and source files, then a local model (Ollama, qwen2.5) writes an answer **with numbered sources**. Example (8 Nov 2026): "What is the current operational status of the lab?" answered in 34 s from three cited files |
| History | `py tools/knowledge/history.py` | Imports shared chat exports into "13 - Automation Inbox/History review" after redaction and owner approval |

Everything runs locally; nothing is sent to a cloud service. Limitations: the vault reflects the repository at the last build (Home shows the build time); live database contents are not read, only model definitions; generated notes are overwritten on the next build, so personal notes belong in Decisions / Runbooks / Incidents.

## Not included in this copy

- `13 - Automation Inbox/History review/`: nine full chat transcripts (ChatGPT and Claude Code sessions). Held back until the owner decides whether to publish them.
- `.obsidian/plugins/`: third-party plugin code (Cosmograph graph view; install it from Obsidian's community plugins). `.obsidian/*.json` settings are included.
