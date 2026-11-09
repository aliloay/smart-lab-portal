# Knowledge and context

| Source | Used by | How |
|---|---|---|
| Live database (via tools and instant routes) | Ask the lab | Read-only queries per question; nothing cached in the model |
| `ai_guide.py` system guide | Both portal assistants | Short plain-language description of the lab's flows |
| Obsidian vault + repository files | Knowledge agent | Hybrid BM25 + embedding search, graph neighbours, numbered sources ([ai-context-integration.md](../knowledge/ai-context-integration.md)) |
| Device records for the target in view | Scan the lab | The record of the scanned marker's key |

The portal assistants never read the Obsidian vault directly; staff reach it through "Ask the project". Context is kept short because small local models have small context windows.
