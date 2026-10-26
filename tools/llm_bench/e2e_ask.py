"""
End-to-end Lab AI benchmark through the REAL backend (POST /api/ai/ask on the isolated copy backend, 127.0.0.1:8100):
instant database answers -> keyword tool router -> local model, exactly as the portal runs it. Same 52 questions
(eval_lab.json); the model under test is whatever the copy backend's OLLAMA_MODEL is. Camera services are sampled.

    E2E_EMAIL=... E2E_PASSWORD=... py tools/llm_bench/e2e_ask.py --label "<config>" [--cams url,url] [--out file]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time

import requests

from bench import REFUSAL, Sampler

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:8100/api"
assert ":8100" in BASE                                    # the isolated copy only


def ok_for(q, r):
    ans, tools = (r.get("answer") or ""), r.get("tools_used") or []
    low = ans.lower()
    k = q["kind"]
    if k in ("snapshot", "instant"):
        if "NEED_TOOLS" in ans:
            return False
        return all(a.lower() in low for a in q.get("all", [])) and \
            all(any(x.lower() in low for x in grp) for grp in q.get("any", []))
    if k == "tools":                    # the right tool, or an exact database answer before any model
        return any(t in tools for t in q["tool"]) or any(str(u).startswith("instant") for u in tools)
    return any(x in low for x in REFUSAL) or (bool(tools) and "snapshot" not in tools)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--cams", default="")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(HERE, "results_e2e.jsonl"))
    a = ap.parse_args()
    qs = json.load(open(os.path.join(HERE, "eval_lab.json"), encoding="utf-8"))["questions"]
    s = requests.Session()
    tok = s.post(BASE + "/auth/login", json={"email": os.environ["E2E_EMAIL"], "password": os.environ["E2E_PASSWORD"]}).json()["access_token"]
    s.headers["Authorization"] = "Bearer " + tok
    s.post(BASE + "/ai/ask", json={"question": "Is LAB_01 ready?", "history": []}, timeout=600)   # warm the model
    sampler = Sampler([c for c in a.cams.split(",") if c]); sampler.start()
    rows = []
    for rep in range(a.reps):
        for q in qs:
            t0 = time.perf_counter()
            r = s.post(BASE + "/ai/ask", json={"question": q["q"], "history": []}, timeout=600)
            dt = time.perf_counter() - t0
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            row = {"id": q["id"], "kind": q["kind"], "rep": rep, "status": r.status_code, "s": round(dt, 3),
                   "path": "instant" if body.get("instant") else "routed" if body.get("routed") else "model",
                   "tools": body.get("tools_used"), "ok": r.status_code == 200 and ok_for(q, body),
                   "answer": (body.get("answer") or body.get("detail") or "")[:240]}
            rows.append(row)
            print(f"{q['id']:>2} {q['kind']:<8} {row['path']:<7} ok={row['ok']!s:<5} {dt:6.2f}s | {row['answer'][:80]!r}", flush=True)
    sampler.stop = True; sampler.join(3)

    def pq(xs, p):
        xs = sorted(xs); return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None
    by = {}
    for r in rows:
        by.setdefault(r["path"], []).append(r["s"])
    acc = {}
    for r in rows:
        acc.setdefault(r["kind"], []).append(r["ok"])
    summ = {"label": a.label, "n": len(rows), "errors": sum(r["status"] != 200 for r in rows),
            "all_p50": pq([r["s"] for r in rows], .5), "all_p95": pq([r["s"] for r in rows], .95),
            "by_path": {k: {"n": len(v), "p50": pq(v, .5), "p95": pq(v, .95)} for k, v in by.items()},
            "acc": {k: f"{sum(v)}/{len(v)}" for k, v in acc.items()},
            "acc_all": round(sum(r["ok"] for r in rows) / len(rows), 3), **sampler.summary(), "at": time.strftime("%Y-%m-%d %H:%M")}
    print(json.dumps(summ))
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps({**summ, "rows": rows}) + "\n")


if __name__ == "__main__":
    main()
