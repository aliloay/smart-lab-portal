"""
Concurrent-session ramp (2026-10-27, owner: "how many could enter the portal at once"). ISOLATED: the backend copy on
127.0.0.1:8100 (DB smartlab_perf_test), never the live portal. Read-only browsing - no bookings, no device commands.

Each simulated user = one signed-in session (admin / staff / student, 1:2:5) that opens pages the way the portal does:
the page's own first reads (the same lists as frontend/src/lib/warm.ts) in parallel like a browser (6 at a time), then
a think time of 2-6 s, then the next page; plus the 30 s background polls (unread count, summary).
Levels run one after another (default 1 5 10 20 30 50 75 100), LEVEL_S seconds each; a level is "stable" when
errors < 1 % and page p95 < 2 s. Stops early when a level is not stable or the backend container passes 90 % RAM.
Per level: sessions, page loads, requests, errors, page / request p50 p95 p99, backend + db CPU and RAM.

    set E2E_ADMIN_PW=... & set E2E_PW=...   (perf-admin / perf-staff / perf-student)
    py tools/perf/session_ramp.py [levels...]      -> docs/perf/session_ramp_<time>.json
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import random
import statistics
import subprocess
import sys
import threading
import time

import requests

BASE = os.environ.get("RAMP_BASE", "http://127.0.0.1:8100/api")
LEVEL_S = float(os.environ.get("LEVEL_S", "45"))
LEVELS = [int(x) for x in sys.argv[1:]] or [1, 5, 10, 20, 30, 50, 75, 100]
PAGES = {
    "admin": {"/": ["/access-events?limit=30&security_only=true", "/issues/summary", "/issues?active=true&limit=50",
                    "/access-events?limit=40", "/devices", "/summary", "/labs/overview", "/alerts?open_only=true",
                    "/reports/access?days=7"],
              "labs": ["/labs", "/labs/overview"], "access": ["/labs", "/users", "/access-events?limit=400"],
              "bookings": ["/bookings"], "devices": ["/devices", "/labs"], "alerts": ["/alerts?open_only=false"],
              "command": ["/robots", "/monitor", "/security/cameras", "/system/services", "/alerts?open_only=true",
                          "/access-events?limit=40", "/security/events?limit=30", "/labs/environment/all"],
              "system": ["/system/health", "/analytics/anomalies", "/analytics/system?days=30"],
              "operations": ["/analytics/trends?weeks=5", "/analytics/operations?days=30", "/labs"],
              "equipment": ["/labs/environment/all", "/labs/1/environment"], "reliability": ["/reliability/briefing"],
              "ai": ["/ai/status"]},
    "staff": {"/": ["/issues/summary", "/issues?active=true&limit=50", "/access-events?limit=40", "/devices", "/summary",
                    "/labs/overview"], "labs": ["/labs", "/labs/overview"], "bookings": ["/bookings"],
              "devices": ["/devices", "/labs"], "issues": ["/issues?limit=500&active=true", "/issues/summary", "/labs"],
              "command": ["/robots", "/monitor", "/security/cameras", "/alerts?open_only=true", "/labs/environment/all"],
              "equipment": ["/labs/environment/all", "/labs/1/environment"]},
    "student": {"/": ["/analytics/me?days=90", "/ai/student/status", "/bookings", "/labs/overview",
                      "/access-events?limit=8", "/issues?limit=20"], "labs": ["/labs", "/labs/overview"],
                "book": ["/labs"], "bookings": ["/bookings"], "robots": ["/robots"], "issues": ["/issues?limit=200"],
                "notifications": ["/notifications/inbox?tab=all&offset=0&limit=50"]},
}
ACCOUNTS = {"admin": ("perf-admin@giu-uni.de", os.environ.get("E2E_ADMIN_PW")),
            "staff": ("perf-staff@giu-uni.de", os.environ.get("E2E_PW")),
            "student": ("perf-student@giu-uni.de", os.environ.get("E2E_PW"))}


def login(role: str) -> requests.Session:
    s = requests.Session()
    email, pw = ACCOUNTS[role]
    t0 = time.perf_counter()
    r = s.post(BASE + "/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    s.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    s.login_ms = (time.perf_counter() - t0) * 1000
    return s


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.req, self.page, self.codes, self.errors, self.logins, self.by = [], [], {}, 0, [], {}

    def add_req(self, ms, code, path=""):
        with self.lock:
            self.req.append(ms)
            self.by.setdefault(path.split("?")[0], []).append(ms)
            self.codes[code] = self.codes.get(code, 0) + 1
            if code == 0 or code >= 500:
                self.errors += 1


def user(role: str, stop: float, st: Stats, pool: cf.ThreadPoolExecutor):
    try:
        s = login(role)
        st.logins.append(s.login_ms)
    except Exception:                                       # noqa: BLE001
        st.add_req(0, 0)
        return
    pages = PAGES[role]
    names = list(pages)
    last_poll = 0.0
    while time.time() < stop:
        name = random.choice(names)
        t0 = time.perf_counter()

        def get(path):
            a = time.perf_counter()
            try:
                code = s.get(BASE + path, timeout=15).status_code
            except requests.RequestException:
                code = 0
            st.add_req((time.perf_counter() - a) * 1000, code, path)
        list(pool.map(get, pages[name]))                    # a page's first reads, in parallel like a browser
        with st.lock:
            st.page.append((time.perf_counter() - t0) * 1000)
        if time.time() - last_poll > 30:
            for p in ("/notifications/unread-count", "/summary"):
                get(p)
            last_poll = time.time()
        time.sleep(random.uniform(2, 6))


def docker_stats() -> dict:
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:                                       # noqa: BLE001
        return {}
    res = {}
    for line in out.splitlines():
        n, c, m = line.split("|")
        if "loadtest" in n or n.endswith("db-1"):
            res[n] = {"cpu": float(c.rstrip("%")), "mem": float(m.rstrip("%"))}
    return res


def pct(a, p):
    if not a:
        return None
    s = sorted(a)
    return round(s[min(len(s) - 1, int(p * len(s)))], 1)


def main():
    results = []
    for n in LEVELS:
        st = Stats()
        roles = [("admin", "staff", "staff", "student", "student", "student", "student", "student")[i % 8] for i in range(n)]
        stop = time.time() + LEVEL_S
        samples = []
        with cf.ThreadPoolExecutor(max_workers=max(6, n * 6)) as reqpool, cf.ThreadPoolExecutor(max_workers=n) as users:
            futs = [users.submit(user, r, stop, st, reqpool) for r in roles]
            while time.time() < stop:
                samples.append(docker_stats())
                time.sleep(5)
            cf.wait(futs)
        total = sum(st.codes.values())
        cpu = {k: round(statistics.mean(s[k]["cpu"] for s in samples if k in s), 1) for k in (samples[0] if samples else {})}
        mem = {k: max(s[k]["mem"] for s in samples if k in s) for k in (samples[0] if samples else {})}
        row = {"sessions": n, "seconds": LEVEL_S, "logins_ok": len(st.logins), "login_p95_ms": pct(st.logins, .95),
               "page_loads": len(st.page), "requests": total, "errors": st.errors,
               "error_rate": round(st.errors / total, 4) if total else None, "codes": st.codes,
               "page_ms": {"p50": pct(st.page, .5), "p95": pct(st.page, .95), "p99": pct(st.page, .99)},
               "req_ms": {"p50": pct(st.req, .5), "p95": pct(st.req, .95), "p99": pct(st.req, .99)},
               "req_per_s": round(total / LEVEL_S, 1), "cpu_mean_pct": cpu, "mem_max_pct": mem}
        row["slowest_endpoints"] = sorted(((k, pct(v, .95), len(v)) for k, v in st.by.items()), key=lambda x: -(x[1] or 0))[:8]
        row["stable"] = bool(total) and row["error_rate"] < 0.01 and (row["page_ms"]["p95"] or 0) < 2000
        results.append(row)
        print(f"{n:4d} sessions | logins {row['logins_ok']}/{n} | pages {row['page_loads']:5d} | req {total:6d} "
              f"({row['req_per_s']}/s) | err {st.errors} | page p50/p95/p99 {row['page_ms']['p50']}/{row['page_ms']['p95']}/"
              f"{row['page_ms']['p99']} ms | req p95 {row['req_ms']['p95']} ms | cpu {cpu} | "
              f"{'STABLE' if row['stable'] else 'NOT STABLE'}", flush=True)
        print("      slowest p95:", ", ".join(f"{k} {v} ms" for k, v, _ in row["slowest_endpoints"][:6]), flush=True)
        if not row["stable"] or any(v > 90 for v in mem.values()):
            break
        time.sleep(5)
    os.makedirs("docs/perf", exist_ok=True)
    out = f"docs/perf/session_ramp_{time.strftime('%Y%m%d-%H%M')}.json"
    json.dump({"base": BASE, "levels": results}, open(out, "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
