---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/robot_monitor/fanuc_probe.py"
source_hash: "04aadae52073d81c0d41e710072fc66f4834a34ff9b188e61c1f9be938cad218"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/robot_monitor/fanuc_probe.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[docs_LAB_TEST_2026-10-14.md]] - mentioned by docs
- [[docs_ROBOTS.md]] - mentioned by docs

```py
"""
FANUC controller inspection - READ-ONLY, for choosing the monitoring
interface (nothing is assumed about the controller until this has run).

What it does, and nothing else:
  1. ping-like TCP connect checks on a short list of well-known ports (a
     connect is opened and closed at once - no data is sent);
  2. if port 80 answers: GET of the controller's web home page and of the
     status pages FANUC web servers commonly offer, saved to fanuc_probe_out/
     for reading (a page that does not exist just returns 404).

It never logs in, never posts, never writes a register, an I/O or a program.

    py fanuc_probe.py --robot <IP of one FANUC Ethernet port>

Run it for EACH of the two cables' addresses (they may be different
interfaces with different addresses - the audit in docs/ROBOTS.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import socket

import requests

PORTS = {80: "HTTP (controller web server)", 21: "FTP", 23: "Telnet", 502: "Modbus TCP",
         44818: "EtherNet/IP", 60008: "SNPX / HMI", 18735: "Stream Motion (UDP normally; TCP check only)"}
PAGES = ["/", "/MD/CURPOS.DG", "/MD/SUMMARY.DG", "/MD/ERRALL.LS", "/MD/IOSTATE.DG"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fanuc_probe_out")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot", required=True)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print(f"FANUC read-only probe of {a.robot} ({stamp})")
    open_ports = []
    for port, what in PORTS.items():
        s = socket.socket()
        s.settimeout(1.0)
        try:
            ok = s.connect_ex((a.robot, port)) == 0
        finally:
            s.close()
        print(f"  tcp {port:<6} {'OPEN  ' if ok else 'closed'} {what}")
        if ok:
            open_ports.append(port)
    if 80 in open_ports:
        for page in PAGES:
            try:
                r = requests.get(f"http://{a.robot}{page}", timeout=4)
                name = f"{stamp}_{a.robot}_{page.strip('/').replace('/', '_') or 'index'}.txt"
                with open(os.path.join(OUT, name), "w", encoding="utf-8", errors="replace") as f:
                    f.write(r.text)
                print(f"  GET {page:<16} HTTP {r.status_code}, {len(r.text)} chars -> fanuc_probe_out/{name}")
            except requests.RequestException as e:
                print(f"  GET {page:<16} failed: {e.__class__.__name__}")
    print("Send the output (and the saved pages) - the monitoring interface is chosen from what is really there.")


if __name__ == "__main__":
    main()

```
