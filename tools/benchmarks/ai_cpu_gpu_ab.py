"""A/B: the assistants' model (qwen2.5:1.5b) answering on the CPU (num_gpu 0) vs the GPU, same prompts.
Read-only for the portal; only talks to the local Ollama. Run it ONLY while both cameras are idle
(the GTX 1650 belongs to the cameras). Leaves the model back on the CPU at the end.
    py -I tools/benchmarks/ai_cpu_gpu_ab.py [reps]
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen2.5:1.5b"
PROMPTS = [
    "In two sentences: why must the lab door stay locked when the portal is offline?",
    "List three checks before starting a UR5e robot, one line each.",
    "Explain in one paragraph what a cable gland does on an electronics enclosure.",
]


def ask(prompt: str, cpu: bool) -> dict:
    body = {"model": MODEL, "prompt": prompt, "stream": False, "keep_alive": "10m",
            "options": {"num_predict": 120, "temperature": 0, "num_gpu": 0 if cpu else 99}}
    t = time.time()
    req = urllib.request.Request(OLLAMA + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return {"wall_s": round(time.time() - t, 2), "tokens": r.get("eval_count", 0),
            "tok_s": round(r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 1e-9), 1),
            "load_s": round(r.get("load_duration", 0) / 1e9, 2)}


def vram() -> int:
    ps = json.loads(urllib.request.urlopen(OLLAMA + "/api/ps", timeout=10).read())
    return sum(m.get("size_vram", 0) for m in ps.get("models", [])) // 2**20


def main() -> None:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    out = {}
    for mode in ("cpu", "gpu", "cpu"):
        ask("warm up", mode == "cpu")                       # model (re)load is not counted
        runs = [ask(p, mode == "cpu") for _ in range(reps) for p in PROMPTS]
        key = mode if mode not in out else "cpu_after"
        out[key] = {"vram_mb": vram(), "median_wall_s": statistics.median(r["wall_s"] for r in runs),
                    "median_tok_s": statistics.median(r["tok_s"] for r in runs), "runs": runs}
        print(f"{key:9s} vram {out[key]['vram_mb']:5d} MB  answer median {out[key]['median_wall_s']:.2f} s  "
              f"{out[key]['median_tok_s']:.1f} tok/s  (n={len(runs)})")
    print(json.dumps({k: {kk: v for kk, v in d.items() if kk != 'runs'} for k, d in out.items()}))


if __name__ == "__main__":
    main()
