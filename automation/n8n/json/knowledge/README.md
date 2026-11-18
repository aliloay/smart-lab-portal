# Knowledge workflows (repo copies)

Copied 2026-11-19 from the read-only backup `D:\SmartLabData\n8n_backup_20261118\published\` (Gemini B-17).
These three are live in the local n8n but were not tracked in the repo before.

| File | Workflow |
|---|---|
| kbSourceSync0001.json | Knowledge source sync (calls the knowledge service build on port 5199) |
| kbVaultHealth002.json | Vault health / drift report |
| kbWeeklySumm003.json | Weekly knowledge summary |

They use the n8n credential **"KB service token (local)"** (header auth). Only the credential's name and id are in
these files, never its value. Importing them into another n8n needs that credential created there first.
Repo copies only: nothing here changes, activates or runs the live workflows.
