---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/N8N_RECOVERY_2026-10-14.md"
source_hash: "682804ac2facf5b0a4cb0f272f39187adf59eb461466b02d6af806213bad9702"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/N8N_RECOVERY_2026-10-14.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs

# n8n workflows 01 / 03 / 05 / 07 - recovery and repo-vs-live decision (2026-10-14)

## What happened
On 2026-10-14 ~01:00 the repo files were overwritten with the live n8n definitions while they showed as
locally modified. Live n8n itself was never edited, imported, activated or deactivated.

## Recovery (done, verified)
The knowledge registry (`SmartLabKnowledge/data/registry.json`, observed 2026-10-13 22:41) holds the sha256
and size of all four files as they were before the overwrite. Each one matches the committed HEAD version
**byte for byte with CRLF line endings** - the "modified" status was line endings only; there were no
uncommitted logic edits. The working tree now holds exactly those bytes again (sha256 verified) and
`git status` shows the four files clean.
Copies kept (git-ignored): `backups/n8n-recovery-20261014/<name>.owner-recovered.json` and
`<name>.live-sync.json`.

## Repo vs live - differences (live n8n observed by export 2026-10-14)
Cosmetic, n8n fills these in itself (no behaviour change): sticky-note ids, `options: {}`,
`responseMode`/`method`/`contentType` defaults, schedule `field: days`.

Real differences needing YOUR decision:
| Workflow | Repo | Live | Effect |
|---|---|---|---|
| 01 "Lab Needs Heads-up?" | IF typeValidation **loose** | **strict** | strict fails a run when a value has the wrong type instead of coercing it |
| 03 "Is It A Burst?" | loose | strict | same |
| 05 "Anything Needs Attention?" | loose | strict | same |
| 07 weekly report | has node **"AI Summary (optional)"** feeding the admin message | node removed; message built from the report directly | live sends no AI summary |

Options: (a) keep repo as is (live differs - drift reported daily by Knowledge 2), (b) copy live into repo
(the `.live-sync.json` files), (c) change live to match repo (needs a separate approved n8n edit).
Nothing is changed until you choose.

## Decision (owner delegated, 2026-10-14 ~02:10): option (b)
The repo now holds the live definitions (`.live-sync.json` copies), so repo = what actually runs; live n8n
unchanged. The previous repo versions remain in git history and in `backups/n8n-recovery-20261014/*.owner-recovered.json`.
Effect to know: 01/03/05 use strict type checks; 07 sends no AI summary.

