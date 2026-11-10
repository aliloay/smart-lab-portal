---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/knowledge-platform/EVALUATION.md"
source_hash: "fa2e2b451ca38c7ff35004083f8075f069d79cbb57942a1b1f635d797398cf20"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/knowledge-platform/EVALUATION.md` - edit the original in the repository, not this note.

Systems: none

# Knowledge platform — tests and evaluation (2026-10-13)

## Automated tests

`py -m pytest -q tools/knowledge` → **16 passed** (fixture repo in a temp dir; no real data,
no network: the LLM URL points at a closed port).

Covered: deny list (.env never read) · secrets never reach vault or index · incremental scan
(unchanged / changed / new / renamed / removed) · removed source keeps curated notes ·
malformed workflow JSON does not stop the build · workflow note accuracy (trigger, edges,
endpoints, external host flagged, file-inactive vs live-unverified, credential names only, no
credential ids) · drift detects a new node without touching the workflow file · exact identifier
search (`192.168.1.151`) · unknown question → "Not in the indexed sources" · LLM unavailable →
clear error with evidence kept · non-local LLM URL refused · prompt-injection text stays quoted
evidence · writes outside the vault refused · broken link reported · backup → restore round
trip · corrupted index → rebuild.

## Real-repository run

* Build: 156 sources, 23 workflows, 2,032 chunks; first build 3.9 s, unchanged rebuild 1.5 s.
* Secrets: 17 files had values redacted (kinds listed in the vault's *Index status*). A scan for
  the 10 known secret values from `.env` / `camera.env` / demo credentials found **0** in vault + data.
* Found while doing this: the demo admin password is in the public README since the first
  commit and the live portal accepts it — a security issue to fix outside this project.
* Workflows: all 23 call only `http://backend:8000`; all 23 contain write calls (notify / record run).

## Retrieval (BM25), `kb.py eval --no-llm`, 10 answerable + 1 unanswerable question

**hit@5 = 9/10** (rank 1 for 7). Warm latency 7–21 ms; first query ~110 ms (index load).
Miss: "IP address of the Master ESP32" — the wording does not overlap; searching the address
itself finds it. This is the case semantic embeddings would fix.

## Answers (qwen2.5:3b, CPU only), `kb.py eval`

| Measure | Result |
|---|---|
| Generation time | 24–68 s per question (CPU; GPU left to SecurityCam) |
| Citation numbers valid | 11/11 |
| Expected key facts present | 7/10 |
| Correctly declined the unanswerable question | yes |
| Wrong statement | 1: described the re-ID fix as "rolled back to CPU" (the fix was one crop at a time on the GPU) |
| Useless answer | 1 (the retrieval miss above) |

Conclusion: search + cited evidence is reliable; the 3B model's prose is a **draft** — read the
cited passages before relying on it. Not measured: answer quality with SecurityCam running
(Docker / camera were stopped), RAM/VRAM under combined load.

