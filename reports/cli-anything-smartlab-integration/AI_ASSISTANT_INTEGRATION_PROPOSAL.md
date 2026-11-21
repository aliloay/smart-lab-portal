# Proposal: using the smartlab CLI layer for faster, live AI answers

**Status: proposal only. Nothing in the live assistants was changed for this.** The model change on 21 Nov was a
separate, benchmarked deployment (`docs/benchmarks/LOCAL_MODEL_BENCHMARK_2026-11-21.md`).

## What already exists (so we don't build it twice)
- **Portal assistant** (`backend/app/services/agent.py` + `ai.py`, documented in `docs/AGENT_SPEED_REPORT_2026-10-27.md`).
  It already runs the flow the owner described:
  - **instant answers** straight from the database, with no model: offline devices, robots/PCs/cameras status, system
    health, stock, bookings, who is where, "where is the X lab";
  - then a **tool router** with 9 typed, read-only tools (`tool_gateway.py`);
  - then the local model.
  - 34 of 52 benchmark questions are answered instantly (median 0.03 s).
- **Knowledge assistant** (`tools/knowledge/agent.py`): routes lookup / answer / investigate over the vault and the repo,
  with citations.

## The gap measured today
Live spot check (21 Nov), portal assistant:
- **"How many labs are there?"** Both models answered "1"; the database has 11. The snapshot the model sees is scoped to
  one lab.
- **"Is the consumables bin online?"** qwen3 said "offline", qwen2.5 said "no data". It was online (BIN_NODE_1, seen
  seconds earlier).

These are routing and data gaps (the question reached the model with a thin snapshot), not model-size gaps.

## Proposal
```text
question ─► classifier (existing)
              ├─ static fact (where is lab, what is X)  ─► vault / FAQ (existing, lookup route)
              ├─ LIVE status (is/are ... online, last seen, which ESP32, what model)
              │        ─► NEW: deterministic answer from the same functions smartlab uses
              │           (device liveness = portal device_out/state; model = ollama /api/ps + config)
              └─ complex / why / how ─► RAG + local model (existing)
```
1. **Portal assistant (backend, Docker):** add instant intents for the live questions that failed or are common. They
   read the same data the CLI shows, directly in the backend, which already has it:
   - `device_online(<name>)`;
   - `lab_count` / `list_labs`;
   - `which_esp32(<role>)`;
   - `assistant_model`.
   - The backend must **not** shell out to the CLI. No subprocess and no new endpoint; it calls the existing service
     functions.
2. **Knowledge assistant (host Python):** for live-status questions, it may import `cli_anything.smartlab.core` functions
   **as a library**, through the same read-only allow-list. It gets no shell access, no extra endpoint and no new rights.
   It uses the knowledge service's existing keys and, for device data, an owner-provided read-only sign-in.
3. **Answer format:** one line, plus the source and age, e.g. "BIN_NODE_1 is ONLINE (last report 8 s ago, portal
   /api/devices)".

## Safety rules for the integration
- An allow-listed function set only; user text is never turned into a command line; there is no generic "run smartlab"
  tool.
- The assistants gain no write ability. The CLI layer has none to give.
- No change to the live Obsidian vault or index without a separately reviewed plan.

## Benchmark plan (before / after)
- **Questions:** the existing 52-question portal set, plus 12 new live-status questions (WH set: where / which / is / are
  / when / what model). Expected answers come from `smartlab --json` at the same moment.
- **Measure:** accuracy, median and p95 time, and the share answered instantly.
- **Accept only if:** accuracy ≥ 86.5 % (today's baseline) and no new p95 regression.
- **Not run yet:** the after-numbers need the implementation, which waits for owner approval of this proposal.
