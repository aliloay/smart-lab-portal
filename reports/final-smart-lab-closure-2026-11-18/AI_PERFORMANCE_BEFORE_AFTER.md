# AI assistant: performance before / after (19 Nov 2026)

**Status: FIXED AND VERIFIED (offline, at home, cameras off). Lab re-measurement with the cameras running: NOT TESTED.**

Commit `7619717` on `fix/pre-lab-hardening`. Files: `tools/knowledge/agent.py`, `tools/knowledge/kb.py`, `tools/knowledge/test_agent.py`.
Model unchanged: `qwen2.5:1.5b` on the CPU (camera-first GPU policy), Ollama, i7-9750H.

## The complaint
At GIU on 18 Nov, generative answers ("Ask the project") took **up to 47 s** while both cameras were analysing.

## What was measured (profiling)
Bench harness: 6 project questions run through `agent.run`. The script is in the session scratchpad; its output is copied below.

| Stage | Baseline finding |
|---|---|
| Instant routes (lookup, lab data) | < 1 s; not the problem |
| Prompt reading (CPU) | ~100–140 tokens/s → a 600-token prompt costs ~5–7 s **before the first word** |
| Generation | ~22 tokens/s → a 170-token answer costs ~8 s |
| Worst case | an "investigate" question built a **1,825-token prompt → 41.3 s** at home. With the cameras taking CPU at the lab, about 2–3× slower: the 47 s seen on 18 Nov |
| Cold model load | 5.6 s the first time after idle |

So latency was mainly **prompt size** plus **answer length**, and the CPU contention from the cameras multiplied both.

## Changes
1. **Evidence:**
   - the best passage gets 720 chars and the other two 400;
   - passages scoring below 45 % of the best are dropped (they were noise);
   - investigate-route extra code is capped at 1,000 chars.
2. **Answer length:** at most 3 sentences / 150 tokens ("stop when it is answered").
3. **Answer cache:** the same question (same route) within 30 min is answered from memory. The key includes the index build time, so a rebuild clears it. This helps an exhibition, where the same questions repeat.
4. **Chunking fix** (quality, see AI_QUALITY_VALIDATION.md): sections are split into equal pieces with a 150-char overlap, so there are no heading-only stubs.
5. **Vault coverage:** the lab-PC relay, PC agent and LAN presence code are now indexed.
6. **Unchanged:** grounding rules, citations, `[n]` validity check, abstain sentence, read-only tools, model, CPU/GPU policy.

## Results (same 6 questions, home laptop, cameras off)

| Run | Median total | Worst total | Prompt tokens (6 q) | Notes |
|---|---|---|---|---|
| Baseline 18 Nov code | 9.5 s | **41.3 s** | 538, 598, 529, 518, 578, **1825** | worst = investigate route |
| After, cold (new prompt, no Ollama prompt cache) | 14.7 s | **22.0 s** | 680, 605, 548, 661, 631, **1046** | the median is higher because the first run loaded the model cold, next to the embedding job |
| After, warm (Ollama KV cache) | 11.1 s | 13.6 s | same | |
| Live service `:5199/ask`, new question | **5.3 s** total, first word 3.8 s | | | through the real streaming endpoint |
| Live service, same question again | **0.0 s** | | | answer cache hit |

The worst case went from 41 s to 22 s (−47 %), and the investigate prompt from 1,825 to 1,046 tokens (−43 %). Repeated questions are instant.
The portal streams tokens, so a visitor sees the first words after the prompt is read (~4–7 s at home), not the total time.

**Expected at the lab (UNVERIFIED until measured there):** about 2–3× the home numbers while both cameras analyse.
That means about 10–20 s to the first word on a new question, a worst case under ~45 s, and repeats instant.
The remaining lever is the GPU (the A/B on 19 Oct gave 68 s → 3 s). It stays off because the owner reverted it after the two-camera test (cameras first).
It can be switched with `llm_gpu_policy` / `OLLAMA_CPU_ONLY` if the owner decides.

## Tests
`py -m pytest -q tools/knowledge` → **52 passed**. Two new tests: the cache answers a repeated question without calling the model, and long sections split into equal pieces with no stub.
