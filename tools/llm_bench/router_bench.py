"""
Tool-router benchmark (2026-10-26): reworded questions that avoid the keyword router's words. Compares
  * the keyword router (backend ai.route, re-implemented here from the same patterns via import of the patterns file
    is not possible outside Docker, so the patterns are passed in as JSON by the caller) and
  * small local models choosing a tool through Ollama's tools API (FunctionGemma 270M, Qwen3 0.6B, ...).
Score: right tool (or "none" for questions that need no tool). Time per decision.

    py tools/llm_bench/router_bench.py --ctx ctx.json --model functiongemma:270m [--model qwen3:0.6b ...]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import time

import requests

# expected tool, question (paraphrases the keyword list does not cover on purpose) - "none" = answer from snapshot
CASES = [
    ("get_environment", "How warm is it in the robotics lab today?"),
    ("get_environment", "Is the air in LAB_01 too damp?"),
    ("get_environment", "Did any fire sensor trigger yesterday?"),
    ("get_trends", "Has door usage gone up or down over the past couple of months?"),
    ("get_trends", "Compare each of the last eight weeks for bookings."),
    ("get_maintenance_priorities", "What needs repairing most urgently?"),
    ("get_maintenance_priorities", "Rank the broken things by urgency."),
    ("list_open_issues", "Which problems have people reported in LAB_01?"),
    ("get_lab_readiness", "Can students start working in LAB_01 now?"),
    ("get_lab_readiness", "Is everything in LAB_02 set up for a class?"),
    ("get_anomalies", "Anything weird happening with the door lately?"),
    ("get_anomalies", "Did someone try to force their way in?"),
    ("get_report", "Summarize what happened today."),
    ("list_labs", "How many people fit in each room?"),
    ("get_operations_overview", "How busy were the labs this month?"),
    ("none", "How many door entries were granted this week?"),
    ("none", "Is anyone inside right now?"),
    ("none", "Thanks, that's all."),
]


def keyword_route(routes, q):
    for name, rx in routes:
        if re.search(rx, q.lower()):
            return name
    return "none"


def model_route(url, model, tools, q, think):
    body = {"model": model, "stream": False, "keep_alive": "30m", "tools": tools,
            "options": {"temperature": 0, "num_ctx": 2048, "num_thread": 4, "num_gpu": 0, "num_predict": 64},
            "messages": [{"role": "system", "content": "You route questions about a university lab to ONE tool. Call the "
                          "single best tool. If the question needs no tool (greeting, or a simple count already known), "
                          "reply with the word NONE."}, {"role": "user", "content": q}]}
    if think is not None:
        body["think"] = think
    t = time.perf_counter()
    r = requests.post(url + "/api/chat", json=body, timeout=300)
    dt = time.perf_counter() - t
    if r.status_code != 200:
        return "error:" + r.text[:60], dt
    m = r.json().get("message") or {}
    calls = m.get("tool_calls") or []
    return (calls[0]["function"]["name"] if calls else "none"), dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--routes", default="", help="JSON file with the backend's [[tool, regex], ...]")
    ap.add_argument("--model", action="append", default=[])
    ap.add_argument("--url", default="http://127.0.0.1:11434")
    ap.add_argument("--think-false", action="append", default=[], help="models that need think=false")
    a = ap.parse_args()
    tools = json.load(open(a.ctx, encoding="utf-8"))["tools"]
    out = {}
    if a.routes:
        routes = json.load(open(a.routes, encoding="utf-8"))
        ok = sum(keyword_route(routes, q) == want for want, q in CASES)
        out["keyword_router"] = {"acc": f"{ok}/{len(CASES)}", "ms_p50": 0.1}
        print("keyword", [(q[:30], keyword_route(routes, q)) for want, q in CASES if keyword_route(routes, q) != want])
    for m in a.model:
        think = False if m in a.think_false else None
        model_route(a.url, m, tools, "hello", think)                  # load + warm
        res = [(want,) + model_route(a.url, m, tools, q, think) for want, q in CASES]
        ok = sum(got == want for want, got, _ in res)
        out[m] = {"acc": f"{ok}/{len(CASES)}", "ms_p50": round(st.median(dt for *_, dt in res) * 1000),
                  "ms_max": round(max(dt for *_, dt in res) * 1000),
                  "wrong": [(q[:40], got) for (want, got, _), (_, q) in zip(res, CASES) if got != want]}
        print(m, json.dumps(out[m]))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "wrong"} for k, v in out.items()}))


if __name__ == "__main__":
    main()
