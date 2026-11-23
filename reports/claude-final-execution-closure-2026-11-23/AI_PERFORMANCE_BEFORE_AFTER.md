# AI performance before / after - 23 Nov 2026

## Configuration (verified 23 Nov)
| Item | Value | Source |
|---|---|---|
| Knowledge assistant model | `qwen3:1.7b`, `think=false` | `tools/knowledge/config.json` via `kb.answer_model()` (single source since K8) |
| Portal assistant model | `qwen2.5:1.5b` | `.env` `OLLAMA_MODEL` |
| Cache key | question, forced route, index version, **model** | `serve.py` (K8) |
| Model lock | only around the model call; FAQ, guard and lookup never wait | `agent.run(llm_lock=)` (K3) |
| GPU | only while the cameras are idle (camera-first gate, `tools/knowledge/gpu_gate.py`) | `CLAUDE.md` |

## Benchmark (live service, port 5199, 23 Nov about 06:05)
- **Script:** `tools/perf/kb_latency_bench.py`.
- **Load:** the V3 re-render had just started, so the CPU was heavily busy. Model-route times are pessimistic; FAQ and guard times are not affected in any meaningful way.

| Case | Question | n | Median s | Max s | First token s | Route | Citations |
|---|---|---|---|---|---|---|---|
| Short static | Where is the Robotics Lab? | 5 | **0.12** | 1.24 (first, warm-up) | 1.24 | faq | 6 |
| Short static, "what time" | What time does the robotics lab close? | 5 | **0.14** | 0.18 | 0.14 | faq | 3 |
| Restricted | What is the admin password? | 5 | **0.00** | 0.02 | 0.00 | guard | 1 |
| Device status (before C-06) | Is the environment node online? | 1 cold + 2 cached | 10.82 cold | - | 8.11 | answer (model) | 3, **wrong answer "ONLINE"** |
| Device status (after C-06, live re-check) | Is the environment node online? | 1 | **0.05** | - | - | guard | 1 |
| Normal RAG | How does the consumables bin estimate the item count? | 1 | 9.64 | - | 5.73 | answer | 3 |
| Long generative | Explain how the two security cameras share a person's identity... | 1 | 11.91 | - | 7.51 | answer | 3 |
| Unknown / live sensor | What is the coolant temperature of the FANUC controller right now? | 1 | **0.00** | - | - | guard | 1 |

Model questions were run once each, because the service caches completed answers (the repeat runs above show `cached: true`). The p90/p95 for model routes need a dedicated run on an idle machine with the cache cleared. Not done, to keep the cameras' CPU share.

## Before → after (same live service)
| Question | Before | After | Change |
|---|---|---|---|
| "What time does the robotics lab close?" | 40.67 s, model (22 Nov, correct answer) | 0.14 s median, FAQ | C-03 |
| "When is the Robotics Lab open?" | 18.6 s, model, **wrong "7:00 AM"** (22 Nov) | 0.17 s, FAQ, correct | K10 |
| "Is the environment node online?" | 10.8 s, model, **wrong "ONLINE"** (node offline since 22 Nov 16:28) | 0.05 s, guard: points to "Ask the lab" / Devices for live status | C-06 |
| "Why doesn't the door open?" | - | 72 s, investigate route | heavy question, model; expected |

## Fixes behind these numbers
- **C-02:** the question-word / negation regex really works now (it was dead code).
- **C-03:** "what time" is read as "when".
- **C-06:** current device state ("is X online", "when was X last seen") is live data. The knowledge assistant no longer answers it from documents; the portal's database-backed assistant does.

**Accuracy before speed:** every change makes the assistant refuse or redirect rather than guess. None makes the model answer more.
