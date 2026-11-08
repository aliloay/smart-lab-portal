"""
UR5e collector - READ-ONLY monitoring over RTDE (Robotics Lab, Phase 5).

Runs on the lab laptop, connects to the UR5e controller over the lab
Ethernet with Universal Robots' Real-Time Data Exchange (RTDE) interface
through the `ur_rtde` library, and reports to the portal:

    every 5 s   state RUNNING / IDLE / FAULT + what RTDE exposed
                POST /api/equipment/state
    every 60 s  a few numbers (speed scaling, joint positions) as metrics

It only RECEIVES. It never sends a command, a program or an I/O write to
the robot: there is no control interface in this file.

    pip install ur_rtde requests
    py ur5e_rtde_collector.py --robot 192.168.1.160

STATUS: written against the RTDE fields documented by Universal Robots
(robot_mode, safety_mode, runtime_state, actual_q, speed_scaling); NOT yet
run against this lab's controller. Confirm every field and code below with
the RTDE guide for the controller's software version before relying on it.
"""
import argparse
import os
import sys
import time

import requests

PORTAL = os.environ.get("PORTAL_URL", "http://127.0.0.1:8000/api")
DEVICE_KEY = os.environ.get("DEVICE_KEY", "dev-device-key-change-me")

# RTDE runtime_state: 2 = PLAYING (a program is running). VERIFY.
RUNTIME_PLAYING = 2
# RTDE safety_mode: 1 = NORMAL, 2 = REDUCED; anything else (protective
# stop, safeguard stop, emergency stops, violation, fault...) is a FAULT
# for monitoring purposes. VERIFY against the controller's guide.
SAFETY_OK = {1, 2}


def classify(runtime_state, safety_mode):
    if safety_mode is not None and safety_mode not in SAFETY_OK:
        return "FAULT"
    return "RUNNING" if runtime_state == RUNTIME_PLAYING else "IDLE"


def post(path, body):
    try:
        r = requests.post(PORTAL + path, json=body, timeout=3,
                          headers={"X-Device-Key": DEVICE_KEY})
        if r.status_code != 200:
            print(f"[portal] {path} -> HTTP {r.status_code} {r.text[:120]}")
        return r
    except requests.RequestException as e:
        print(f"[portal] unreachable: {e}")
        return None


def main():
    ap = argparse.ArgumentParser(description="UR5e read-only RTDE collector")
    ap.add_argument("--robot", required=True, help="controller IP on the lab LAN")
    ap.add_argument("--device", default="UR5E_01", help="device id in the portal")
    ap.add_argument("--asset", default="UR5E-01", help="asset tag in the portal")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--period", type=float, default=5.0)
    ap.add_argument("--metrics-period", type=float, default=60.0)
    args = ap.parse_args()

    try:
        from rtde_receive import RTDEReceiveInterface      # receive-only interface
    except ImportError:
        sys.exit("ur_rtde is not installed: pip install ur_rtde")

    rx = None
    last_metrics = 0.0
    print(f"Collecting from {args.robot} as {args.device} (read-only). Ctrl+C stops.")
    while True:
        try:
            if rx is None:
                rx = RTDEReceiveInterface(args.robot)
                print("[rtde] connected")
            robot_mode = rx.getRobotMode()
            safety_mode = rx.getSafetyMode()
            runtime_state = rx.getRuntimeState()
            state = classify(runtime_state, safety_mode)
            body = {"device_uid": args.device, "lab_id": args.lab, "kind": "ROBOT",
                    "asset_tag": args.asset, "state": state,
                    "firmware_version": "ur5e-collector-0.1",
                    "detail": {"robot_mode": robot_mode, "safety_mode": safety_mode,
                               "runtime_state": runtime_state}}
            if time.time() - last_metrics >= args.metrics_period:
                q = rx.getActualQ()
                body["metrics"] = ([{"metric": "ur_speed_scaling",
                                     "value": float(rx.getSpeedScaling()), "unit": ""}] +
                                   [{"metric": f"ur_joint{i}_rad", "value": float(v), "unit": "rad"}
                                    for i, v in enumerate(q)])
                last_metrics = time.time()
            post("/equipment/state", body)
        except KeyboardInterrupt:
            break
        except Exception as e:                        # connection lost: report nothing
            print(f"[rtde] {type(e).__name__}: {e} - reconnecting")
            rx = None                                  # the portal sees it go offline
            time.sleep(5)
            continue
        time.sleep(args.period)


if __name__ == "__main__":
    main()
