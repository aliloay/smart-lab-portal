#!/usr/bin/env python3
"""
Local knowledge service for the portal and n8n - 127.0.0.1 only (never the lab network).

    py tools/knowledge/serve.py            # http://127.0.0.1:5199

The portal backend (Docker) reaches it as http://host.docker.internal:5199; n8n the same way.
Measured 2026-10-14: a 127.0.0.1-bound service is reachable from the containers and NOT from
the LAN address. Every request needs the header X-KB-Key (tools/knowledge/config.json
"service_key", created on first start; the backend reads KB_SERVICE_KEY from .env).

  GET  /status                     index, embeddings, model, last jobs
  POST /ask   {"question", "route"?}  NDJSON stream: meta, step, sources, token, done
  POST /jobs/build | /jobs/health | /jobs/drift | /jobs/digest
                                   maintenance jobs; one at a time (409 while one runs)
Nothing here writes outside the vault / private data folders, and nothing touches the
database, devices, Docker or n8n.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent  # noqa: E402
import kb  # noqa: E402

PORT = 5199
JOB_LOCK = threading.Lock()
LLM_LOCK = threading.Semaphore(2)          # at most 2 answers at once (CPU protection)
STATE = {"jobs": {}}


def service_key(cfg_path=os.path.join(HERE, "config.json")) -> str:
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.isfile(cfg_path) else \
        json.load(open(os.path.join(HERE, "config.example.json"), encoding="utf-8"))
    if not cfg.get("service_key"):
        cfg["service_key"] = secrets.token_urlsafe(32)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=1)
    return cfg["service_key"]


def run_job(name: str) -> dict:
    """Maintenance jobs, each a fixed command of this tool (no arguments from the request)."""
    py = sys.executable
    cmds = {"build": [[py, os.path.join(HERE, "history.py"), "import"], [py, os.path.join(HERE, "history.py"), "pages"],
                      [py, os.path.join(HERE, "kb.py"), "live-export"], [py, os.path.join(HERE, "kb.py"), "build"], [py, os.path.join(HERE, "graph.py"), "build"],
                      [py, "-c", "import sys;sys.path.insert(0,r'%s');import kb;print(kb.build_embeddings(kb.load_config(),log=None))" % HERE]],
            "health": [[py, os.path.join(HERE, "kb.py"), "health"]],
            "drift": [[py, os.path.join(HERE, "kb.py"), "live-export"], [py, os.path.join(HERE, "kb.py"), "drift"]],
            "digest": [[py, os.path.join(HERE, "digest.py")]]}
    t0, outs, ok = time.perf_counter(), [], True
    for c in cmds[name]:
        r = subprocess.run(c, cwd=os.path.abspath(os.path.join(HERE, "..", "..")), capture_output=True,
                           text=True, timeout=1800, encoding="utf-8", errors="ignore")
        outs.append((r.stdout or r.stderr).strip()[-400:])
        if r.returncode != 0:
            ok = False
            break
    return {"job": name, "ok": ok, "seconds": round(time.perf_counter() - t0, 1),
            "finished": datetime.now().astimezone().isoformat(timespec="seconds"), "output": outs[-1] if outs else ""}


class Handler(BaseHTTPRequestHandler):
    server_version = "SmartLabKnowledge/1"
    KEY = ""

    def _auth(self) -> bool:
        if hmac.compare_digest(self.headers.get("X-KB-Key", ""), self.KEY):
            return True
        self._json(401, {"error": "missing or wrong X-KB-Key"})
        return False

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if not self._auth():
            return
        if self.path != "/status":
            return self._json(404, {"error": "not found"})
        cfg = kb.load_config()
        idx_p = os.path.join(cfg["data"], "index.json")
        emb = os.path.join(cfg["data"], "embeddings.npy")
        self._json(200, {"ok": True, "index_built": datetime.fromtimestamp(os.path.getmtime(idx_p)).astimezone().isoformat(timespec="seconds") if os.path.isfile(idx_p) else None,
                         "embeddings": os.path.isfile(emb), "model": cfg.get("agent_model", "qwen2.5:1.5b"),
                         "jobs": STATE["jobs"], "job_running": JOB_LOCK.locked()})

    def do_POST(self):
        if not self._auth():
            return
        try:
            body = self._body()
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        if self.path == "/ask":
            return self._ask(body)
        if self.path.startswith("/jobs/"):
            name = self.path.split("/")[-1]
            if name not in ("build", "health", "drift", "digest"):
                return self._json(404, {"error": "unknown job"})
            if not JOB_LOCK.acquire(blocking=False):
                return self._json(409, {"error": "another job is running - try later"})
            try:
                res = run_job(name)
            finally:
                JOB_LOCK.release()
            STATE["jobs"][name] = res
            return self._json(200 if res["ok"] else 500, res)
        self._json(404, {"error": "not found"})

    def _ask(self, body):
        q = str(body.get("question", "")).strip()[:600]
        if not q:
            return self._json(400, {"error": "empty question"})
        forced = body.get("route") if body.get("route") in ("lookup", "answer", "investigate") else None
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def emit(e):
            try:
                self.wfile.write((json.dumps(e, ensure_ascii=False) + "\n").encode())
                self.wfile.flush()
            except OSError:
                raise KeyboardInterrupt            # the browser closed the stream: stop generating
        cfg = kb.load_config()
        cfg["model"] = cfg.get("agent_model", "qwen2.5:1.5b")
        if not LLM_LOCK.acquire(timeout=60):
            emit({"type": "done", "status": "failed", "error": "busy - two answers already running"})
            return
        try:
            res = agent.run(cfg, q, forced, out=lambda s: emit({"type": "step", "text": s}) if s.startswith("step:") else None,
                            on_token=lambda t: emit({"type": "token", "text": t}), emit=emit)
            emit({"type": "done", **{k: res.get(k) for k in ("status", "route", "error", "note", "total_ms", "retrieval_ms",
                                                              "citations_valid", "answer")},
                  "llm": res.get("llm")})
        except KeyboardInterrupt:
            pass
        finally:
            LLM_LOCK.release()

    def log_message(self, fmt, *args):         # no request bodies in logs
        sys.stderr.write(f"[kb-service] {self.address_string()} {fmt % args}\n")


def warm_up() -> None:
    """Load the answer model and the embedding model into memory now (CPU, same
    options as real questions so Ollama does not reload), so the first question in
    the portal does not wait ~6 s for a model load. Failures only print a line."""
    t0 = time.time()
    try:
        cfg = kb.load_config()
        cfg["model"] = cfg.get("agent_model", "qwen2.5:1.5b")
        agent.ollama_stream(cfg, "Reply with: ok", lambda _t: None)
        kb.embed(cfg, ["warm up"], "search_query: ")
        print(f"[kb-service] models warm in {time.time() - t0:.1f} s")
    except BaseException as e:                 # Ollama down: questions still work later (slower first one)
        print(f"[kb-service] warm-up skipped: {e.__class__.__name__}")


def main():
    Handler.KEY = service_key()
    threading.Thread(target=warm_up, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Smart Lab knowledge service on http://127.0.0.1:{PORT} (this laptop only). Ctrl+C stops.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
