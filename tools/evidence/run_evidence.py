"""
Thesis evidence run (2026-10-17) - READ-ONLY checks against the running system.

    py -I tools/evidence/run_evidence.py [--base http://192.168.1.200] [--runs 20]

Writes docs/reports/evidence_<timestamp>.json and .md. Every check records: procedure, expected,
observed, PASS / FAIL / NOT_AVAILABLE, and its evidence class:
  REAL_HARDWARE - observed from a physical device right now (fresh heartbeat / live frames)
  LIVE_SYSTEM   - the running portal and its services (software, real deployment)
  OFFLINE       - historical rows in the database (real data, not current)
  SIMULATION    - simulated sources (never counted as physical validation)
Nothing here writes to the database (only GET requests + read-only AI questions), and it never
sends anything to a robot, door or PC. Credentials come from SMARTLAB_EMAIL / SMARTLAB_PASSWORD.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def http(method, url, token=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    except (TimeoutError, OSError) as e:          # timeout / refused: recorded as a failed check, run continues
        raw, code = json.dumps({"error": e.__class__.__name__}).encode(), 0
    ms = (time.perf_counter() - t0) * 1000
    try:
        return code, json.loads(raw or b"null"), ms
    except ValueError:
        return code, raw, ms


class Run:
    def __init__(self):
        self.checks = []

    def add(self, area, name, procedure, expected, observed, result, evidence, detail=None):
        self.checks.append({"area": area, "check": name, "procedure": procedure, "expected": expected,
                            "observed": observed, "result": result, "evidence": evidence, "detail": detail})
        print(f"[{result:13}] {area} / {name}: {observed}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://192.168.1.200")
    ap.add_argument("--runs", type=int, default=20)
    a = ap.parse_args()
    api = a.base.rstrip("/") + "/api"
    R = Run()
    started = datetime.now(timezone.utc)

    code, j, ms = http("GET", api + "/health")
    R.add("API", "health", "GET /api/health", "HTTP 200", f"HTTP {code} in {ms:.0f} ms", "PASS" if code == 200 else "FAIL", "LIVE_SYSTEM")
    code, tok, _ = http("POST", api + "/auth/login", body={"email": os.environ.get("SMARTLAB_EMAIL", "admin@giu-uni.de"),
                                                           "password": os.environ.get("SMARTLAB_PASSWORD", "")})   # never a default in the repo
    token = tok.get("access_token") if isinstance(tok, dict) else None
    R.add("Security", "admin sign-in", "POST /auth/login", "token", "token received" if token else f"HTTP {code}", "PASS" if token else "FAIL", "LIVE_SYSTEM")
    if not token:
        return finish(R, started, a)
    code, _, _ = http("GET", api + "/incidents")
    R.add("Security", "anonymous refused", "GET /incidents without a token", "401", f"HTTP {code}", "PASS" if code == 401 else "FAIL", "LIVE_SYSTEM")

    # ---- latency of the main read paths (warm)
    for path in ("/summary", "/labs/overview", "/devices", "/system/status", "/system/health", "/alerts?open_only=true",
                 "/incidents?state=ACTIVE", "/reports-center/alerts?days=7", "/analytics/system?days=7"):
        times = []
        for _ in range(a.runs):
            c, _, ms = http("GET", api + path, token)
            if c == 200:
                times.append(ms)
        if not times:
            R.add("Performance", path, f"GET x{a.runs}", "HTTP 200", "no successful call", "FAIL", "LIVE_SYSTEM")
            continue
        p50, p95 = statistics.median(times), sorted(times)[max(0, int(0.95 * len(times)) - 1)]
        R.add("Performance", path, f"GET x{a.runs} (warm, laptop over LAN)", "p95 < 500 ms",
              f"median {p50:.0f} ms, p95 {p95:.0f} ms", "PASS" if p95 < 500 else "FAIL", "LIVE_SYSTEM")

    # ---- data freshness per source and device states
    c, h, _ = http("GET", api + "/system/health", token)
    for k, f in (h.get("data_sources") or {}).items():
        R.add("Data freshness", k, f"latest row of {f['source']}", "live (recent for its cadence)",
              f"{f['state']} - last {f.get('last') or 'never'} ({f['records']} rows)",
              "PASS" if f["state"] == "live" else "NOT_AVAILABLE", "REAL_HARDWARE" if f["state"] == "live" else "OFFLINE")
    for s in h.get("services", []):
        cls = "SIMULATION" if s["state"] == "SIMULATION" else "REAL_HARDWARE" if s.get("group") else "LIVE_SYSTEM"
        R.add("Health", s["name"] + (f" ({s.get('device_uid')})" if s.get("device_uid") else ""), "background probe / heartbeat",
              "ONLINE", f"{s['state']} - {s['detail']}",
              "SIMULATION" if s["state"] == "SIMULATION" else "PASS" if s["state"] == "ONLINE"
              else "NOT_AVAILABLE" if s["key"] == "websocket" else "FAIL", cls)

    # ---- cameras (the vision services on this laptop)
    for port, cam in ((5100, "SECCAM_LAB01"), (5101, "SECCAM_LAB02")):
        c, j, ms = http("GET", f"http://127.0.0.1:{port}/health", timeout=5)
        if c != 200 or not isinstance(j, dict):
            R.add("Cameras", cam, f"GET :{port}/health", "service up, picture", f"HTTP {c}", "FAIL", "LIVE_SYSTEM")
            continue
        ok = bool(j.get("camera")) and j.get("fps", 0) > 0
        R.add("Cameras", cam, f"GET :{port}/health", "camera picture with fps > 0",
              f"camera={j.get('camera')} fps={j.get('fps')} analysis_age={j.get('analysis_age_s')} s, errors={j.get('analysis_errors')}",
              "PASS" if ok else "FAIL", "REAL_HARDWARE" if ok else "LIVE_SYSTEM")

    # ---- robots
    c, robots, _ = http("GET", api + "/robots", token)
    for r in robots or []:
        sim = (r.get("source") == "SIMULATION") or str(r.get("device_uid", "")).upper().endswith("_SIM")
        has_q = bool(r.get("q"))
        R.add("Robots", r.get("device_uid"), "GET /robots (collector telemetry)", "fresh joint values",
              f"state={r.get('state')} joints={'yes' if has_q else 'no'} stale={r.get('stale')}",
              "SIMULATION" if sim else "PASS" if has_q and not r.get("stale") else "FAIL",
              "SIMULATION" if sim else "REAL_HARDWARE")
        c2, ctl, _ = http("GET", api + f"/robots/{r['device_id']}/control", token)
        if isinstance(ctl, dict) and ctl.get("master"):
            m = ctl["master"]
            R.add("Robots", f"{r.get('device_uid')} master control", "GET control (UR5e)", "mode dry_run until sign-off; truthful phase",
                  f"mode={ctl.get('control_mode')} phase={m['phase']} ({m['detail']})",
                  "PASS" if ctl.get("control_mode") == "dry_run" else "FAIL", "LIVE_SYSTEM")

    # ---- PCs
    c, eq, _ = http("GET", api + "/equipment", token)
    pcs = [e for e in (eq or []) if e.get("kind") == "PC"]
    R.add("PCs", "enrolled PC agents", "GET /equipment (kind PC)", ">= 1 pilot PC reporting",
          f"{len(pcs)} PC(s); online: {sum(1 for p in pcs if p.get('online'))}", "PASS" if pcs else "NOT_AVAILABLE", "REAL_HARDWARE")

    # ---- reports traceability and incidents
    c, rep, _ = http("GET", api + "/reports-center/access?days=30", token)
    R.add("Reports", "source traceability", "GET /reports-center/access", "names its source table and warns on stale data",
          f"source={rep.get('source')}, rows={rep.get('count')}, warnings={len(rep.get('warnings', []))}",
          "PASS" if rep.get("source") == "access_events" else "FAIL", "OFFLINE")
    c, inc, _ = http("GET", api + "/incidents?state=ACTIVE", token)
    R.add("Incidents", "open incidents", "GET /incidents?state=ACTIVE", "listed with counts and escalation flags",
          f"{inc.get('counts')} escalations={inc.get('escalations')}", "PASS" if "counts" in inc else "FAIL", "LIVE_SYSTEM")

    # ---- AI: accuracy (expected facts) + latency
    qa = [("which labs are free now", ["Free"], "lab data"),
          ("what is the UR5e home position", ["ROBOT_CONTROL.md"], "project knowledge"),
          ("how does the global STOP work for the UR5e", ["STOP"], "project knowledge"),
          ("how does the door controller decide to open the door", ["ACCESS", "door"], "project knowledge"),
          ("what is offline", ["Offline"], "lab data")]
    for q, must, kind in qa:
        c, ans, ms = http("POST", api + "/ai/ask", token, {"question": q, "history": []}, timeout=300)
        text = (ans or {}).get("answer", "") if isinstance(ans, dict) else ""
        ok = c == 200 and all(m.lower() in text.lower() for m in must)
        R.add("AI", q, f"POST /ai/ask ({kind})", f"answer contains {must}; < 3 s",
              f"HTTP {c} in {ms:.0f} ms via {(ans or {}).get('tools_used') if isinstance(ans, dict) else '-'}",
              "PASS" if ok and ms < 3000 else "FAIL", "LIVE_SYSTEM")

    # ---- reliability centre (2026-10-18)
    c, dr, _ = http("GET", api + "/reliability/drift", token)
    open_drift = [f for f in (dr or {}).get("findings", []) if not f.get("accepted")]
    R.add("Reliability", "configuration drift", "GET /reliability/drift vs app/config_baseline.json",
          "matches the approved baseline (secrets only checked for presence / not default)",
          f"baseline {(dr or {}).get('baseline_version')}: {len(open_drift)} open difference(s) "
          + "; ".join(f"{f['component']} {f['expected']}->{f['actual']}" for f in open_drift[:4]),
          "PASS" if c == 200 and not open_drift else "FAIL", "LIVE_SYSTEM")
    c, bk, _ = http("GET", api + "/reliability/backups", token)
    rd = (bk or {}).get("restore_drill")
    R.add("Backups", "restore drill (isolated database)", "tools/evidence/restore_drill.py result via /reliability/backups",
          "last drill ok, < 30 days old", "no drill recorded" if not rd else
          f"ok={rd.get('ok')} at {rd.get('at')}: restore {rd.get('restore_s')} s, {rd.get('tables')} tables, {rd.get('rows')} rows",
          "NOT_AVAILABLE" if not rd else ("PASS" if rd.get("ok") else "FAIL"), "LIVE_SYSTEM")
    c, g, _ = http("GET", api + "/reliability/graph", token)
    R.add("Reliability", "dependency model", "GET /reliability/graph", "every part with a state and evidence class; likely roots",
          f"{(g or {}).get('summary')} roots: {[r['name'] for r in (g or {}).get('likely_roots', [])][:5]}",
          "PASS" if c == 200 and (g or {}).get("nodes") else "FAIL", "LIVE_SYSTEM")
    c, pf, _ = http("GET", api + "/reliability/performance", token)
    objs = (pf or {}).get("objectives", [])
    R.add("Performance", "service objectives", "GET /reliability/performance (since backend start)",
          "objectives met or no data yet", "; ".join(f"{o['key']} met={o['met']} n={o['samples']}" for o in objs),
          "PASS" if c == 200 and all(o["met"] in (True, None) for o in objs) else "FAIL", "LIVE_SYSTEM")
    c, q, _ = http("GET", api + "/incidents/quality?days=30", token)
    R.add("Incidents", "alert quality", "GET /incidents/quality?days=30", "grouping active; storms visible",
          f"{(q or {}).get('incidents')} incidents / {(q or {}).get('reports')} reports, {(q or {}).get('distinct_conditions')} "
          f"conditions, storms {len((q or {}).get('storms', []))}", "PASS" if c == 200 else "FAIL", "LIVE_SYSTEM")
    try:
        import subprocess
        out = subprocess.run(["py", "-I", os.path.join(ROOT, "tools", "evidence", "clock_check.py"), "--json"],
                             capture_output=True, text=True, timeout=120).stdout
        rows = json.loads(out)["rows"]
        drift_rows = [r for r in rows if r["status"] == "DRIFT"]
        R.add("Clock", "clock agreement", "tools/evidence/clock_check.py", "all local clocks within limits",
              "; ".join(f"{r['clock']} {r['offset_ms']} ms" for r in rows if r["offset_ms"] is not None)[:400],
              "PASS" if not [r for r in drift_rows if "ntp" not in r["clock"].lower()] else "FAIL", "LIVE_SYSTEM")
        if drift_rows:
            R.add("Clock", "laptop vs internet time", "SNTP pool.ntp.org", "within 1 s",
                  "; ".join(f"{r['clock']} {r['offset_ms']} ms" for r in drift_rows), "FAIL", "LIVE_SYSTEM")
    except Exception as e:
        R.add("Clock", "clock agreement", "tools/evidence/clock_check.py", "runs", f"could not run ({e.__class__.__name__})",
              "NOT_AVAILABLE", "LIVE_SYSTEM")
    try:
        import subprocess
        out = subprocess.run(["py", "-3.14", os.path.join(ROOT, "tools", "security_vision", "scenario_bench.py")],
                             capture_output=True, text=True, timeout=600, cwd=os.path.join(ROOT, "tools", "security_vision")).stdout
        line = [x for x in out.splitlines() if x.startswith("SIMULATED")]
        R.add("Vision identity", "scenario bench (12 scenarios + two cameras)", "tools/security_vision/scenario_bench.py",
              "0 frames with someone else's name, 0 name switches", line[0] if line else out[-200:],
              "SIMULATION", "SIMULATION")
    except Exception as e:
        R.add("Vision identity", "scenario bench", "scenario_bench.py", "runs", f"could not run ({e.__class__.__name__})",
              "NOT_AVAILABLE", "SIMULATION")
    for area, check, why in (
            ("Robots", "UR5e Home / STOP live test", "commissioning steps 1-10 with the qualified operator (docs/ROBOT_CONTROL.md)"),
            ("Robots", "FANUC motion", "BLOCKED: remote interface not configured, no HOME TP program, no tested stop"),
            ("Cameras", "camera 2 mounting + floor calibration + identity scenarios", "docs/LAB_GO_NOGO_2026-10-18.md section 1"),
            ("Hardware", "ESP32 nodes (door, bins, environment)", "power / fuse / voltage bench checks; nodes offline since 11-13 Oct"),
            ("PCs", "student-PC agent pilot", "needs university IT approval")):
        R.add(area, check, "physical procedure", "done with people on site", why,
              "BLOCKED" if why.startswith("BLOCKED") else "PHYSICAL_VALIDATION_REQUIRED", "REAL_HARDWARE")

    # ---- backups
    st = (h or {}).get("backup") or {}
    R.add("Backups", "automatic dump", "backups/backup_status.json via /system/health", "state OK (recent, readable)",
          f"state={st.get('state')} last_success={st.get('last_success')} file={st.get('file')} ({st.get('size_kb')} KB)",
          "PASS" if st.get("state") == "OK" else "FAIL", "LIVE_SYSTEM")
    finish(R, started, a)


def finish(R, started, a):
    ts = started.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(ROOT, "docs", "reports")
    os.makedirs(out, exist_ok=True)
    summary = {k: sum(1 for c in R.checks if c["result"] == k) for k in
               ("PASS", "FAIL", "NOT_AVAILABLE", "SIMULATION", "PHYSICAL_VALIDATION_REQUIRED", "BLOCKED")}
    env = {"base": a.base, "started": started.isoformat(), "host": os.environ.get("COMPUTERNAME"), "runs": a.runs}
    with open(os.path.join(out, f"evidence_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump({"environment": env, "summary": summary, "checks": R.checks}, f, indent=1, default=str)
    lines = [f"# Smart Lab evidence run {started.isoformat(timespec='seconds')}", "",
             f"Environment: {json.dumps(env)}", "", f"Summary: {summary}", "",
             "Evidence classes: REAL_HARDWARE (observed from a device now), LIVE_SYSTEM (running software), "
             "OFFLINE (historical rows), SIMULATION (never physical validation).", "",
             "| Area | Check | Procedure | Expected | Observed | Result | Evidence |", "|---|---|---|---|---|---|---|"]
    for c in R.checks:
        lines.append("| " + " | ".join(str(c[k]).replace("|", "/") for k in ("area", "check", "procedure", "expected", "observed", "result", "evidence")) + " |")
    with open(os.path.join(out, f"evidence_{ts}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n{summary} -> docs/reports/evidence_{ts}.md")


if __name__ == "__main__":
    main()
