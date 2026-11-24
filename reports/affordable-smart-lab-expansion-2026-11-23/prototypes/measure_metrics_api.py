"""Reusable diagnostic: times the read-only metrics endpoints. Standard library; GET requests only (plus one sign-in).
  set E2E_EMAIL, E2E_PASSWORD;  python measure_metrics_api.py http://127.0.0.1:8100 [runs]
The endpoints are cached for 20-60 s, so each uncached number is the first call after a pause."""
import json, os, statistics, sys, time, urllib.request

BASE, N = sys.argv[1].rstrip("/"), int(sys.argv[2]) if len(sys.argv) > 2 else 3


def call(path, data=None, token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {"Content-Type": "application/json"}
    t = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers=h), timeout=60) as r:
        body = r.read()
    return (time.perf_counter() - t) * 1000, body


_, b = call("/api/auth/login", json.dumps({"email": os.environ["E2E_EMAIL"], "password": os.environ["E2E_PASSWORD"]}).encode())
tok = json.loads(b)["access_token"]
latest = json.loads(call("/api/metrics/latest", token=tok)[1])
dev = next(r["device_id"] for r in latest if r["metric_name"] == "temperature")
time.sleep(21)
for p in ["/api/system/health", "/api/metrics/latest", f"/api/metrics/history?device_id={dev}&metric=temperature&period=24h",
          f"/api/metrics/history?device_id={dev}&metric=temperature&period=90d", "/api/metrics/coverage?days=30",
          f"/api/metrics/diagnose/{dev}", "/api/metrics/timeline?hours=168"]:
    first = []
    for i in range(N):
        first.append(call(p, token=tok)[0])
        again, body = call(p, token=tok)
        if i < N - 1 and "/metrics/" in p and "diagnose" not in p and "timeline" not in p:
            time.sleep(61 if "coverage" in p else 21)
    print(f"{p.split('device_id')[0]:34} first call median {statistics.median(first):7.1f} ms   repeat {again:6.1f} ms   {len(body) / 1024:6.1f} kB")
