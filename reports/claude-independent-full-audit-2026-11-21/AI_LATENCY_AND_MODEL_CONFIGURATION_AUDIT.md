# AI latency and model configuration audit

## Configuration (LIVE-VERIFIED, 19:09–19:30)

| Item | Value | Source |
|---|---|---|
| Ollama | `127.0.0.1:11434`, CUDA GTX 1650 detected (3.2 GiB available), `OLLAMA_FLASH_ATTENTION=true`, `KV_CACHE_TYPE=q8_0`, `NUM_PARALLEL=1` | `%LOCALAPPDATA%\Ollama\server.log` |
| Installed models | `qwen3:1.7b` (Q4_K_M), `qwen2.5:1.5b` (Q4_K_M), `nomic-embed-text` (F16) | `/api/tags` |
| **Resident models** | **all three, `size_vram = 0` (CPU)**, keep-alive about 4 h | `/api/ps` before and after the benchmark |
| Portal assistant | `OLLAMA_MODEL = OLLAMA_STUDENT_MODEL = qwen2.5:1.5b`, `OLLAMA_GPU_POLICY=auto`, `OLLAMA_CPU_ONLY=false`, `NUM_THREAD=4`, `KEEP_ALIVE=4h` | `docker compose exec backend printenv` |
| Knowledge assistant | `model = agent_model = qwen3:1.7b`, `llm_gpu_policy=auto`, `llm_on_cpu=true` (ignored under auto), timeout 240 s | `tools/knowledge/config.json` (git-ignored; secrets not reproduced) |
| GPU gate | `{"device":"gpu","reason":"cameras idle"}` since about 17:27 | `GET :5199/gpu-gate` |
| Embeddings/index | built 18:01 today, 13,292 chunks (162 new), job 302 s | `GET :5199/status` |

### The "qwen2.5:3b" mismatch

- **Fixed in the live configuration.** Knowledge now names `qwen3:1.7b`, which is installed.
- Leftovers: `.env.example:23` and `backend/.env.example:70` comments, and the `test_ai_local.py` fixtures, where it is harmless.
- **CLAUDE.md is stale.** It still says "both assistants run qwen2.5:1.5b on the GPU" (F-18).

## Measured latency (TESTED, knowledge service `/ask`, CPU-resident models, cameras idle, backend tests finished)

Harness: `scratchpad/audit_aibench.py`. Raw data: `evidence/knowledge_latency.json`.

| Class | Question | Route | First token | Total | Notes |
|---|---|---|---|---|---|
| Short fact (lookup) | "Which port does the knowledge service listen on?" | lookup | – | **1.41 s** first / 0.10 s warm | evidence only: `answer=null`, citations returned |
| Short fact (lookup) | "Where is the reusable bin firmware?" | lookup | – | **0.099 s** (retrieval 97.6 ms) | correct file cited |
| Live/identifier fact | "What IP address does the environment node use?" | answer | **7.77 s** | **11.67 s** | prompt 505 tok in 7.71 s; 47 answer tokens in 3.68 s (**12.8 tok/s**); correct answer, `citations_valid=true` |
| Normal RAG | "How does the consumables bin calculate stock from weight?" | answer | 9.70 s | **15.69 s** | **answer partly wrong** ("counting the number of items"); truth = (total − tare) / unit mass |
| Multi-document | "Compare how the door master and the reusable bin report…" | answer | 12.96 s | **18.38 s** | garbled comparison |
| Needs refusal | "WiFi password of the GIU campus network?" | guard | 0.02 s | **0.02 s** | correct refusal, cites the exclusion policy |
| Repeat | same as the first question | cache | – | **0.00 s** | answer cache works |

### Comparison with the owner's 21 Nov benchmark (HISTORICAL)

- qwen3:1.7b on the GPU: 5.4 s median total.
- qwen3:1.7b on the CPU: 12.7 s median total.
- **My measurements match the CPU row.**

### Not measured

- **The portal assistant (`/api/ai/...`):** it needs a signed-in user. I did not use credentials and did not mint tokens. The `agent_live.py` instant answers (lab count, device by role, ESP32 boards, model in use) are covered by backend tests only.
- **Frontend rendering time:** not measured.

## F-05: GPU gate says GPU, but the models stay on the CPU

1. When cameras are live, `gpu_gate` correctly returns CPU, and both callers send `options.num_gpu = 0`.
2. When the gate flips to "gpu", callers just omit `num_gpu` (`tools/knowledge/kb.py:680`, `agent.py:184`, `backend/app/services/ai.py:556/628/795`).
3. **Observed:** the runner already resident on the CPU kept serving (size_vram stayed 0 after 4 synthesis calls), so the GPU was never used.
4. **Likely mechanism (UNVERIFIED):** Ollama reuses a loaded runner when the request does not specify a conflicting `num_gpu`. Keep-alive is 4 h.
5. **Fix options:**
   - (a) When the gate flips CPU → GPU, send one `{"model": m, "keep_alive": 0}` to unload, so the next call loads on the GPU.
   - (b) Send an explicit `num_gpu` (e.g. 999) when the gate says GPU.
   - Then re-measure. The expected result (owner's benchmark, HISTORICAL) is about 5 s.
6. **Camera safety is unaffected:** an unwanted CPU load is the safe direction.

## Where the time goes

Breakdown for the 11.7 s answer:

| Stage | Time | Share |
|---|---|---|
| Retrieval (embedding + search) | 0.19 s | 2 % |
| Prompt evaluation (505 tokens on the CPU) | 7.7 s | 66 % |
| Generation (47 tokens at 12.8 tok/s) | 3.7 s | 32 % |

- **Prompt evaluation dominates.** Shorter contexts (fewer and shorter citations) or the GPU would help most.

## Fast-answer architecture

See FAQ_FAST_ANSWER_PROPOSAL.md.

### Architecture comparison

| Architecture | Latency (measured or derived) | Quality | Freshness | Grounding | Maintenance risk |
|---|---|---|---|---|---|
| Current full RAG (CPU) | 11.7–18.4 s measured | variable; 1 of 3 synthesis answers contained an invented statement | index age (rebuilt 18:01) | citations validated | low |
| Current full RAG (GPU) | about 5 s (historical benchmark) | same | same | same | low |
| Lookup route (evidence only) | 0.1 s measured | the user reads the snippets; no synthesis | index age | exact citations | low |
| FAQ fast path (curated answer + source) | expected < 0.1 s (a dictionary lookup; not measured) | exact if curated | stale if facts change; needs a source-hash check | the FAQ entry cites a file and line | **medium**: entries must be re-validated when the source changes |
| Direct live lookup (DB/API) | expected 10–50 ms (the API answers in 14 ms for health; not measured for these queries) | exact | live | the API is the source | low, if each intent is a typed query |
| Cached static fact | 0 s measured (answer cache) | as good as the first answer | invalidated by index rebuild | as the first answer | low |
| **Hybrid (recommended)** | < 0.1 s for matched intents, otherwise RAG | best | live for status, index for docs | always cited | medium; mitigated by strict intent matching plus a fallback to RAG on low confidence |

### Fragility controls

- Match on entity IDs (device UID, IP, lab code, file path), not loose keywords.
- Require one entity plus one intent.
- On ambiguity, fall back to RAG.
- Every FAQ answer carries its source path, and a CI test re-checks the fact against the source file. The repo already has `tools/knowledge/eval_questions.json`; extend it.
