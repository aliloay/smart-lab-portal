# AI, RAG, voice and assistant latency audit

## Models (verified 18 Nov)
- Ollama 0.40.16. Installed: `qwen2.5:1.5b` (986 MB), `nomic-embed-text:latest` (274 MB). `qwen2.5:3b` is NOT installed.
- Every default now says qwen2.5:1.5b: docker-compose, .env, backend config, knowledge kb.py / config.example.json / serve.py / agent.py, scripts/ollama_models.bat. Only historical comments in .env.example mention 3b.
- GPU gate (camera first): camera state STREAMING now counts as live (Argon; test_gpu_gate).

## Bounded benchmark: Argon's "timed out" re-measured (LIVE LOCAL SOFTWARE)
Tool: tools/benchmarks/smolmaxxing_x86/bench_ollama.py, 12-case golden set (11 scored), temperature 0, context 4096.
Cameras were off; the tool refuses to run while a camera listens and stops below 700 MB free RAM. The model was
unloaded afterwards. Raw data: `ai_benchmark_results.json`.

| Config | Cold load | First token median / p95 | Full answer median / p95 | Generation | Prompt eval | Quality (mean, full) | Forbidden |
|---|---|---|---|---|---|---|---|
| GPU (GTX 1650; 1,141 MB VRAM warm) | 5.33 s | 0.191 / 0.254 s | 0.334 / 1.036 s | 76.4 tok/s | 993 tok/s | 0.682, 5/11 | 1 |
| CPU, 4 threads | 1.33 s | 0.655 / 0.901 s | 1.122 / 3.115 s | 25.0 tok/s | 284 tok/s | 0.652, 5/11 | 1 |

- **Timeout diagnosis:** not reproducible with 2.4-3.5 GB free RAM. Argon's snapshot had 0.88-1.26 GB free, so a cold model load while the laptop pages is the probable cause. Keep the 30 min keep_alive, and start the AI only with more than 2 GB free.
- **Forbidden answer** (case "measured-vs-derived", both configs): "The bin measured the capacitance." The snapshot said the node cannot. A 1.5B model can invert facts even from a correct snapshot.

## Portal assistant (LIVE LOCAL SOFTWARE, release images)
| Question | Before (live, 18 Nov) | After |
|---|---|---|
| are there any open alarms? | instant 71 ms, from records | unchanged |
| who entered the lab today? | instant 59 ms | unchanged |
| what is everyone doing right now? | instant 34 ms | unchanged |
| what is the stock of resistors? | **LLM, 25.8 s (cold model): "I do not have access to the stock"** | instant `bins_stock` (commit 89ba1be) |
| is the door open? | **LLM, 2.3 s: answered with fingerprint refusals** | instant `door_status`: the Master's door-contact report with its age; an old report is said to be too old; "contact sensor, not the lock" |
| did the bin measure the capacitance? | the model can say it did (benchmark) | instant `node_capabilities`: grams / label / estimate / not ppm (commit 279c625), students too |

After deploying backend 7e3ed3b46b8e (279c625), verified live (LIVE LOCAL SOFTWARE), all instant:
- stock: 33 ms, "30 pieces, estimated, device offline"
- door: 30 ms, "last report Tue 17 Nov 19:09 said open - too old to say what the door is now"
- capabilities: 9.5 ms
- alarms: 16 ms

Rules kept:
- Deterministic answers for access, alarms, stock, door state and node capabilities never go to the model.
- Ordinary navigation never waits on the AI.
- The tool gateway refuses every physical action (MCP e2e: unlock_door refused).

## Knowledge / RAG and voice
- **Knowledge service:** tools/knowledge 49 tests pass. The new GET /health answers without auth; everything else still needs the X-KB-Key. The service was not running at home, so /ask streaming latency through it was NOT RUN live. The n8n Knowledge workflows error while it is off (see the n8n audit).
- **Voice** (STT/TTS, :5320): 6 unit tests pass; service not running; latency NOT RUN.
- **Answer quality on the 11-question golden set:** 0.68 (GPU). Use the portal's instant answers for facts; the LLM for explanations only.

## Recommendations (not done)
- The assistant's broader factual accuracy needs a larger model or a retrieval-only mode. A model change needs the owner's approval and a camera A/B test (CLAUDE.md, 19 Oct decision).
