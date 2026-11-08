---
type: "source-mirror"
source_kind: "documentation"
source_path: "automation/n8n/README.md"
source_hash: "b5652ee67d0447e2ec4a63424be14be57d7929ddea343e80beda915522e6c581"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `automation/n8n/README.md` - edit the original in the repository, not this note.

Systems: [[n8n automation]]

## Related
- [[docs_AUTOMATION.md]] - mentioned by docs

# n8n workflows

| Path | What |
|---|---|
| `json/*.json` | the 23 workflows (01-12 lab operations, 13-22 Robotics Lab, 23 emergency), importable into n8n: **start here** |
| `src/*.ts` | the same workflows as n8n Workflow SDK code (reviewable source) |
| `gen.py` | generates `src/*.ts` |
| `build_json.mjs` | compiles `src/*.ts` → `json/*.json` (`npm i --no-save @n8n/workflow-sdk@0.33.1` first) |
| `workflows.json` | ids of the copies in the n8n Cloud project |
| `export_workflows.py` | downloads the live versions from an n8n instance |

No credentials, keys or ids are in these files: nodes reference the two
credentials **by name** (`Smart Lab automation key`, `Smart Lab webhook
token`). Setup, security boundary and verification results:
[[docs_AUTOMATION.md|docs/AUTOMATION.md]].

