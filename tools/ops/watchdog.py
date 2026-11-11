"""
Smart Lab service watchdog - MONITOR ONLY (2026-11-11 closure mission).

    py tools/ops/watchdog.py --once          one snapshot as JSON; exit code 1 if a required service is down
    py tools/ops/watchdog.py                 every 15 s; writes a line to logs/watchdog.jsonl when a state CHANGES

What it does: asks each local service for its health page (or just its port) and records when one goes down
or comes back, with how long it was away. What it deliberately does NOT do: restart anything. A camera restart
is a gap in the recording of who is in the lab, launch.bat may rebuild the portal, and the door and the robots
are never this script's business. When something is down it says so and names the fix: run launch.bat, which
starts only what is missing.

Standard library only; nothing is sent anywhere but 127.0.0.1.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "logs", "watchdog.jsonl")

# name, port, health path (None = the port answering is enough), required for the portal to work
SERVICES = [
    ("portal (web)", 80, None, True),
    ("portal API", 8000, "/api/health", True),
    ("database", 5433, None, True),
    ("n8n automation", 5678, "/healthz", False),
    ("face server (door camera)", 5000, None, False),
    ("security camera 1", 5100, "/health", False),
    ("security camera 2", 5101, "/health", False),
    ("knowledge service", 5199, None, False),
    ("voice service", 5320, None, False),
    ("local AI (Ollama)", 11434, "/api/version", False),
    ("OPC UA feed", 4840, None, False),
]
DOWN_AFTER = 3                      # consecutive failed checks before a service counts as down (45 s)


def check(port: int, path: Optional[str], timeout: float = 2.0) -> tuple[bool, str]:
    """(up, detail). A health page must answer 2xx; without one the port must accept a connection."""
    if path is None:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout):
                return True, "port open"
        except OSError as e:
            return False, e.__class__.__name__
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
            return (200 <= r.status < 300), f"HTTP {r.status}"
    except Exception as e:                       # refused, timeout, HTTP error: all "not healthy"
        return False, e.__class__.__name__


def snapshot(services=SERVICES, probe=check) -> list[dict]:
    out = []
    for name, port, path, required in services:
        t = time.perf_counter()
        up, detail = probe(port, path)
        out.append({"service": name, "port": port, "up": up, "detail": detail, "required": required,
                    "ms": round((time.perf_counter() - t) * 1000)})
    return out


class Watch:
    """State changes only: a service is DOWN after DOWN_AFTER failed checks in a row, UP again at the first
    good one. Pure (the clock and the results are passed in), so it is tested without any service."""

    def __init__(self):
        self.fails: dict[str, int] = {}
        self.down_since: dict[str, float] = {}

    def update(self, snap: list[dict], now: float) -> list[dict]:
        events = []
        for s in snap:
            n = s["service"]
            if s["up"]:
                self.fails[n] = 0
                if n in self.down_since:
                    events.append({"event": "RECOVERED", "service": n, "port": s["port"],
                                   "down_s": round(now - self.down_since.pop(n))})
                continue
            self.fails[n] = self.fails.get(n, 0) + 1
            if self.fails[n] == DOWN_AFTER and n not in self.down_since:
                self.down_since[n] = now
                events.append({"event": "DOWN", "service": n, "port": s["port"], "detail": s["detail"],
                               "required": s["required"],
                               "fix": "run launch.bat - it starts only what is missing (this script restarts nothing)"})
        return events


def main() -> int:
    ap = argparse.ArgumentParser(description="Smart Lab service watchdog (monitor only)")
    ap.add_argument("--once", action="store_true", help="one snapshot as JSON, then exit")
    ap.add_argument("--every", type=float, default=15.0, help="seconds between checks (default 15)")
    a = ap.parse_args()
    if a.once:
        snap = snapshot()
        print(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "services": snap}, indent=1))
        return 1 if any(s["required"] and not s["up"] for s in snap) else 0
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    w = Watch()
    print(f"[watchdog] monitoring {len(SERVICES)} services every {a.every:.0f} s - changes go to {LOG}")
    while True:
        for e in w.update(snapshot(), time.time()):
            e["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[watchdog] {e['event']} {e['service']} (port {e['port']})")
            try:
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(e) + "\n")
            except OSError as err:               # a locked log never stops the watching
                print(f"[watchdog] could not write the log: {err!r}")
        time.sleep(max(5.0, a.every))


if __name__ == "__main__":
    sys.exit(main())
