# Local model benchmark, 21 Nov 2026 (32 GB RAM, i7-9750H, GTX 1650)

**Question:** with the RAM upgrade, is a better or bigger local model worth it?

## Method
- **Benchmark:** the knowledge assistant's own lab question set (`tools/knowledge/eval_questions.json`, 13 questions), run
  through `agent.bench`.
  - Scored on correct facts in the answer (`facts_ok`) and the speed to the first word and to the full answer.
- **Device:** CPU (6 threads) or GPU, forced for each run. The cameras were idle (the IP cameras are at GIU), so the GPU
  runs are a best case.
- **qwen3 models:** run with `think=false` (no hidden reasoning pass), the same as the portal backend.
- **Harness:** `scratchpad/model_bench.py` (outside the repo, read-only wrapper around `agent.bench`).

## Results (knowledge assistant)
| Model | Device | Facts correct | First word (median) | Full answer (median) | Slowest |
|---|---|---|---|---|---|
| qwen2.5:1.5b (previous) | CPU | 7/11 | 6.1 s | 9.1 s | 16.1 s |
| qwen2.5:1.5b (previous) | GPU | 8/11 | 0.1 s | 4.8 s | 9.2 s |
| **qwen3:1.7b (chosen)** | CPU | **9/11** | 7.0 s | 12.7 s | 17.2 s |
| **qwen3:1.7b (chosen)** | GPU | **9/11** | 0.1 s | 5.4 s | 7.8 s |
| llama3.2:3b | CPU | 8/11 | 12.8 s | 23.7 s | 46.9 s |
| llama3.2:3b | GPU | 7/11 | 0.2 s | 12.8 s | 22.0 s |
| qwen3:4b | CPU | 8/11 | 21.4 s | 46.0 s | 58.6 s |
| qwen3:4b | GPU | 8/11 | 0.2 s | 26.1 s | 28.6 s |
| qwen2.5:7b | CPU | 9/11 | 31.5 s | 42.6 s | 65.2 s |

**Reading the table:**
- **Bigger models did not answer better.**
  - qwen2.5:7b matched qwen3:1.7b (9/11) but took 3–4× longer on the CPU.
  - The 3B/4B models scored lower.
- **The RAM upgrade makes a 7B model possible on the CPU, but not useful:** about 43 s per answer for no gain in accuracy.
- **Retrieval found the right source in 9 of 12 answerable questions for every model.** The remaining errors come from the
  evidence passages, not the model size.

## Portal assistant: unchanged (qwen2.5:1.5b)
- **27 Oct, portal benchmark** (52 questions through the portal's route, `docs/AGENT_SPEED_REPORT_2026-10-27.md`):
  qwen2.5:1.5b scored 86.5 % against 80.8 % for qwen3:1.7b.
- **Spot check today** (5 live portal questions): neither model was clearly better.
  - Both answered "how many labs" wrongly: the snapshot they are given lists 1 lab.
  - qwen3:1.7b called the online consumables bin "offline".
  - qwen2.5:1.5b said "no data".
  - Follow-up: the portal snapshot/instant answers for lab count and bin status (data issue, not model).

## Decision (deployed 21 Nov)
| Assistant | Model | Where set |
|---|---|---|
| Knowledge assistant (vault, n8n knowledge jobs, `agent.py`) | **qwen3:1.7b**, `think=false` | `tools/knowledge/config.json` `model` / `agent_model` (+ code defaults) |
| Portal assistant (web, phone) | **qwen2.5:1.5b** | `.env` `OLLAMA_MODEL` / `OLLAMA_STUDENT_MODEL` |

- **Embeddings:** stay on `nomic-embed-text`.
- **Removed:** llama3.2:3b, qwen3:4b, qwen2.5:7b (about 9 GB).
- **GPU rule unchanged** (`tools/knowledge/gpu_gate.py`): the cameras keep the GPU while they analyse; the assistants use the
  GPU only after 2 minutes of camera idle.
- **Rollback (knowledge):** set `model` / `agent_model` back to `qwen2.5:1.5b` in `tools/knowledge/config.json` and restart
  the knowledge service.
