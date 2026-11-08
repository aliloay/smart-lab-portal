"""
Local LLM benchmark on the REAL Smart Lab assistant workload (2026-10-26).

Same frozen input for every model: the staff system prompt + live SNAPSHOT exported from the isolated copy database
(ctx.json) and the backend's own tool definitions. The flow is the backend's (app/services/ai.py _ask_ollama):
  pass 1  snapshot + question, no tools -> an answer, or "NEED_TOOLS"
  pass 2  (only when NEED_TOOLS) tool prompt + tool definitions -> which tool the model calls first
Scored per question kind (eval_lab.json). Timings: time to first token, total, prompt tokens/s, generation tokens/s,
model load time (separate). While it runs, a sampler records camera analyses/s (camera services' /health), GPU
utilisation and VRAM (nvidia-smi) and system CPU.

    py tools/llm_bench/bench.py --ctx <ctx.json> --engine ollama --model qwen2.5:1.5b --gpu 0 --threads 4 --reps 2
    py tools/llm_bench/bench.py ... --engine openai --url http://127.0.0.1:8081   (llama.cpp llama-server)
Results: one JSON line appended to --out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics as st
import subprocess
import threading
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r"\d+(?:\.\d+)?")
REFUSAL = ("don't", "do not", "not available", "no data", "not in", "cannot", "can't", "unknown", "not know",
           "no information", "isn't", "is not", "not recorded", "not have", "unable", "no record", "need_tools",
           "not provided", "not listed", "doesn't")


# ------------------------------------------------------------------------------------------- engines ---
def ollama_chat(url, model, messages, opts, tools=None, stream=True, think=None, timeout=600):
    body = {"model": model, "messages": messages, "stream": stream, "options": opts, "keep_alive": "30m"}
    if tools:
        body["tools"] = tools
    if think is not None:
        body["think"] = think
    t0 = time.perf_counter()
    ttft, text, calls, final = None, "", [], {}
    with requests.post(url.rstrip("/") + "/api/chat", json=body, stream=stream, timeout=timeout) as r:
        r.raise_for_status()
        lines = r.iter_lines() if stream else [r.content]
        for line in lines:
            if not line:
                continue
            d = json.loads(line)
            m = d.get("message") or {}
            if (m.get("content") or m.get("tool_calls")) and ttft is None:
                ttft = time.perf_counter() - t0
            text += m.get("content") or ""
            calls += m.get("tool_calls") or []
            if d.get("done"):
                final = d
    total = time.perf_counter() - t0
    ns = 1e9
    return {"text": text, "calls": [c.get("function", {}).get("name") for c in calls], "ttft": ttft or total,
            "total": total, "load_s": (final.get("load_duration") or 0) / ns,
            "p_tok": final.get("prompt_eval_count") or 0, "p_s": (final.get("prompt_eval_duration") or 0) / ns,
            "g_tok": final.get("eval_count") or 0, "g_s": (final.get("eval_duration") or 0) / ns}


def openai_chat(url, model, messages, opts, tools=None, stream=True, think=None, timeout=600):
    body = {"model": model, "messages": messages, "stream": stream, "temperature": opts.get("temperature", 0.2),
            "max_tokens": opts.get("num_predict", 400)}
    if tools:
        body["tools"] = tools
        body["stream"] = stream = False
    if stream:
        body["stream_options"] = {"include_usage": True}
    t0 = time.perf_counter()
    ttft, text, calls, timings = None, "", [], {}
    with requests.post(url.rstrip("/") + "/v1/chat/completions", json=body, stream=stream, timeout=timeout) as r:
        r.raise_for_status()
        if stream:
            for line in r.iter_lines():
                if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
                    continue
                d = json.loads(line[6:])
                timings = d.get("timings") or timings
                for ch in d.get("choices") or []:
                    c = (ch.get("delta") or {}).get("content") or ""
                    if c and ttft is None:
                        ttft = time.perf_counter() - t0
                    text += c
        else:
            d = r.json()
            timings = d.get("timings") or {}
            m = d["choices"][0]["message"]
            text = m.get("content") or ""
            calls = [c["function"]["name"] for c in m.get("tool_calls") or []]
    total = time.perf_counter() - t0
    return {"text": text, "calls": calls, "ttft": ttft or total, "total": total, "load_s": 0.0,
            "p_tok": timings.get("prompt_n") or 0, "p_s": (timings.get("prompt_ms") or 0) / 1000,
            "g_tok": timings.get("predicted_n") or 0, "g_s": (timings.get("predicted_ms") or 0) / 1000}


# ------------------------------------------------------------------------------------------ sampler ---
class Sampler(threading.Thread):
    def __init__(self, cams):
        super().__init__(daemon=True)
        self.cams, self.stop, self.rows = cams, False, []

    def run(self):
        import psutil
        psutil.cpu_percent(None)
        while not self.stop:
            row = {"t": time.time(), "cpu": psutil.cpu_percent(None)}
            try:
                g = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=3).stdout.strip().split(",")
                row["gpu"], row["vram"] = float(g[0]), float(g[1])
            except Exception:
                pass
            for c in self.cams:
                try:
                    h = requests.get(c, timeout=1.5).json()
                    row.setdefault("fps", []).append(h.get("fps"))
                    row.setdefault("age", []).append((h.get("stream") or {}).get("frame_age_s"))
                except Exception:
                    row.setdefault("fps", []).append(None)
            self.rows.append(row)
            time.sleep(1.0)

    def summary(self):
        def med(xs):
            xs = [x for x in xs if x is not None]
            return round(st.median(xs), 2) if xs else None
        n = len(self.cams)
        return {"cpu_med": med([r["cpu"] for r in self.rows]), "gpu_med": med([r.get("gpu") for r in self.rows]),
                "vram_max": max([r.get("vram") or 0 for r in self.rows] or [0]),
                "cam_fps_med": [med([(r.get("fps") or [None] * n)[i] for r in self.rows]) for i in range(n)],
                "cam_fps_min": [min([x for x in [(r.get("fps") or [None] * n)[i] for r in self.rows] if x is not None],
                                    default=None) for i in range(n)]}


# ------------------------------------------------------------------------------------------- scoring ---
def score_text(q, text):
    low = text.lower()
    if q["kind"] == "snapshot":
        if "NEED_TOOLS" in text:
            return False
        ok = all(a.lower() in low for a in q.get("all", []))
        return ok and all(any(x.lower() in low for x in grp) for grp in q.get("any", []))
    if q["kind"] == "unknown":
        return any(r in low for r in REFUSAL)
    return "NEED_TOOLS" in text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--eval", default=os.path.join(HERE, "eval_lab.json"))
    ap.add_argument("--engine", default="ollama", choices=["ollama", "openai"])
    ap.add_argument("--url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--gpu", type=int, default=0, help="layers on the GPU (ollama num_gpu); -1 = engine default")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--think", default="none", choices=["none", "false"])
    ap.add_argument("--cams", default="", help="comma-separated camera /health URLs to watch")
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--out", default=os.path.join(HERE, "results.jsonl"))
    a = ap.parse_args()
    ctx = json.load(open(a.ctx, encoding="utf-8"))
    qs = json.load(open(a.eval, encoding="utf-8"))["questions"]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        qs = [q for q in qs if q["id"] in keep]
    chat = ollama_chat if a.engine == "ollama" else openai_chat
    opts = {"temperature": 0.2, "num_ctx": a.num_ctx, "num_thread": a.threads, "num_predict": 400}
    if a.gpu >= 0:
        opts["num_gpu"] = a.gpu
    think = False if a.think == "false" else None
    # cold load (separately timed), then one warm-up so the static prompt prefix is cached
    t0 = time.perf_counter()
    w = chat(a.url, a.model, [{"role": "system", "content": ctx["system"]}, {"role": "user", "content": "Hi"}],
             opts, think=think)
    cold = {"cold_first_s": round(time.perf_counter() - t0, 2), "load_s": round(w["load_s"], 2)}
    sampler = Sampler([c for c in a.cams.split(",") if c])
    sampler.start()
    rows = []
    for rep in range(a.reps):
        for q in qs:
            msgs = [{"role": "system", "content": ctx["system"]}, {"role": "user", "content": q["q"]}]
            try:
                r = chat(a.url, a.model, msgs, opts, think=think)
            except Exception as e:
                rows.append({"id": q["id"], "rep": rep, "error": str(e)[:200]}); continue
            row = {"id": q["id"], "kind": q["kind"], "rep": rep, "ttft": r["ttft"], "total": r["total"],
                   "p_tok": r["p_tok"], "p_tps": r["p_tok"] / r["p_s"] if r["p_s"] else None,
                   "g_tok": r["g_tok"], "g_tps": r["g_tok"] / r["g_s"] if r["g_s"] else None,
                   "ok1": score_text(q, r["text"]), "answer": r["text"][:300]}
            need = "NEED_TOOLS" in r["text"]
            if need and q["kind"] in ("tools", "unknown"):
                m2 = [{"role": "system", "content": ctx["extra"]}, {"role": "user", "content": q["q"]}]
                try:
                    r2 = chat(a.url, a.model, m2, opts, tools=ctx["tools"], think=think)
                    row["calls"] = r2["calls"]
                    row["t2"] = r2["total"]
                    if q["kind"] == "tools":
                        row["ok2"] = bool(r2["calls"]) and r2["calls"][0] in q["tool"]
                    else:
                        row["ok2"] = bool(r2["calls"]) or any(x in r2["text"].lower() for x in REFUSAL)
                except Exception as e:
                    row["ok2"], row["error2"] = False, str(e)[:200]
            elif q["kind"] == "tools":
                row["ok2"] = False                  # answered from the snapshot what it does not contain
            rows.append(row)
            print(f"{q['id']:>2} {q['kind']:<8} ok1={row['ok1']!s:<5} ok2={row.get('ok2', '-')!s:<5} "
                  f"ttft={row['ttft']:.2f} total={row['total']:.2f} g_tps={row['g_tps'] or 0:.1f} | {r['text'][:70]!r}",
                  flush=True)
    sampler.stop = True
    sampler.join(3)
    good = [r for r in rows if "error" not in r]

    def q_(xs, p):
        xs = sorted(x for x in xs if x is not None)
        return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None
    kinds = {}
    for r in good:
        k = r["kind"]
        ok = r["ok1"] if k == "snapshot" else r.get("ok2", r["ok1"] if k == "unknown" else False)
        kinds.setdefault(k, []).append(ok)
    summary = {"label": a.label or f"{a.engine}:{a.model}:gpu{a.gpu}:t{a.threads}", "engine": a.engine, "model": a.model,
               "gpu_layers": a.gpu, "threads": a.threads, "num_ctx": a.num_ctx, "reps": a.reps, "n": len(rows),
               "errors": len(rows) - len(good), **cold,
               "ttft_p50": q_([r["ttft"] for r in good], .5), "ttft_p95": q_([r["ttft"] for r in good], .95),
               "total_p50": q_([r["total"] for r in good], .5), "total_p95": q_([r["total"] for r in good], .95),
               "prompt_tps_p50": q_([r["p_tps"] for r in good], .5), "gen_tps_p50": q_([r["g_tps"] for r in good], .5),
               "acc": {k: f"{sum(v)}/{len(v)}" for k, v in kinds.items()},
               "acc_all": round(sum(sum(v) for v in kinds.values()) / max(1, sum(len(v) for v in kinds.values())), 3),
               **sampler.summary(), "at": time.strftime("%Y-%m-%d %H:%M")}
    print(json.dumps(summary))
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps({**summary, "rows": rows}) + "\n")


if __name__ == "__main__":
    main()
