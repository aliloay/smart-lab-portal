"""
PC fleet + screen-sharing load - SIMULATED, ISOLATED (2026-10-21). Runs next to load_simlab.py against
the isolated backend copy (default http://127.0.0.1:8100, DB *_test - docs/perf/LOAD_TEST.md), never the
live portal. For DURATION seconds:
  * N simulated PC agents (SIMPC_01..): a state report every 30 s (staggered), a poll every 1 s
  * the LAN presence collector: one report for all N every 2 s
  * an admin presenting from a browser: a 60 KB JPEG frame every 0.5 s
  * N students watching /share: frame.jpg every 0.5 s + status every 1.5 s
  * every 20 s: Stop, then Start again - time until a viewer gets 410 / the next picture
Prints p50 / p95 / max latency per request kind, errors, and the stop / restart timings.
    py tools/perf/pc_fleet_sim.py [seconds] [base] [pcs]
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import threading
import time

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
BASE = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8100").rstrip("/")
N = int(sys.argv[3]) if len(sys.argv) > 3 else 11
API = BASE + "/api"
if "8000" in BASE or BASE.endswith(":80") or BASE == "http://localhost":
    sys.exit("refusing: this test must not run against the live portal")
KEY = [l.split("=", 1)[1].strip().strip('"') for l in open(os.path.join(ROOT, ".env"), encoding="utf-8")
       if l.startswith("DEVICE_API_KEY=")][0]
EMAIL, PASSWORD = os.environ.get("E2E_EMAIL"), os.environ.get("E2E_PASSWORD")
STUDENT_EMAIL = os.environ.get("E2E_STUDENT_EMAIL", "ali@giu-uni.de")
STUDENT_PASSWORD = os.environ.get("E2E_STUDENT_PASSWORD")
DEV = {"X-Device-Key": KEY}
JPEG = b"\xff\xd8\xff\xe0" + os.urandom(60_000)
lat: dict[str, list[float]] = {}
errors: dict[str, int] = {}
events: list[dict] = []
lock = threading.Lock()
end = time.monotonic() + DUR


def rec(kind: str, fn):
    t = time.perf_counter()
    try:
        r = fn()
        ok = r.status_code < 500
    except requests.RequestException:
        r, ok = None, False
    with lock:
        lat.setdefault(kind, []).append((time.perf_counter() - t) * 1000)
        if not ok:
            errors[kind] = errors.get(kind, 0) + 1
    return r


def token(email: str, pw: str) -> str:
    r = requests.post(API + "/auth/login", json={"email": email, "password": pw}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def agent(i: int) -> None:
    uid = f"SIMPC_{i:02d}"
    s = requests.Session()
    s.headers.update(DEV)
    time.sleep(i * 30 / N)                                   # staggered like real PCs
    last = 0.0
    while time.monotonic() < end:
        if time.monotonic() - last >= 30:
            last = time.monotonic()
            rec("agent state (30 s)", lambda: s.post(API + "/equipment/state", timeout=10, json={
                "device_uid": uid, "lab_id": "LAB_01", "kind": "PC", "state": "RUNNING",
                "detail": {"os_user": f"student{i}", "agent_started": 1.0, "boot_time": 1, "ips": [f"10.9.0.{i}"],
                           "macs": [f"02-00-00-00-00-{i:02x}"]}}))
        rec("agent poll (1 s)", lambda: s.get(API + "/equipment/pc/poll", params={"device_uid": uid}, timeout=10))
        time.sleep(1.0)


def presence() -> None:
    s = requests.Session()
    s.headers.update(DEV)
    while time.monotonic() < end:
        rec("LAN presence (2 s)", lambda: s.post(API + "/equipment/pc/presence", timeout=10, json={
            "lab_id": "LAB_01", "pcs": [{"device_uid": f"SIMPC_{i:02d}", "present": True, "via": "ping",
                                         "ip": f"10.9.0.{i}", "mac": f"02-00-00-00-00-{i:02x}"} for i in range(1, N + 1)]}))
        time.sleep(2.0)


def presenter(admin: str) -> None:
    s = requests.Session()
    s.headers.update({"Authorization": "Bearer " + admin})
    while time.monotonic() < end:
        r = rec("share frame upload (0.5 s)", lambda: s.post(API + "/equipment/broadcast/frame", data=JPEG,
                                                             headers={"Content-Type": "image/jpeg"}, timeout=10))
        if r is not None and r.status_code == 409:              # stopped: the cycle thread restarts it
            time.sleep(0.2)
            continue
        time.sleep(0.5)


def viewer(student: str, idx: int) -> None:
    s = requests.Session()
    s.headers.update({"Authorization": "Bearer " + student})
    last_status = 0.0
    while time.monotonic() < end:
        rec("viewer frame.jpg (0.5 s)", lambda: s.get(API + "/equipment/broadcast/frame.jpg", timeout=10))
        if time.monotonic() - last_status > 1.5:
            last_status = time.monotonic()
            rec("viewer status (1.5 s)", lambda: s.get(API + "/equipment/broadcast/status", timeout=10))
        time.sleep(0.5)


def cycle(admin: str, student: str) -> None:
    """Stop / start every 20 s: how fast does a viewer see it?"""
    a = {"Authorization": "Bearer " + admin}
    st = {"Authorization": "Bearer " + student}
    time.sleep(10)
    while time.monotonic() < end - 15:
        t = time.perf_counter()
        requests.post(API + "/equipment/broadcast/stop", headers=a, timeout=10)
        while requests.get(API + "/equipment/broadcast/frame.jpg", headers=st, timeout=10).status_code != 410:
            pass
        stop_ms = (time.perf_counter() - t) * 1000
        late = requests.post(API + "/equipment/broadcast/frame", headers={**a, "Content-Type": "image/jpeg"},
                             data=JPEG, timeout=10).status_code
        t = time.perf_counter()
        requests.post(API + "/equipment/broadcast/start", headers=a, json={"source": "browser"}, timeout=10)
        while requests.get(API + "/equipment/broadcast/frame.jpg", headers=st, timeout=10).status_code != 200:
            time.sleep(0.05)
        events.append({"stop_to_410_ms": round(stop_ms, 1), "late_frame_after_stop": late,
                       "start_to_picture_ms": round((time.perf_counter() - t) * 1000, 1)})
        time.sleep(20)


def main() -> None:
    if not (EMAIL and PASSWORD):
        sys.exit("set E2E_EMAIL / E2E_PASSWORD (seeded demo admin of the TEST database)")
    admin = token(EMAIL, PASSWORD)
    student = token(STUDENT_EMAIL, STUDENT_PASSWORD or PASSWORD)
    requests.post(API + "/equipment/broadcast/start", headers={"Authorization": "Bearer " + admin},
                  json={"source": "browser", "title": "load test"}, timeout=10)
    th = [threading.Thread(target=agent, args=(i,)) for i in range(1, N + 1)]
    th += [threading.Thread(target=presence), threading.Thread(target=presenter, args=(admin,)),
           threading.Thread(target=cycle, args=(admin, student))]
    th += [threading.Thread(target=viewer, args=(student, i)) for i in range(N)]
    for t in th:
        t.daemon = True
        t.start()
    while time.monotonic() < end:
        time.sleep(1)
    requests.post(API + "/equipment/broadcast/stop", headers={"Authorization": "Bearer " + admin}, timeout=10)
    out = {"seconds": DUR, "pcs": N, "viewers": N, "errors": errors, "stop_start_cycles": events, "latency_ms": {}}
    for k, v in sorted(lat.items()):
        v = sorted(v)
        out["latency_ms"][k] = {"n": len(v), "p50": round(statistics.median(v), 1),
                                "p95": round(v[int(0.95 * (len(v) - 1))], 1), "max": round(v[-1], 1)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
