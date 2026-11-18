# AI_OLLAMA_RAG_VOICE_BENCHMARK.md

- **Evidence Class**: `LIVE_SERVICE` (measured on-site at GIU on 18 Nov while both physical cameras were streaming on the GTX 1650 GPU) + `UNIT_TEST` (`88 passed`).

---

## 1. Root Cause of the Prior Ollama Benchmark Timeout (`LIVE_SERVICE` Forensic Diagnosis)

In the 17 Nov night audit, the standalone Ollama benchmark script timed out after 30 seconds. Today at GIU, we reproduced and inspected `%LOCALAPPDATA%\Ollama\server.log` during the timeout and found the exact root cause:
1. **CUDA vs DirectML Contention on the 4 GB GTX 1650 when `"num_gpu": 0` is omitted on `/api/embeddings`**:
   - Both security cameras (`SECCAM_LAB01` and `SECCAM_LAB02`) run continuous DirectML (`d3d12`) inference at 12–15 Hz on the GTX 1650 (`gpu_mem_mb = 868 MB`, `util = 30–33%`).
   - When a client calls Ollama's legacy `/api/embeddings` endpoint **without** `"options": {"num_gpu": 0}`, Ollama (`server.log`: `load_tensors: offloaded 13/13 layers to GPU, CUDA0 model buffer size = 216.15 MiB`) loads `nomic-embed-text:latest` onto `CUDA0` and executes a CUDA kernel warmup (`warming up the model with an empty run`). Under heavy WDDM context switching against two active DirectML camera processes + 90% host RAM use, the CUDA load/warmup took `55.54 seconds` and stalled!
2. **How Production `kb.py` Avoids This (and How We Hardened It Further)**:
   - `tools/knowledge/kb.py:513` (`embed()`) already passes `"options": {"num_gpu": 0}` to `/api/embed`, keeping `nomic-embed-text` on CPU!
   - However, `kb.py:519` previously used `timeout = 120 s` even for interactive single-query embedding inside `search()` (`kb.py:584`). If Ollama was busy reloading a model, interactive `/ask` could block for up to 120 s before falling back to BM25.
   - **Gemini Fix (`tools/knowledge/kb.py:508, 584`)**: Added `timeout = 4.0 s` (`query_embed_timeout_s`) for interactive single-query `search()`, so if Ollama is cold-loading, `search()` falls back to BM25 within 4 s while batch `build_embeddings` retains the 120 s timeout.

---

## 2. Live On-Site AI, RAG, GPU Gate & Voice Benchmarks (`LIVE_SERVICE`)

All measurements below were taken **while both physical security cameras (`:5100` and `:5101`) were actively streaming and analyzing on the GPU**:

| Subsystem / Benchmark | Measured Latency / Throughput | Output / Verification | Evidence Class |
|---|---|---|---|
| **GPU Gate (`GET :5199/gpu-gate`)** | `6 ms` | `{"device": "cpu", "reason": "camera 5100 live, 5101 live - cameras first"}` (`fps = 5.44 / 5.28`, `gpu_free_mb = 3228.0`) | `LIVE_SERVICE` |
| **Knowledge Service Health (`GET :5199/health`)** | `6 ms` | `{"ok": true, "service": "knowledge"}` | `LIVE_SERVICE` |
| **Knowledge `/ask` (`route="lookup"`, Cameras)** | **`6.1 ms`** total | Instant grounded lookup (`status: "completed"`) | `LIVE_SERVICE` |
| **Knowledge `/ask` (`route="lookup"`, ESP32 Nodes)** | **`95.1 ms`** total | Instant grounded lookup (`status: "completed"`) | `LIVE_SERVICE` |
| **Ollama `nomic-embed-text` (`num_gpu=0` Cold Load)** | **`3,952.4 ms`** | 768-dim L2-normalized embedding on CPU | `LIVE_SERVICE` |
| **Ollama `nomic-embed-text` (`num_gpu=0` Warm)** | **`116.1 ms`** | **`34x` faster** once resident (`keep_alive: "30m"`) | `LIVE_SERVICE` |
| **Ollama `qwen2.5:1.5b` (`num_gpu=0` Cold Load)** | Load: `5,575.5 ms`<br>First token: **`6,963.2 ms`**<br>Full answer (21 tok): **`10,030.9 ms`** (`6.82 tok/s`) | *"The Smart Lab Consumables Bin measures mass in grams using an HX711 load cell."* (Zero hallucinated capacitance/ppm) | `LIVE_SERVICE` |
| **Ollama `qwen2.5:1.5b` (`num_gpu=0` Warm)** | Load: `18.3 ms`<br>First token: **`390.1 ms`**<br>Full answer (21 tok): **`3,620.2 ms`** (`6.50 tok/s`) | **`17.8x` faster first-token latency** when warm on CPU; zero impact on camera FPS (`6.0 fps` maintained on both cameras) | `LIVE_SERVICE` |
| **Voice TTS (`POST :5320/speak`, Piper `en_US-lessac-medium`)** | **`685.9 ms`** (`111,148 B` WAV, `2.52 s` audio) | `3.67x` faster than real-time speech synthesis | `LIVE_SERVICE` |
| **Voice STT (`POST :5320/transcribe`, Faster-Whisper `tiny.en` int8)** | **`3,535.1 ms`** (`decode_ms: 347 ms`) | Transcribed synthesized WAV under 80% concurrent CPU load | `LIVE_SERVICE` |
