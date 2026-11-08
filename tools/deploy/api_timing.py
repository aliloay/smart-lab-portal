"""Read-only API latency probe: logs in once, then times GET endpoints N times each (p50 / p95 / max, ms).
Usage: E2E_PASSWORD=... py -I tools/deploy/api_timing.py [base] [runs] [path ...]
The password is read from the environment and never printed."""
import json
import os
import ssl
import statistics
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://localhost"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
PATHS = sys.argv[3:] or ["/api/emergency/status", "/api/system/status", "/api/access-events?limit=400",
                         "/api/analytics/operations?days=30", "/api/analytics/anomalies", "/api/bookings",
                         "/api/security/events?limit=30", "/api/alerts?open_only=true", "/api/monitor",
                         "/api/analytics/system?days=30", "/api/issues?limit=500&active=true", "/api/robots",
                         "/api/devices", "/api/health"]
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE   # the portal's local self-signed certificate


def call(path, token=None, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.status, r.read()


def login():
    for path in ("/api/auth/login", "/api/auth/token"):
        try:
            _, raw = call(path, body={"email": os.environ.get("E2E_EMAIL", "admin@giu-uni.de"),
                                      "password": os.environ["E2E_PASSWORD"]})
            d = json.loads(raw)
            return d.get("access_token") or d.get("token")
        except Exception:
            continue
    raise SystemExit("login failed")


token = login()
print(f"{'endpoint':55s} {'p50':>7s} {'p95':>7s} {'max':>7s}  status")
for path in PATHS:
    times, status = [], None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        try:
            status, _ = call(path, token)
        except urllib.error.HTTPError as e:
            status = e.code
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[min(len(times) - 1, int(0.95 * len(times)))]
    print(f"{path[:55]:55s} {statistics.median(times):7.0f} {p95:7.0f} {times[-1]:7.0f}  {status}")
