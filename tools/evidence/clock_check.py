"""
Clock check - READ-ONLY (2026-10-18). Every timestamp in the portal is only as good as the clock that
made it. This measures each clock against THIS laptop's clock (the reference all local services share)
and, when the internet is reachable, the laptop against an NTP server.

    py -I tools/evidence/clock_check.py [--json]

What has a clock of its own, and how it is checked:
  laptop          SNTP to pool.ntp.org (UDP 123, one query) - skipped without internet (lab network)
  backend, db,    inside Docker (WSL2 VM - its clock can lag after the laptop sleeps): read with
  n8n             docker exec, offset = their time - midpoint of the call
  camera services /health "time" (new code) or the HTTP Date header (1 s resolution)
  face / AI /     HTTP Date header (1 s resolution)
  knowledge
  lab PCs         the PC agent reports its own time; the portal stores the difference (clock_offset_s)
No own clock (timestamped by the server on arrival): ESP32 nodes (no NTP in any firmware), the UR5e
collector (RTDE time is controller uptime - stamped with the laptop clock), the FANUC page (no time).
Nothing is changed anywhere.
"""
from __future__ import annotations

import email.utils
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOCAL_OK_MS = 500          # services on this laptop / in its Docker VM
DEVICE_OK_MS = 2000        # other computers on the lab network


