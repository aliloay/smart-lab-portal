"""Knowledge assistant latency benchmark (closure 2026-11-23) against the running service on port 5199.

usage: py tools/perf/kb_latency_bench.py out.json
Read-only questions only. The service key is read from tools/knowledge/config.json and never printed.
Model answers are cached by the service: repeated runs of a model question measure the cache, not the model.
"""
import json
import os
import statistics
import sys
import time
import urllib.request

KEY = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge", "config.json")))["service_key"]
CASES = [
    ("short static (FAQ)", "Where is the Robotics Lab?", 5),
    ("short static (FAQ, what time)", "What time does the robotics lab close?", 5),
    ("restricted (guard)", "What is the admin password?", 5),
    ("short live (device status)", "Is the environment node online?", 3),
    ("normal RAG", "How does the consumables bin estimate the item count?", 1),
    ("long generative", "Explain how the two security cameras share a person's identity between them.", 1),
    ("unknown", "What is the coolant temperature of the FANUC controller right now?", 1),
]


def ask(q):
    req = urllib.request.Request("http://127.0.0.1:5199/ask", data=json.dumps({"question": q}).encode(),
                                 headers={"Content-Type": "application/json", "X-KB-Key": KEY})
    t0, first, route, status, cached, text, ncit = time.perf_counter(), None, None, None, False, "", 0
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "token":
                first = first if first is not None else time.perf_counter() - t0
                text += e.get("text", "")
            elif e.get("type") == "meta":
                ncit = len(e.get("citations") or [])
            elif e.get("type") == "done":
                route, status, cached = e.get("route"), e.get("status"), bool(e.get("cached"))
    return {"total_s": round(time.perf_counter() - t0, 2), "first_token_s": round(first, 2) if first else None,
            "route": route, "status": status, "cached": cached, "citations": ncit, "answer": text[:160]}


out = []
for name, q, n in CASES:
    runs = [ask(q) for _ in range(n)]
    tot = [r["total_s"] for r in runs]
    row = {"case": name, "question": q, "n": n, "median_s": statistics.median(tot), "max_s": max(tot),
           "first_token_s": runs[0]["first_token_s"], "route": runs[0]["route"], "status": runs[0]["status"],
           "citations": runs[0]["citations"], "cached_after_first": [r["cached"] for r in runs[1:]],
           "answer": runs[0]["answer"]}
    out.append(row)
    print(json.dumps(row, ensure_ascii=False))
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
