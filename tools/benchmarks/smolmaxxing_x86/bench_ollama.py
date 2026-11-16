"""Smart Lab local-AI benchmark: speed AND answer quality, one variable at a time (2026-11-16).

Read-only use of the local Ollama (11434) or of a separate server given with --url (e.g. an isolated llama.cpp/Ollama on
127.0.0.1:11501). Standard library only; no credentials, no portal, no database, no hardware. Synthetic prompts from
golden_set.json. Refuses to run while a security-camera service is listening, stops when available RAM falls below a
floor, and leaves the model unloaded at the end.

    py -I tools/benchmarks/smolmaxxing_x86/bench_ollama.py --configs gpu,cpu_t4,cpu_t6 --repeats 2 --out results.json

Configs (each changes ONE thing; model, context 4096, temperature 0, seed, prompt and answer length stay fixed):
    gpu     default placement (all layers on the graphics card if it fits)
    cpu_t4  num_gpu 0, 4 threads  (the lab's CPU fallback: OLLAMA_NUM_THREAD=4)
    cpu_t6  num_gpu 0, 6 threads  (one thread per physical core of the i7-9750H)
    cpu_t8 / cpu_t12 are accepted as well.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERA_PORTS = (5100, 5101)
CONFIGS = {
    "gpu": {},
    "cpu_t4": {"num_gpu": 0, "num_thread": 4},
    "cpu_t6": {"num_gpu": 0, "num_thread": 6},
    "cpu_t8": {"num_gpu": 0, "num_thread": 8},
    "cpu_t12": {"num_gpu": 0, "num_thread": 12},
}


# ------------------------------------------------------------------ pure helpers (unit-tested offline) ---------
def percentile(values, p):
    s = sorted(values)
    if not s:
        return None
    return s[min(len(s) - 1, max(0, math.ceil(p / 100 * len(s)) - 1))]


def summarize(values):
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": round(min(values), 3), "median": round(statistics.median(values), 3),
            "p95": round(percentile(values, 95), 3), "max": round(max(values), 3)}


def score_answer(answer: str, must, forbid):
    """(score 0..1, list of missed groups, list of forbidden phrases found). Case-insensitive keyword check."""
    a = (answer or "").lower()
    hit_forbid = [f for f in forbid if f.lower() in a]
    if hit_forbid:
        return 0.0, [], hit_forbid
    missed = [g for g in must if not any(alt.lower() in a for alt in g)]
    return (1 - len(missed) / len(must)) if must else 1.0, missed, []


# ------------------------------------------------------------------ host guards -----------------------------------------
class _MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]


def available_ram_mb() -> float:
    m = _MS()
    m.dwLength = ctypes.sizeof(_MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 20


def port_listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def gpu_snapshot():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu,temperature.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip()
        used, util, temp = [x.strip() for x in out.split(",")]
        return {"vram_used_mb": int(used), "gpu_util_pct": int(util), "gpu_temp_c": int(temp)}
    except Exception:
        return {}


def ollama_rss_mb():
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -like 'ollama*' } | Measure-Object WorkingSet64 -Sum).Sum"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return round(int(out) / 2 ** 20) if out else None
    except Exception:
        return None


# ------------------------------------------------------------------ Ollama calls -----------------------------------------
def _post(url, path, body, stream=False, timeout=300):
    req = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def unload(url, model):
    try:
        _post(url, "/api/generate", {"model": model, "prompt": "", "keep_alive": 0, "stream": False}, timeout=60).read()
    except Exception:
        pass


def chat(url, model, system, user, options, keep_alive):
    body = {"model": model, "stream": True, "keep_alive": keep_alive,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 160, **options}}
    t0 = time.perf_counter()
    first = None
    text = []
    final = {}
    with _post(url, "/api/chat", body) as r:
        for line in r:
            if not line.strip():
                continue
            d = json.loads(line)
            piece = d.get("message", {}).get("content", "")
            if piece:
                if first is None:
                    first = time.perf_counter() - t0
                text.append(piece)
            if d.get("done"):
                final = d
    total = time.perf_counter() - t0
    ev = final.get("eval_count", 0)
    return {"answer": "".join(text), "ttft_s": first, "total_s": total,
            "load_s": final.get("load_duration", 0) / 1e9,
            "prompt_tokens": final.get("prompt_eval_count", 0),
            "prompt_tok_s": final.get("prompt_eval_count", 0) / max(final.get("prompt_eval_duration", 1) / 1e9, 1e-9),
            "gen_tokens": ev, "gen_tok_s": ev / max(final.get("eval_duration", 1) / 1e9, 1e-9)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen2.5:1.5b")
    ap.add_argument("--configs", default="gpu,cpu_t4,cpu_t6")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--min-free-mb", type=int, default=700, help="abort when available RAM falls below this")
    ap.add_argument("--max-minutes", type=int, default=25)
    ap.add_argument("--out", default=str(HERE / "results.json"))
    ap.add_argument("--golden", default=str(HERE / "golden_set.json"), help="alternative case file / system prompt (to A/B a prompt change)")
    a = ap.parse_args(argv)

    busy = [p for p in CAMERA_PORTS if port_listening(p)]
    if busy:
        sys.exit(f"REFUSING: a camera service is listening on {busy}; the GPU and CPU belong to the cameras. Stop nothing - run this when they are idle.")
    gs = json.loads(Path(a.golden).read_text(encoding="utf-8"))
    started = time.time()
    report = {"model": a.model, "url": a.url, "repeats": a.repeats, "host_ram_available_mb_start": round(available_ram_mb()),
              "gpu_start": gpu_snapshot(), "configs": {}}
    errors = 0
    try:
        for name in a.configs.split(","):
            opts = CONFIGS[name]
            unload(a.url, a.model)
            time.sleep(1.5)
            rec = {"options": opts, "cases": [], "cold_load_s": None}
            first_request = True                                # the first answer of a config includes loading the model
            ram_before = available_ram_mb()
            for case in gs["cases"]:
                user = f"SNAPSHOT (synthetic):\n{case['snapshot']}\n\nQuestion: {case['question']}"
                for rep in range(a.repeats):
                    if available_ram_mb() < a.min_free_mb:
                        raise SystemExit(f"STOP: available RAM {available_ram_mb():.0f} MB < floor {a.min_free_mb} MB")
                    if time.time() - started > a.max_minutes * 60:
                        raise SystemExit("STOP: time budget used")
                    try:
                        r = chat(a.url, a.model, gs["system"], user, opts, "3m")
                    except Exception as e:                      # timeouts / server errors are results, not crashes
                        errors += 1
                        rec["cases"].append({"id": case["id"], "rep": rep, "error": str(e)[:120]})
                        if errors > 3:
                            raise SystemExit("STOP: more than 3 errors")
                        continue
                    cold, first_request = first_request, False
                    if cold:
                        rec["cold_load_s"] = round(r["load_s"], 2)
                    sc, missed, forb = score_answer(r["answer"], case["must"], case["forbid"])
                    rec["cases"].append({"id": case["id"], "category": case["category"], "rep": rep, "score": sc,
                                         "missed": missed, "forbidden": forb, "cold": cold,
                                         **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}})
            rec["ram_available_mb_before_load"] = round(ram_before)
            rec["ram_available_mb_warm"] = round(available_ram_mb())
            rec["ollama_working_set_mb_warm"] = ollama_rss_mb()
            rec["gpu_warm"] = gpu_snapshot()
            warm = [c for c in rec["cases"] if "error" not in c and not c.get("cold")]
            rec["summary"] = {
                "ttft_s": summarize([c["ttft_s"] for c in warm if c["ttft_s"] is not None]),
                "total_s": summarize([c["total_s"] for c in warm]),
                "gen_tok_s": summarize([c["gen_tok_s"] for c in warm]),
                "prompt_tok_s": summarize([c["prompt_tok_s"] for c in warm]),
                "quality_mean": round(statistics.mean(c["score"] for c in warm), 3) if warm else None,
                "cases_fully_correct": sum(1 for c in warm if c["score"] == 1.0), "answers": len(warm),
                "forbidden_hits": sum(1 for c in warm if c["forbidden"]), "errors": sum(1 for c in rec["cases"] if "error" in c)}
            report["configs"][name] = rec
            unload(a.url, a.model)
    finally:
        unload(a.url, a.model)
        report["gpu_end"] = gpu_snapshot()
        report["host_ram_available_mb_end"] = round(available_ram_mb())
        report["minutes"] = round((time.time() - started) / 60, 1)
        Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    for n, rec in report["configs"].items():
        s = rec["summary"]
        print(f"{n:8s} TTFT med {s['ttft_s'].get('median')} p95 {s['ttft_s'].get('p95')} | total med {s['total_s'].get('median')} | "
              f"gen {s['gen_tok_s'].get('median')} tok/s | quality {s['quality_mean']} ({s['cases_fully_correct']}/{s['answers']} full) | "
              f"forbidden {s['forbidden_hits']} | errors {s['errors']}")


if __name__ == "__main__":
    main()
