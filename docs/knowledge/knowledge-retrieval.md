# Knowledge retrieval

Commands (standard library only, run from the repository root):

```powershell
py tools/knowledge/kb.py build                      # regenerate notes, catalogue and index
py tools/knowledge/kb.py search "door relay"        # search only, no model
py tools/knowledge/agent.py "How does the door decide fail-secure?"   # routed answer with sources
py tools/knowledge/graph.py related backend/app/api/routes/security.py  # tests, commits and notes linked to a file
py tools/knowledge/kb.py health                     # broken links, stale or orphan notes
py tools/knowledge/serve.py                         # local service on 127.0.0.1:5199 for the portal and n8n
```

Search is hybrid: **BM25** over chunked notes and files (exact words and identifiers), blended with embedding cosine similarity when an embedding model is available (`kb.py search`). The agent then adds graph neighbours (tests and commits of the matched files) before asking the model.

Configuration: copy `tools/knowledge/config.example.json` to `config.json` and set `vault`, `data`, `ollama`, `model` (default `qwen2.5:3b`) and the service key. Tests: 49 passed (`py -m pytest -q tools/knowledge`, 9 Nov 2026).
