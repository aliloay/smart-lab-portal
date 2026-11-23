"""Routing evaluation for the knowledge assistant (closure 2026-11-23). No model is called.

    py tools/knowledge/route_eval.py [route_eval.json]

For each held-out question it computes the fast route exactly as agent.run does before the model:
guard -> route() -> evidence (real index) -> faq_answer (+ investigate rule) -> status_guard -> "model"/"lookup".
`expect` lists the acceptable outcomes separated by "|": "faq:<exact FAQ question>", "guard:<kind>", "notfaq"
(anything except an FAQ answer: the model, lookup or a guard is fine), "model".
The number that must stay 0 is WRONG_FAQ: a curated answer given to a different question.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent  # noqa: E402
import kb  # noqa: E402


def fast_route(cfg, q):
    g = agent.guard(q)
    if g:
        return "guard:" + g.split("+")[0]
    r, _ = agent.route(q)
    hits, _ = agent.evidence(cfg, q, agent.FAST["k"] if r != "lookup" else 6)
    if not hits:
        return "model"
    fa = agent.faq_answer(q, hits)
    if fa and r == "investigate" and fa["match"] < 0.8:
        fa = None
    if fa:
        return "faq:" + fa["heading"]
    fs = agent.faq_semantic(cfg, q)
    if fs and not (r == "investigate" and fs["match"] < agent.FAQ_SEM_INVESTIGATE):
        return "faq:" + fs["heading"]
    if agent.status_guard(q):
        return "guard:live"
    return "lookup" if r == "lookup" else "model"


def ok(got, expect):
    for e in expect.split("|"):
        if e == "notfaq" and not got.startswith("faq:"):
            return True
        if e == "model" and got in ("model", "lookup"):
            return True
        if got == e:
            return True
    return False


def main(path):
    cfg = kb.load_config()
    rows = json.load(open(path, encoding="utf-8"))
    res = {"total": len(rows), "pass": 0, "wrong_faq": 0, "missed_faq": 0, "missed_guard": 0, "fails": []}
    for row in rows:
        got = fast_route(cfg, row["q"])
        if ok(got, row["expect"]):
            res["pass"] += 1
            continue
        if got.startswith("faq:"):
            res["wrong_faq"] += 1
        elif "faq:" in row["expect"]:
            res["missed_faq"] += 1
        elif "guard:" in row["expect"]:
            res["missed_guard"] += 1
        res["fails"].append({"q": row["q"], "expect": row["expect"], "got": got})
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "route_eval.json"))
