# Local-AI benchmark (speed and answer quality) - isolated, read-only

Written 2026-11-16 while assessing `hyperionaidev/smolmaxxing` for the Smart Lab laptop. Result: smolmaxxing's code is ARM-only and was not adopted; this folder keeps the **measurement method**.

## What it is
`bench_ollama.py` sends 12 hand-written, **synthetic** Smart Lab questions (`golden_set.json`) to a local Ollama-compatible server and records time to first token, total latency, tokens/s, RAM/VRAM and a keyword quality score (required facts present, forbidden claims absent). One variable per config (`gpu`, `cpu_t4`, `cpu_t6`, ...). Python standard library only; no credentials, no portal, no database, no hardware, no n8n.

## Safety rules built in
- **Refuses to start while a security-camera service listens** on 5100/5101 (the GPU and CPU belong to the cameras). Run it when both cameras are idle.
- Stops below `--min-free-mb` (default 700) available RAM, after `--max-minutes` (25), or after more than 3 errors.
- Leaves the model **unloaded** at the end. Writes results where you point `--out` (use `docs/reports/local-only-*/`; never commit results or model files).
- Talks to the production Ollama (`127.0.0.1:11434`) only as a client, like a user asking a question. For an experiment with another engine use its own port, e.g. `--url http://127.0.0.1:11501`; never another service on 11434, no autostart.

## Run
```powershell
py -I tools\benchmarks\smolmaxxing_x86\bench_ollama.py --configs gpu,cpu_t4,cpu_t6 --repeats 2 --out docs\reports\local-only-2026-11-16\run.json
py -I -m pytest -q tools\benchmarks\smolmaxxing_x86          # offline tests of scoring, statistics and the camera guard
```
About 1.5 minutes for the default run. Read the saved answers, not only the scores: the scoring is keyword-based and has false negatives (and cannot judge wording).

## Limits
Short prompts (~180 tokens; production snapshot prompts are larger); 2 repeats per prompt; one human reviewer; no camera load. At temperature 0 with a fixed seed the GPU still gave different text for 5 of 12 prompts, so wording is not reproducible.

## Not implemented yet
An OpenAI-style adapter (`/v1/chat/completions`) for a separate `llama-server` comparison with the same GGUF - see `docs/reports/local-only-2026-11-16/SMOLMAXXING_X86_BENCHMARK_RESULTS.md` section 6 (needs owner approval for the ~30 MB binary).
