# Smart Lab local agent (`tools/knowledge/agent.py`) — 2026-10-14

## Use it

```powershell
cd C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal
py tools\knowledge\agent.py "Where is the Master ESP32 IP documented?"        # lookup: evidence only, no AI
py tools\knowledge\agent.py "Why will the Smart Lab not use a PLC?"           # answer: streamed, cited
py tools\knowledge\agent.py "Investigate why the count could go above stock_max"   # multi-step, read-only
py tools\knowledge\agent.py "..." --run-tests knowledge                        # investigation + allowlisted offline tests
py tools\knowledge\agent.py --bench                                            # latency + quality benchmark
```

Ctrl+C cancels. Every answer prints the route and why, the retrieval time, the evidence list with labels,
the status (completed / failed / cancelled) and the time to the first word. Open a cited `path:lines`
in VS Code or the vault's *14 - Sources* mirror.

## Routes (fixed rules, not chosen by the model)

| Route | When | What runs |
|---|---|---|
| lookup | "where / which file / find / list", or an IP, file name or commit in the question | search only (≈30–200 ms), no LLM |
| answer | everything else | 4 compact passages (the best ~480 chars of each hit) → local LLM, streamed |
| investigate | "investigate / debug / diagnose / trace / root cause / why does …" | search → grep code for the exact identifiers → read the most relevant lines → git history of those files → related tests → optional allowlisted test run → cited findings |

Tools are fixed functions: `read` (repo allowlist, deny list, ≤120 lines, ≤4,000 chars), `grep` (safe
pattern, ≤30 hits), `git_log` (≤10 entries), `run_tests` (only `knowledge` or `camera` offline suites).
There is no shell, no write, no network tool. Limits: 6 evidence steps, 4 files, 180 s.

## Evidence labels

VERIFIED_CURRENT (repo file/test, read now) · DOCUMENTED (repo doc) · TESTED (a recorded result — not live) ·
HISTORICAL (git) · REPORTED (owner said, in an approved conversation) · PROPOSAL (assistant suggestion,
unverified). Nothing the agent reads is LIVE_VERIFIED: it never queries the running systems.

## Where the time went (measured 2026-10-13/14, CPU, qwen2.5:3b, old `kb.py ask`)

| Step | Time |
|---|---|
| model load (unloaded after 5 min idle) | 6.5 s |
| reading the prompt: 1,274 tokens at 49 tok/s | **25.9 s** |
| writing 170 tokens at 11 tok/s | 15.4 s |

Fixes, in order of effect: compact evidence (the relevant window, 4 hits → ~700–800 tokens), keep the model
loaded 15 min, cap the answer, stream it, skip the LLM for lookups, and the smaller installed model.

## Benchmark (11 questions, `agent.py --bench`, CPU, camera GPU untouched: 495 MB before and after)

| | Before (kb.py ask, 3B) | Agent, 3B | **Agent, 1.5B (default)** |
|---|---|---|---|
| first word | — (no streaming; full answer after 24–68 s) | 12.3 s median | **6.8 s median** |
| full answer | 24–68 s | 16.8 s median (max 22.9) | **10.0 s median (max 12.6)** |
| lookup route | — | 33 ms | 34 ms |
| correct answers (read by hand) | 7/10 + 1 wrong | 5/10, 3 refused answerable | **9/10**, 1 muddled ("runs on CPU and GPU") |
| keyword fact check | 7/10 | 5/10 | 8/10 |

Repeat with `py tools\knowledge\agent.py --bench [--model qwen2.5:3b]`. Note: repeating the same questions
right away reuses Ollama's prompt cache (first word ~0.2 s) — the numbers above are fresh prompts.

## Not done / needs approval

* GPU inference for the LLM: not tested (camera priority). Needs an opt-in benchmark with the camera running.
* `nomic-embed-text` (downloaded before approval): unused. Use or remove — owner decision.
* The investigation planner is a fixed sequence; an LLM-chosen tool loop was not built (a 3B/1.5B model
  follows tool instructions only partly — see the lumped citations in the stock_max example).
* Live-state questions (is the camera running, is a workflow active) are not answered from live systems.
