# Obsidian: knowledge management

The project keeps its engineering knowledge in an Obsidian vault that is **generated from this repository** and extended with hand-written notes. The copy in [`docs/knowledge/obsidian/vault/`](obsidian/vault/) (322 notes) opens directly in Obsidian; the live vault is at `C:/Users/dell/SmartLabKnowledge/vault` on the engineer PC.

Verified roles (from `tools/knowledge/`):

| Role | Supported | How |
|---|---|---|
| Structured engineering knowledge base | Yes | `kb.py build` writes system notes, the n8n workflow catalogue, the database dictionary and one note per source file, all wikilinked |
| Operational documentation | Yes | Runbooks, decisions, incidents folders (hand-written notes survive rebuilds) |
| Knowledge base for an AI agent | Yes | `agent.py` / `serve.py` search the vault and repository and answer with numbered sources using a local model |
| Contextual retrieval for the portal | Yes, for staff | `POST /api/knowledge/ask` → knowledge service on 127.0.0.1:5199 |
| Live API into the Obsidian app | **No** | Obsidian itself is only a viewer; the tools read and write Markdown files directly |

Everything runs locally: the only network call is to Ollama at 127.0.0.1. The tools never write to the repository, the database, n8n, Docker or any device.

See: [vault-structure.md](vault-structure.md) · [ai-context-integration.md](ai-context-integration.md) · [knowledge-retrieval.md](knowledge-retrieval.md) · deeper design: [knowledge-platform/](../knowledge-platform/).
