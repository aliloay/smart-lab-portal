#!/usr/bin/env bash
# Every candidate on the same frozen workload (bench.py), CPU 4 threads, both camera services watched.
#   bash tools/llm_bench/sweep.sh <ctx.json> <out.jsonl> model [model ...]
# Each model is stopped after its run so only one is in memory at a time.
CTX=$1; OUT=$2; shift 2
HERE=$(cd "$(dirname "$0")" && pwd)
CAMS=http://127.0.0.1:5102/health,http://127.0.0.1:5103/health
for m in "$@"; do
  think=none
  case "$m" in qwen3*|qwen3.5*|*lfm2.5-thinking*|gemma4*) think=false ;; esac
  ollama stop "$m" >/dev/null 2>&1
  echo "=== $m (think=$think)"
  py "$HERE/bench.py" --ctx "$CTX" --model "$m" --gpu 0 --threads 4 --reps 1 --think $think \
     --cams "$CAMS" --label "ollama $m cpu t4" --out "$OUT" 2>&1 | tail -1
  ollama stop "$m" >/dev/null 2>&1
done
