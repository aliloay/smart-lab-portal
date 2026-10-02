"""
Lab PC agent (Robotics Lab, Phase 7) - visible, documented, minimal.

Runs on PC-01 / PC-02 (wired to the lab LAN) and every 30 s reports to the
portal: CPU, RAM, disk and network use, and whether someone is logged in
(state RUNNING = a session is open, IDLE = nobody logged in). The portal
answers with the mode an engineer set: NORMAL, MAINTENANCE or EXAM.

In EXAM mode - and only then - it compares the RUNNING PROGRAM NAMES
against the prohibited list the portal sends (configured by staff) and
reports each one once as a violation. Staff are notified; nothing is
decided automatically about the student.

What it never does: screenshots, keystrokes, browser history, file
contents, webcam/microphone. Websites (Instagram, YouTube...) cannot be
seen from a program list - blocking those needs a managed / kiosk exam
browser, which is a lab policy, not this agent.

    pip install psutil requests
    py pc_agent.py --device PC_01 --portal http://192.168.1.200:8000/api

STATUS: written and syntax-checked; not yet deployed on the lab PCs.
"""
import argparse
import os
import time

import psutil
import requests

DEVICE_KEY = os.environ.get("DEVICE_KEY", "dev-device-key-change-me")


def logged_in_user():
    users = psutil.users()
    return users[0].name if users else None


def main():
    ap = argparse.ArgumentParser(description="Smart Lab PC agent")
    ap.add_argument("--device", required=True, help="device id in the portal, e.g. PC_01")
    ap.add_argument("--asset", default=None, help="asset tag, e.g. PC-01")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://192.168.1.200:8000/api")
    ap.add_argument("--period", type=float, default=30.0)
    args = ap.parse_args()
    headers = {"X-Device-Key": DEVICE_KEY}
    reported = set()                  # program names already reported in this exam
    net0 = psutil.net_io_counters()
    t0 = time.time()
    print(f"Smart Lab PC agent for {args.device}. Reports usage and, in exam mode, "
          f"prohibited programs. Ctrl+C stops.")
    psutil.cpu_percent(None)
    while True:
        time.sleep(args.period)
        net, t = psutil.net_io_counters(), time.time()
        dt = max(t - t0, 1e-6)
        user = logged_in_user()
        body = {"device_uid": args.device, "lab_id": args.lab, "kind": "PC",
                "asset_tag": args.asset, "state": "RUNNING" if user else "IDLE",
                "firmware_version": "pc-agent-0.1",
                "detail": {"os_user": user},
                "metrics": [
                    {"metric": "pc_cpu_pct", "value": psutil.cpu_percent(None), "unit": "%"},
                    {"metric": "pc_ram_pct", "value": psutil.virtual_memory().percent, "unit": "%"},
                    {"metric": "pc_disk_pct", "value": psutil.disk_usage(os.path.abspath(os.sep)).percent, "unit": "%"},
                    {"metric": "pc_net_rx_kbps", "value": round((net.bytes_recv - net0.bytes_recv) * 8 / 1000 / dt, 1), "unit": "kbps"},
                    {"metric": "pc_net_tx_kbps", "value": round((net.bytes_sent - net0.bytes_sent) * 8 / 1000 / dt, 1), "unit": "kbps"},
                ]}
        net0, t0 = net, t
        try:
            r = requests.post(args.portal + "/equipment/state", json=body, headers=headers, timeout=5)
            reply = r.json() if r.status_code == 200 else {}
        except (requests.RequestException, ValueError) as e:
            print(f"[portal] unreachable: {e}")
            continue
        mode = reply.get("mode", "NORMAL")
        if mode != "EXAM":
            reported.clear()
            continue
        prohibited = set(reply.get("prohibited", []))
        for p in psutil.process_iter(["pid", "name"]):
            name = (p.info["name"] or "").lower()
            # Once per program per exam: several processes of one program
            # (a browser, an app with helpers) are one violation, not many.
            if name in prohibited and name not in reported:
                reported.add(name)
                print(f"[exam] prohibited program running: {name}")
                try:
                    requests.post(args.portal + "/equipment/violations", headers=headers, timeout=5,
                                  json={"device_uid": args.device, "kind": "PROHIBITED_PROGRAM",
                                        "detail": f"{name} running", "os_user": user})
                except requests.RequestException:
                    reported.discard(name)                    # try again next round


if __name__ == "__main__":
    main()
