# n8n workflows

| Path | What |
|---|---|
| `json/*.json` | the 12 workflows, importable into n8n: **start here** |
| `src/*.ts` | the same workflows as n8n Workflow SDK code (reviewable source) |
| `gen.py` | generates `src/*.ts` |
| `build_json.mjs` | compiles `src/*.ts` → `json/*.json` (`npm i --no-save @n8n/workflow-sdk@0.33.1` first) |
| `workflows.json` | ids of the copies in the n8n Cloud project |
| `export_workflows.py` | downloads the live versions from an n8n instance |

No credentials, keys or ids are in these files: nodes reference the two
credentials **by name** (`Smart Lab automation key`, `Smart Lab webhook
token`). Setup, security boundary and verification results:
[docs/AUTOMATION.md](../../docs/AUTOMATION.md).
