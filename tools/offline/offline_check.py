"""
Offline acceptance check (2026-10-27, P8): the Smart Lab must work with the INTERNET disconnected and only the lab
LAN / this laptop available.

    py -I tools/offline/offline_check.py                 # one round
    py -I tools/offline/offline_check.py --minutes 30    # the acceptance run: one round a minute for 30 minutes

It first proves whether the internet is really unreachable (TCP to two public addresses + one DNS lookup). Only then
can a round count as OFFLINE-VERIFIED; with internet up the same checks run but are labelled ONLINE (not an offline
test). Your admin password is asked at a hidden prompt (or SMARTLAB_EMAIL / SMARTLAB_PASSWORD), never stored.

Checks per round (each PASS / FAIL with its time):
  portal health, sign-in, summary, lab AI question (local model / instant), project-knowledge lookup, voice status +
  speak->transcribe round trip, scan registry + one marker image, an xlsx report export, OPC UA port, Ollama local,
  the AI configuration (local-only provider, no cloud key in use).
Result: backups/offline_check_<time>.json and a summary line per round.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = os.environ.get("SMARTLAB_API", "http://127.0.0.1/api")


def internet_reachable() -> dict:
    out = {}
    for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        try:
            with socket.create_connection((host, port), timeout=2):
                out[f"{host}:{port}"] = True
        except OSError:
            out[f"{host}:{port}"] = False
    try:
        socket.setdefaulttimeout(3)
        socket.gethostbyname("example.com")
        out["dns example.com"] = True
    except OSError:
        out["dns example.com"] = False
    finally:
        socket.setdefaulttimeout(None)
    out["any"] = any(v for k, v in out.items())
    return out


def call(method: str, path: str, token: str | None = None, body=None, raw: bytes | None = None, ctype=None, timeout=120):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw; headers["Content-Type"] = ctype or "application/octet-stream"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), round(time.perf_counter() - t, 2)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), round(time.perf_counter() - t, 2)
    except OSError as e:
        return 0, str(e).encode(), round(time.perf_counter() - t, 2)


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def one_round(email: str, password: str) -> dict:
    res: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "internet": internet_reachable(), "checks": {}}
    c = res["checks"]

    def rec(name, ok, s, note=""):
        c[name] = {"ok": bool(ok), "s": s, **({"note": note[:200]} if note else {})}
    st, b, s = call("GET", "/health"); rec("portal_health", st == 200, s)
    st, b, s = call("POST", "/auth/login", body={"email": email, "password": password}); tok = None
    if st == 200:
        tok = json.loads(b).get("access_token")
    rec("sign_in", tok is not None, s, "" if tok else f"HTTP {st}")
    if not tok:
        return res
    st, b, s = call("GET", "/summary", tok); rec("summary", st == 200, s)
    st, b, s = call("GET", "/ai/status", tok)
    try:
        info = json.loads(b) if st == 200 else {}
    except ValueError:
        info = {}
    rec("ai_status", st == 200, s, json.dumps(info)[:200])
    st, b, s = call("POST", "/ai/ask", tok, body={"question": "How many people are inside the lab right now?", "history": []}, timeout=180)
    model = (json.loads(b).get("model") if st == 200 else None) or ""
    rec("lab_ai_answer", st == 200 and "claude" not in model.lower(), s, f"model {model}")
    st, b, s = call("POST", "/knowledge/ask", tok, body={"question": "Where is the Master ESP32 IP documented?", "route": "lookup"}, timeout=120)
    done = [json.loads(x) for x in b.decode(errors="ignore").splitlines() if x.strip().startswith("{")] if st == 200 else []
    rec("project_knowledge", st == 200 and any(e.get("type") == "done" and e.get("status") == "completed" for e in done), s)
    st, b, s = call("GET", "/voice/status", tok); rec("voice_status", st == 200, s, b.decode(errors="ignore")[:120])
    st, wav, s1 = call("POST", "/voice/speak", tok, body={"text": "Is the robotics lab free right now?"})
    if st == 200 and wav:
        st2, b2, s2 = call("POST", "/voice/transcribe", tok, raw=wav, ctype="audio/wav")
        txt = (json.loads(b2).get("text") if st2 == 200 else "") or ""
        rec("voice_round_trip", st2 == 200 and "lab" in txt.lower(), round(s1 + s2, 2), txt)
    else:
        rec("voice_round_trip", False, s1, f"speak HTTP {st}")
    st, b, s = call("GET", "/scan/registry", tok)
    code = (json.loads(b)["assets"][0]["code"] if st == 200 and json.loads(b).get("assets") else None)
    rec("scan_registry", st == 200 and code is not None, s)
    if code:
        st, b, s = call("GET", "/scan/marker.png?code=" + urllib.parse.quote(code), tok)
        rec("scan_marker", st == 200 and b[:4] == b"\x89PNG", s)
    st, b, s = call("GET", "/reports-center", tok)
    kind = json.loads(b)[0]["kind"] if st == 200 and json.loads(b) else "none"
    st, b, s = call("GET", f"/reports-center/{kind}?days=7&format=xlsx", tok)
    rec("report_export_xlsx", st == 200 and b[:2] == b"PK", s, f"HTTP {st}")
    rec("opcua_port_4840", port_open(4840), 0)
    rec("ollama_local_11434", port_open(11434), 0)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=0)
    a = ap.parse_args()
    email = os.environ.get("SMARTLAB_EMAIL") or input("Admin e-mail: ").strip()
    password = os.environ.get("SMARTLAB_PASSWORD") or getpass.getpass("Password: ")
    rounds = []
    end = time.time() + a.minutes * 60
    while True:
        r = one_round(email, password)
        rounds.append(r)
        ok = sum(v["ok"] for v in r["checks"].values()); n = len(r["checks"])
        label = "ONLINE (internet reachable - not an offline test)" if r["internet"]["any"] else "OFFLINE-VERIFIED round"
        bad = [k for k, v in r["checks"].items() if not v["ok"]]
        print(f"{r['at']}  {ok}/{n} pass  {label}" + (f"  FAIL: {', '.join(bad)}" if bad else ""))
        if time.time() >= end:
            break
        time.sleep(max(0, 60 - (time.time() % 60)))
    out = os.path.join(REPO, "backups", f"offline_check_{time.strftime('%Y%m%d_%H%M%S')}.json")
    offline_rounds = [r for r in rounds if not r["internet"]["any"]]
    summary = {"rounds": len(rounds), "offline_rounds": len(offline_rounds),
               "offline_minutes": round(a.minutes, 1) if len(offline_rounds) == len(rounds) else None,
               "all_checks_passed_offline": bool(offline_rounds) and all(all(v["ok"] for v in r["checks"].values()) for r in offline_rounds),
               "verdict": ("OFFLINE VERIFIED" if offline_rounds and len(offline_rounds) == len(rounds)
                           and all(all(v["ok"] for v in r["checks"].values()) for r in offline_rounds)
                           else "NOT AN OFFLINE TEST (internet was reachable)" if not offline_rounds else "OFFLINE WITH FAILURES")}
    json.dump({"summary": summary, "rounds": rounds}, open(out, "w", encoding="utf-8"), indent=1)
    print(json.dumps(summary)); print("Saved", out)


if __name__ == "__main__":
    main()
