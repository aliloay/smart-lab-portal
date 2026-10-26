"""
Smart Lab full-system load test - SIMULATED, ISOLATED, NON-DESTRUCTIVE.

Runs against a separate backend copy on its own database (default http://127.0.0.1:8100, DB
smartlab_loadtest_test - see docs/perf/LOAD_TEST.md), never the live portal, never a physical
robot or camera. Starts for DURATION seconds:
  * 2 robot collectors, source "sim" (UR5e + FANUC models; posted as SIMULATION)
  * 2 camera services fed from local recordings (ports 5102/5103, devices SECCAM_LT1/LT2)
  * an environment node posting readings every 2 s
  * dashboard API polling at the portal's own rates, latency sampled per endpoint
  * process CPU / memory / thread sampling (psutil) and GPU use (nvidia-smi)
WebSocket clients run separately (tools/perf/ws_clients.mjs) so their numbers are independent.

    py tools/perf/load_simlab.py [seconds] [base]
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import threading
import time

import psutil
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
BASE = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8100").rstrip("/")
API = BASE + "/api"
if "8000" in BASE or BASE.endswith(":80") or BASE == "http://localhost":
    sys.exit("refusing: this test must not run against the live portal")
KEY = [l.split("=", 1)[1].strip().strip('"') for l in open(os.path.join(ROOT, ".env"), encoding="utf-8")
       if l.startswith("DEVICE_API_KEY=")][0]
REC = os.path.join(ROOT, "tools", "security_vision", "recordings")
EMAIL, PASSWORD = os.environ.get("E2E_EMAIL"), os.environ.get("E2E_PASSWORD")


def pct(a, p):
    a = sorted(a)
    return round(a[min(len(a) - 1, int(p * len(a)))], 1) if a else None


def start_workloads():
    procs, env = [], dict(os.environ)
    rm = os.path.join(ROOT, "tools", "robot_monitor")
    for dev, model in (("UR5E_LT", "UR5e"), ("FANUC_LT", "FANUC")):
        procs.append(subprocess.Popen(["py", "-3.12", os.path.join(rm, "robot_collector.py"), "--source", "sim",
                                       "--device", dev, "--model", model, "--portal", API, "--max-minutes", str(DUR / 60 + 1)],
                                      cwd=rm, env={**env, "DEVICE_KEY": KEY}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    sv = os.path.join(ROOT, "tools", "security_vision")
    vids = sorted(f for f in os.listdir(REC) if f.endswith(".mp4"))[-2:]
    extra = os.environ.get("SIMLAB_CAMERA_ARGS", "").split()   # e.g. the old config, for a before/after run
    for port, dev, vid in ((5102, "SECCAM_LT1", vids[0]), (5103, "SECCAM_LT2", vids[-1])):
        procs.append(subprocess.Popen(["py", "security_vision.py", "--lab", "LAB_01", "--device", dev, "--port", str(port),
                                       "--portal", API, "--face-server", ""] + extra, cwd=sv,
                                      env={**env, "SECURITY_CAMERA_SOURCE": os.path.join(REC, vid)},
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    return procs


def env_node(stop):
    s = requests.Session()
    s.headers["X-Device-Key"] = KEY
    t, n = 0, 0
    while not stop.is_set():
        s.post(API + "/access/telemetry", timeout=5, json={"device_uid": "ENV_LT", "lab_id": "LAB_01", "readings": [
            {"metric": "temperature", "value": 23.0 + (n % 10) / 10, "unit": "C"},
            {"metric": "humidity", "value": 45.0, "unit": "%"}, {"metric": "motion", "value": n % 2, "unit": "state"},
            {"metric": "smoke", "value": 0, "unit": "state"}, {"metric": "flame", "value": 0, "unit": "state"}]})
        n += 1
        stop.wait(2.0)


def dashboard(stop, lat, errors):
    s = requests.Session()
    tok = s.post(API + "/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10).json()
    s.headers["Authorization"] = "Bearer " + (tok.get("access_token") or tok.get("token"))
    rid = None
    rates = {"/monitor": 2.5, "/security/cameras": 2.0, "/robots": 2.0, "/labs/hazards/active": 1.7,
             "/system/status": 5.0, "/summary": 10.0, "/health": 5.0}
    due = {k: 0.0 for k in rates}
    while not stop.is_set():
        now = time.time()
        if rid is None:
            try:
                rid = next((r["device_id"] for r in s.get(API + "/robots", timeout=5).json() if r["device_uid"] == "FANUC_LT"), None)
                if rid:
                    rates[f"/robots/{rid}/events?limit=100"] = 2.0
                    due[f"/robots/{rid}/events?limit=100"] = 0.0
            except Exception:
                pass
        for path, every in rates.items():
            if now >= due[path]:
                t = time.perf_counter()
                try:
                    r = s.get(API + path, timeout=10)
                    ok = r.status_code < 400
                except requests.RequestException:
                    ok = False
                lat.setdefault(path.split("?")[0].replace(str(rid), ":id") if rid else path, []).append((time.perf_counter() - t) * 1000)
                if not ok:
                    errors.append(path)
                due[path] = now + every
        stop.wait(0.05)


AI_QUESTIONS = ("Summarise this week for the lab manager in three bullets", "Which lab needs attention first and why?",
                "Compare door refusals this week with last week")


def ai_load(stop, out):
    """SIMLAB_AI=1: the Lab AI model answers one question after another for the whole run (the worst case for the
    cameras: a generation is always running). Times per answer are recorded."""
    s = requests.Session()
    tok = s.post(API + "/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10).json()
    s.headers["Authorization"] = "Bearer " + (tok.get("access_token") or tok.get("token"))
    i = 0
    while not stop.is_set():
        t = time.perf_counter()
        try:
            r = s.post(API + "/ai/ask", json={"question": AI_QUESTIONS[i % len(AI_QUESTIONS)], "history": []}, timeout=300)
            out.append({"ms": (time.perf_counter() - t) * 1000, "status": r.status_code})
        except requests.RequestException as e:
            out.append({"ms": (time.perf_counter() - t) * 1000, "status": e.__class__.__name__})
        i += 1


def sample_resources(stop, out):
    while not stop.is_set():
        procs = [p for p in psutil.process_iter(["name", "cmdline"]) if p.info["name"] and "python" in p.info["name"].lower()
                 and any(x in " ".join(p.info["cmdline"] or []) for x in ("security_vision.py", "robot_collector.py"))]
        try:
            cpu = sum(p.cpu_percent(interval=None) for p in procs)
            rss = sum(p.memory_info().rss for p in procs) / 1e6
            thr = sum(p.num_threads() for p in procs)
        except psutil.Error:
            continue
        g = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True).stdout.strip().split(",")
        out.append({"t": time.time(), "cpu": cpu, "rss_mb": rss, "threads": thr, "procs": len(procs),
                    "gpu": float(g[0]) if g and g[0] else None, "vram": float(g[1]) if len(g) > 1 else None,
                    "sys_cpu": psutil.cpu_percent(interval=None)})
        stop.wait(5.0)


def camera_metrics(port):
    try:
        m = requests.get(f"http://127.0.0.1:{port}/metrics", headers={"X-Device-Key": KEY}, timeout=5).json()
        a = m["analysis"]
        return {"engines": m.get("engines"), "capture_fps": m["capture"]["fps"], "analysis_fps": a["fps"],
                "pass_p50": (a["pass_ms"] or {}).get("p50"), "pass_p95": (a["pass_ms"] or {}).get("p95"),
                "frame_age_p95": (a["frame_age_ms"] or {}).get("p95"), "skipped": a["skipped_latest_frame_policy"],
                "parts_p50": m.get("track_parts_ms_p50")}
    except Exception as e:
        return {"error": e.__class__.__name__}


def main():
    if not EMAIL or not PASSWORD:
        sys.exit("set E2E_EMAIL / E2E_PASSWORD (a seeded account of the load-test database)")
    procs = start_workloads()
    stop, lat, errors, res, ai = threading.Event(), {}, [], [], []
    time.sleep(25)                                   # warm-up: models load, collectors connect
    work = [(env_node, (stop,)), (dashboard, (stop, lat, errors)), (sample_resources, (stop, res))]
    if os.environ.get("SIMLAB_AI") == "1":
        work.append((ai_load, (stop, ai)))
    ths = [threading.Thread(target=f, args=a, daemon=True) for f, a in work]
    t0 = time.time()
    [t.start() for t in ths]
    time.sleep(DUR)
    cams = {p: camera_metrics(p) for p in (5102, 5103)}
    stop.set()
    [t.join(timeout=15) for t in ths]
    for p in procs:
        p.terminate()
    print(f"== SIMULATED load, {round(time.time() - t0)} s after 25 s warm-up, against {BASE} (isolated test DB)")
    for path, v in sorted(lat.items()):
        print(f"  {path:32s} n {len(v):4d}  p50 {pct(v, .5):7}  p95 {pct(v, .95):7}  max {round(max(v), 1):7} ms")
    print(f"  API errors: {len(errors)} {sorted(set(errors))[:5]}")
    for p, m in cams.items():
        print(f"  camera :{p} {m}")
    if ai:
        print(f"  AI answers during the run: {len(ai)}  p50 {pct([a['ms'] for a in ai], .5)} ms  "
              f"statuses {sorted({str(a['status']) for a in ai})}")
    if res:
        print(f"  workload procs {res[-1]['procs']}: cpu {pct([r['cpu'] for r in res], .5)}% (p50, sum)  rss {round(res[0]['rss_mb'])}->{round(res[-1]['rss_mb'])} MB"
              f"  threads {res[0]['threads']}->{res[-1]['threads']}  GPU p50 {pct([r['gpu'] for r in res if r['gpu'] is not None], .5)}%"
              f"  VRAM {res[-1]['vram']} MB  system CPU p50 {pct([r['sys_cpu'] for r in res], .5)}%")


if __name__ == "__main__":
    main()