def sntp(host="pool.ntp.org", timeout=2.0):
    """Offset of this laptop's clock vs an NTP server (ms; + = the laptop is ahead)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t0 = time.time()
        s.sendto(b"\x1b" + 47 * b"\0", (host, 123))
        data, _ = s.recvfrom(48)
        t3 = time.time()
    finally:
        s.close()
    secs, frac = struct.unpack("!II", data[40:48])
    server = secs - 2208988800 + frac / 2 ** 32
    return round(((t0 + t3) / 2 - server) * 1000, 1), round((t3 - t0) * 1000, 1)


def docker_time(service, cmd):
    t0 = time.time()
    out = subprocess.run(["docker", "compose", "exec", "-T", service] + cmd, cwd=REPO,
                         capture_output=True, text=True, timeout=20).stdout.strip()
    t1 = time.time()
    return round((float(out.splitlines()[-1]) - (t0 + t1) / 2) * 1000, 1), round((t1 - t0) * 1000)


def http_time(url, headers=None):
    import urllib.error
    t0 = time.time()
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            body = r.read()
            date = r.headers.get("Date")
    except urllib.error.HTTPError as e:           # 401/404 still carry the server's Date
        body, date = b"", e.headers.get("Date")
    t1 = time.time()
    mid = (t0 + t1) / 2
    try:
        j = json.loads(body)
        if isinstance(j, dict) and isinstance(j.get("time"), (int, float)):
            return round((j["time"] - mid) * 1000, 1), "service time"
        if isinstance(j, dict) and isinstance(j.get("time"), str):     # backend: ISO with microseconds
            from datetime import datetime
            return round((datetime.fromisoformat(j["time"]).timestamp() - mid) * 1000, 1), "service time"
    except ValueError:
        pass
    if date:                                       # whole seconds only
        return round((email.utils.parsedate_to_datetime(date).timestamp() - mid) * 1000, 0), "HTTP Date (1 s)"
    return None, "no time exposed"


def device_key():
    for line in open(os.path.join(REPO, ".env"), encoding="utf-8"):
        if line.startswith("DEVICE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main():
    rows = []

    def add(name, method, offset_ms, limit, note=""):
        if offset_ms is None:
            status = "UNAVAILABLE"
        else:
            status = "OK" if abs(offset_ms) <= limit else "DRIFT"
        rows.append({"clock": name, "method": method, "offset_ms": offset_ms, "limit_ms": limit,
                     "status": status, "note": note})

    try:
        off, rtt = sntp()
        add("laptop vs pool.ntp.org", "SNTP", off, 1000, f"round trip {rtt} ms")
    except OSError as e:
        add("laptop vs pool.ntp.org", "SNTP", None, 1000, f"no NTP answer ({e.__class__.__name__}) - lab network has no internet")
    # backend + database through /api/health (ms precision: "time" and the database's clock_timestamp())
    try:
        t0 = time.time()
        with urllib.request.urlopen("http://127.0.0.1/api/health", timeout=5) as r:
            j = json.loads(r.read())
        t1 = time.time()
        from datetime import datetime
        mid = (t0 + t1) / 2
        add("backend (Docker VM)", "/api/health time", round((datetime.fromisoformat(j["time"]).timestamp() - mid) * 1000, 1),
            LOCAL_OK_MS, f"call {round((t1 - t0) * 1000)} ms")
        add("database (Docker VM)", "clock_timestamp()", None if j.get("db_time") is None
            else round((j["db_time"] - mid) * 1000, 1), LOCAL_OK_MS, f"call {round((t1 - t0) * 1000)} ms")
    except Exception as e:
        add("backend / database", "/api/health", None, LOCAL_OK_MS, e.__class__.__name__)
    try:                                           # n8n: docker exec (error bar = the call time)
        off, ms = docker_time("n8n", ["node", "-e", "console.log(Date.now()/1000)"])
        add("n8n container", "docker exec", off, LOCAL_OK_MS + ms / 2, f"+-{ms // 2} ms (exec overhead)")
    except Exception as e:
        add("n8n container", "docker exec", None, LOCAL_OK_MS, e.__class__.__name__)
    key = {"X-Device-Key": device_key()}
    for name, url in (("camera 1 service (5100)", "http://127.0.0.1:5100/health"),
                      ("camera 2 service (5101)", "http://127.0.0.1:5101/health"),
                      ("face server (5000)", "http://127.0.0.1:5000/health"),
                      ("knowledge service (5199)", "http://127.0.0.1:5199/status"),
                      ("Ollama (11434)", "http://127.0.0.1:11434/api/version")):
        try:
            off, how = http_time(url, key)
            add(name, how, off, LOCAL_OK_MS if how == "service time" else 1500)
        except Exception as e:
            add(name, "HTTP", None, LOCAL_OK_MS, f"not reachable ({e.__class__.__name__})")
    try:
        q = ("select device_uid, (component_state->>'clock_offset_s')::float from devices "
             "where device_type='PC' and component_state->>'clock_offset_s' is not null")
        out = subprocess.run(["docker", "compose", "exec", "-T", "db", "psql", "-U", "smartlab", "-d", "smartlab",
                              "-tAc", q], cwd=REPO, capture_output=True, text=True, timeout=20).stdout.strip()
        for line in filter(None, out.splitlines()):
            uid, off = line.split("|")
            add(f"PC {uid}", "agent report (server - agent)", round(float(off) * 1000, 0), DEVICE_OK_MS,
                "includes network delay; + = the PC is behind")
    except Exception as e:
        add("lab PCs", "agent report", None, DEVICE_OK_MS, e.__class__.__name__)
    for name, note in (("ESP32 nodes", "no clock: no NTP in any firmware - the server timestamps on arrival"),
                       ("UR5e collector", "RTDE time is controller uptime - samples stamped with the laptop clock"),
                       ("FANUC monitor", "CURPOS.DG has no time - stamped with the laptop clock")):
        rows.append({"clock": name, "method": "-", "offset_ms": None, "limit_ms": None, "status": "NO OWN CLOCK", "note": note})
    if "--json" in sys.argv:
        print(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows}, indent=1))
        return 0
    print(f"Clock check {time.strftime('%Y-%m-%d %H:%M:%S')} (offsets vs this laptop; + = that clock is ahead)")
    for r in rows:
        off = "" if r["offset_ms"] is None else f"{r['offset_ms']:+.0f} ms"
        print(f"  {r['status']:<12} {r['clock']:<28} {off:>10}  {r['method']}  {r['note']}")
    return 1 if any(r["status"] == "DRIFT" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
