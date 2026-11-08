---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/knowledge-platform/RESEARCH.md"
source_hash: "58e07f1a5d1d3e36480aed9ed2ada8499c691a9120484cbd25bc5cd1ce4ee075"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/knowledge-platform/RESEARCH.md` - edit the original in the repository, not this note.

Systems: none

# Research and architecture decision — 2026-10-13

## Sources read (2026-10-13)

| Source | Finding used |
|---|---|
| https://obsidian.md/help/data-storage | Notes are plain Markdown files in a local vault folder; vault settings in `.obsidian/`; Obsidian refreshes automatically when files change outside the app; avoid nested vaults. |
| https://github.com/coddingtonbear/obsidian-local-rest-api | Community plugin (MIT): HTTPS on 27124 with a self-generated CA, bearer API key, optional HTTP on 27123, built-in MCP server at `/mcp/`. The page does not state a version or the default bind address. |
| https://docs.ollama.com/capabilities/embeddings | `POST /api/embed`, L2-normalised vectors; suggested models embeddinggemma, qwen3-embedding, all-minilm (sizes not on the page). |
| https://docs.n8n.io/hosting/securing/security-audit/ | `n8n audit` (CLI), `POST /audit` (owner), or the n8n node: credentials, database, file-system, risky nodes, instance settings. |

## Environment found

i7-9750H, 15.8 GB RAM (~4 GB free while working), GTX 1650 4 GB (used by SecurityCam:
~0.5 GB for YOLO26s + re-ID), 115 GB free disk. Python 3.14. Ollama 0.40.3 with `qwen2.5:3b`
and `qwen2.5:1.5b`, **no embedding model**. Obsidian **not installed**. n8n image
`n8nio/n8n:latest` (version not readable: Docker Desktop was stopped), editor bound to
`127.0.0.1:5678`, workflows mounted read-only from `automation/n8n/json`. The repository is
under OneDrive.

## Options and decision

| Question | Options | Decision | Why |
|---|---|---|---|
| Obsidian ⇄ tools | A file bridge · B Local REST API plugin · C new service | **A** | Obsidian reads plain files and refreshes on external change; no third-party plugin code, no API key, no open port. B adds a TLS service + key management for no gain at this stage; C is not needed. |
| Vault location | in repo · OneDrive · `C:\Users\dell\SmartLabKnowledge` | **outside both** | The repo is public and itself under OneDrive; the vault must stay private and unsynced. |
| Retrieval | vector DB (Qdrant etc.) · Postgres pgvector · local BM25 | **BM25 now, embeddings later (approval)** | No embedding model is installed; BM25 is exact on identifiers (IPs, file names, env vars) and measured 9/10 hit@5. Semantic misses (wording changes) are the known gap. No new service, no change to the live database. |
| LLM | Ollama GPU · Ollama CPU · other runtime | **Ollama, CPU (`num_gpu: 0`)** | Already installed. The GPU belongs to SecurityCam; CPU keeps the camera untouched. Cost: 24–68 s per answer (measured). |
| n8n integration | n8n calls the tool · tool reads n8n | **tool reads the workflow files now; n8n API later** | The files are the definitions n8n imports; n8n was not running. New workflows need n8n + approval (RUNBOOK). |

## Rejected / deferred, and why

* Obsidian Local REST API and other community plugins — not needed for a file vault; would be
  third-party code with vault access (approval required if wanted later).
* A vector database service — adds a container and a backup target; reconsider after an
  embedding model is approved and measured against the BM25 baseline.
* LLM on the GPU — must first be measured together with SecurityCam (risk: VRAM, frame drops).

## Open questions

* Installed n8n version and live activation state of the 23 workflows (needs n8n running).
* Whether Obsidian (once installed) or any plugin makes network calls beyond update checks — not verified.
* Embedding model choice and size (needs approval to download, then the evaluation below).

