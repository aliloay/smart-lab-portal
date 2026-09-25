"""
Smoke test for the Docker Compose stack, from the outside - the way a phone
and the ESP32 master reach it:

  port 80    the portal (nginx): the app, /api and the /ws live stream
  port 8000  the API directly, as the master calls it

    docker compose up -d --build
    python scripts/compose_smoke.py [host]        (default: localhost)

Standard library only. It WRITES to the stack's database: one booking for
the seeded student (cancelled again at the end) and one issue with a photo.
Run it against a fresh or throwaway stack, not a database you are keeping.
"""
import json
import os
import random
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
WEB = f"http://{HOST}"
API = f"http://{HOST}:8000/api"
DEVICE_KEY = os.environ.get("DEVICE_API_KEY", "dev-device-key-change-me")

failures = 0


def check(label, ok, detail=""):
    global failures
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        failures += 1


def call(method, url, body=None, headers=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def noise_png(w=900, h=800):
    """~2 MB of incompressible pixels: bigger than nginx's 1 MB default."""
    def chunk(t, d):
        c = struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        return struct.pack(">I", len(d)) + t + d + c
    rows = b"".join(b"\x00" + random.randbytes(w * 3) for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 1)) + chunk(b"IEND", b""))


def wait_until_up(seconds=180):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if call("GET", f"{WEB}/api/health")[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(3)
    return False


print(f"\nSmart Lab stack at {HOST}\n")
check("stack answers within 3 minutes", wait_until_up())

# --- the portal, as a phone opens it -------------------------------------
s, page = call("GET", f"{WEB}/")
check("portal page served on port 80", s == 200 and 'id="root"' in page, f"HTTP {s}")
s, page = call("GET", f"{WEB}/labs/1")
check("app routes load directly (no 404 on refresh)", s == 200 and 'id="root"' in page, f"HTTP {s}")
s, body = call("GET", f"{WEB}/api/health")
check("API reachable through the portal, database connected",
      s == 200 and json.loads(body).get("database") is True, body[:120])

s, body = call("POST", f"{WEB}/api/auth/login",
               {"email": "ali@giu-uni.de", "password": "Student#2026"})
check("seeded student can sign in", s == 200, f"HTTP {s} {body[:120]}")
token = json.loads(body)["access_token"] if s == 200 else ""
auth = {"Authorization": f"Bearer {token}"}

s, body = call("GET", f"{WEB}/api/labs", headers=auth)
labs = json.loads(body) if s == 200 else []
lab = next((l for l in labs if l["code"] == "LAB_01"), None)
check("11 laboratories seeded", len(labs) == 11, f"got {len(labs)}")
check("LAB_01 is marked as having the door hardware", bool(lab and lab["has_controller"]))

# --- the live stream through nginx ----------------------------------------
try:
    with socket.create_connection((HOST, 80), timeout=10) as sock:
        sock.sendall((f"GET /ws/activity?token={token} HTTP/1.1\r\nHost: {HOST}\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\n"
                      "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n").encode())
        first = sock.recv(200).decode("latin-1").split("\r\n")[0]
except OSError as e:
    first = str(e)
check("live updates (WebSocket) upgrade through the portal", " 101 " in first, first)

# --- booking -> QR -> the master's validation on port 8000 ----------------
booking_id = None
if lab:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    s, body = call("POST", f"{WEB}/api/bookings", {
        "lab_id": lab["id"], "start_time": now.isoformat(),
        "end_time": (now + timedelta(minutes=50)).isoformat(),
        "reason": "Docker smoke test"}, auth)
    check("booking created", s == 201, f"HTTP {s} {body[:160]}")
    if s == 201:
        booking_id = json.loads(body)["id"]
        s, body = call("GET", f"{WEB}/api/bookings/{booking_id}/qr", headers=auth)
        qr = json.loads(body).get("token", "") if s == 200 else ""
        check("booking QR issued", qr.startswith("SLB:"), f"HTTP {s}")

        s, body = call("GET", f"{API}/health")
        check("API answers on port 8000 (the ESP32 path)", s == 200, f"HTTP {s}")
        req = {"lab_id": "LAB_01", "qr_token": qr, "device_uid": "MASTER_LAB01"}
        s, body = call("POST", f"{API}/access/validate-qr", req, {"X-Device-Key": DEVICE_KEY})
        res = json.loads(body) if s == 200 else {}
        check("master's QR validation returns the student's identity",
              res.get("valid") is True and res.get("auth_subject") == "USER1", body[:160])
        s, _ = call("POST", f"{API}/access/validate-qr", req)
        check("device API refuses a request without the device key", s == 401, f"HTTP {s}")

# --- an issue with a phone-sized photo through nginx ----------------------
if lab:
    s, body = call("POST", f"{WEB}/api/issues", {
        "lab_id": lab["id"], "category": "OTHER", "severity": "LOW",
        "title": "Docker smoke test", "description": "Automated check of the upload path."}, auth)
    check("issue reported", s == 201, f"HTTP {s} {body[:160]}")
    if s == 201:
        issue_id = json.loads(body)["id"]
        png = noise_png()
        boundary = "----smartlabsmoke"
        form = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                f"filename=\"photo.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + png + \
               f"\r\n--{boundary}--\r\n".encode()
        s, body = call("POST", f"{WEB}/api/issues/{issue_id}/photos", headers=auth, raw=form,
                       ctype=f"multipart/form-data; boundary={boundary}")
        check(f"{len(png) / 1e6:.1f} MB photo uploads through the portal", s == 201, f"HTTP {s} {body[:160]}")

if booking_id:
    call("POST", f"{WEB}/api/bookings/{booking_id}/cancel", headers=auth)

print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed.'}\n")
sys.exit(1 if failures else 0)
