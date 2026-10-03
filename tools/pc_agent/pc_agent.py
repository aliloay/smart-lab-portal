"""
Lab PC agent (Robotics Lab, System 1) - visible, documented, minimal.

Runs on PC-01 / PC-02 (on the lab LAN) inside the signed-in user's session
and every 30 s reports to the portal: CPU, RAM, disk and network use, and
whether someone is logged in (state RUNNING = a session is open, IDLE =
nobody logged in). The portal answers with the mode staff set: NORMAL,
EXAM, MAINTENANCE or LOCKED.

Admin master PC controls (the agent polls every 2 s; nothing pushes in):
  * LOCKED (staff "Remove access"): the PC is locked, and locked again
    within ~2 s whenever someone unlocks it, until staff "Give access".
  * Screen view: only while a staff member has the view open in the
    portal. A notice pops up on this PC when it starts; frames go to the
    portal's memory only and stop within ~6 s of the viewer closing.
  * Message: a short text from staff, shown in a pop-up.

In EXAM mode - and only then - it compares the RUNNING PROGRAM NAMES
against the prohibited list the portal sends (configured by staff) and
reports each one once as a violation. Staff are notified; nothing is
decided automatically about the student.

What it never does: keystrokes, browser history, file contents,
webcam/microphone, or screen capture while nobody is viewing. Websites
(Instagram, YouTube...) cannot be seen from a program list - blocking those
needs a managed / kiosk exam browser, which is a lab policy, not this agent.

    pip install psutil requests pillow
    py pc_agent.py --device PC_01 --portal http://192.168.1.200:8000/api
"""
import argparse
import ctypes
import io
import os
import sys
import threading
import time

import psutil
import requests

DEVICE_KEY = os.environ.get("DEVICE_KEY", "dev-device-key-change-me")
POLL_S = 2.0            # mode / screen view / messages
FRAME_S = 0.5           # screen view: about two frames a second
FRAME_WIDTH = 1280      # downscaled: enough to read a screen, small to send

WINDOWS = sys.platform == "win32"


def logged_in_user():
    users = psutil.users()
    return users[0].name if users else None


# ------------------------------------------------------------ Windows ---
def lock_pc() -> bool:
    """Lock this session (same as Win+L). Harmless if already locked."""
    if not WINDOWS:
        return False
    return bool(ctypes.windll.user32.LockWorkStation())


def popup(title: str, text: str) -> None:
    """A topmost information box that does not block the agent."""
    print(f"[{title}] {text}")
    if not WINDOWS:
        return
    MB_ICONINFORMATION, MB_TOPMOST, MB_SETFOREGROUND = 0x40, 0x40000, 0x10000
    threading.Thread(target=ctypes.windll.user32.MessageBoxW, daemon=True,
                     args=(None, text, title, MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND)
                     ).start()


def grab_jpeg() -> bytes | None:
    try:
        from PIL import ImageGrab
    except ImportError:
        print("[screen] pillow is not installed: pip install pillow")
        return None
    try:
        img = ImageGrab.grab()             # the primary screen of this session
    except OSError:                        # locked / secure desktop: nothing to grab
        return None
    if img.width > FRAME_WIDTH:
        img = img.resize((FRAME_WIDTH, round(img.height * FRAME_WIDTH / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=60)
    return buf.getvalue()


# ------------------------------------------------------------- report ---
class Reporter:
    def __init__(self, args, session):
        self.args, self.http = args, session
        self.net0, self.t0 = psutil.net_io_counters(), time.time()
        self.reported = set()           # program names already reported in this exam
        psutil.cpu_percent(None)

    def report(self, locked: bool) -> dict:
        net, t = psutil.net_io_counters(), time.time()
        dt = max(t - self.t0, 1e-6)
        user = logged_in_user()
        body = {"device_uid": self.args.device, "lab_id": self.args.lab, "kind": "PC",
                "asset_tag": self.args.asset, "state": "RUNNING" if user else "IDLE",
                "firmware_version": "pc-agent-0.2",
                "detail": {"os_user": user, "locked_by_portal": locked},
                "metrics": [
                    {"metric": "pc_cpu_pct", "value": psutil.cpu_percent(None), "unit": "%"},
                    {"metric": "pc_ram_pct", "value": psutil.virtual_memory().percent, "unit": "%"},
                    {"metric": "pc_disk_pct", "value": psutil.disk_usage(os.path.abspath(os.sep)).percent, "unit": "%"},
                    {"metric": "pc_net_rx_kbps", "value": round((net.bytes_recv - self.net0.bytes_recv) * 8 / 1000 / dt, 1), "unit": "kbps"},
                    {"metric": "pc_net_tx_kbps", "value": round((net.bytes_sent - self.net0.bytes_sent) * 8 / 1000 / dt, 1), "unit": "kbps"},
                ]}
        self.net0, self.t0 = net, t
        r = self.http.post(self.args.portal + "/equipment/state", json=body, timeout=5)
        reply = r.json() if r.status_code == 200 else {}
        if reply.get("mode") == "EXAM":
            self.exam(set(reply.get("prohibited", [])), user)
        else:
            self.reported.clear()
        return reply

    def exam(self, prohibited: set, user):
        for p in psutil.process_iter(["pid", "name"]):
            name = (p.info["name"] or "").lower()
            # Once per program per exam: several processes of one program
            # (a browser, an app with helpers) are one violation, not many.
            if name in prohibited and name not in self.reported:
                self.reported.add(name)
                print(f"[exam] prohibited program running: {name}")
                try:
                    self.http.post(self.args.portal + "/equipment/violations", timeout=5,
                                   json={"device_uid": self.args.device, "kind": "PROHIBITED_PROGRAM",
                                         "detail": f"{name} running", "os_user": user})
                except requests.RequestException:
                    self.reported.discard(name)                # try again next round


def main():
    ap = argparse.ArgumentParser(description="Smart Lab PC agent")
    ap.add_argument("--device", required=True, help="device id in the portal, e.g. PC_01")
    ap.add_argument("--asset", default=None, help="asset tag, e.g. PC-01")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://192.168.1.200:8000/api")
    ap.add_argument("--period", type=float, default=30.0, help="usage report period (s)")
    args = ap.parse_args()
    http = requests.Session()
    http.headers["X-Device-Key"] = DEVICE_KEY
    rep = Reporter(args, http)
    print(f"Smart Lab PC agent for {args.device}. Reports usage; follows the portal's "
          f"lock / screen view / messages; in exam mode reports prohibited programs. Ctrl+C stops.")

    mode, mirroring, last_report, last_lock = "NORMAL", False, 0.0, 0.0
    while True:
        now = time.monotonic()
        try:
            if now - last_report >= args.period:
                last_report = now
                mode = rep.report(mode == "LOCKED").get("mode", mode)
            p = http.get(args.portal + "/equipment/pc/poll", params={"device_uid": args.device},
                         timeout=5).json()
        except (requests.RequestException, ValueError) as e:
            print(f"[portal] unreachable: {e}")
            time.sleep(POLL_S)
            continue

        new_mode = p.get("mode", "NORMAL")
        if new_mode != mode:
            print(f"[mode] {mode} -> {new_mode}")
            if mode == "LOCKED":
                popup("Smart Lab", "Lab staff gave this PC access again.")
            mode = new_mode
        if mode == "LOCKED" and now - last_lock >= POLL_S:
            last_lock = now
            lock_pc()                    # access removed by staff: locked again if unlocked
        if p.get("message"):
            popup("Message from lab staff", p["message"]["text"])

        watched = bool(p.get("mirror"))
        if watched and not mirroring:
            popup("Smart Lab", "Lab staff are viewing this screen from the Smart Lab portal.")
        elif mirroring and not watched:
            print("[screen] viewing stopped")
        mirroring = watched
        if not mirroring:
            time.sleep(POLL_S)
            continue
        # Viewing: send frames for one poll period, then ask again.
        until = time.monotonic() + POLL_S
        while time.monotonic() < until:
            t = time.monotonic()
            jpeg = grab_jpeg()
            if jpeg:
                try:
                    r = http.post(args.portal + "/equipment/pc/frame", params={"device_uid": args.device},
                                  data=jpeg, headers={"Content-Type": "image/jpeg"}, timeout=5)
                    if r.status_code == 409:    # viewer closed
                        break
                except requests.RequestException:
                    break
            time.sleep(max(0.0, FRAME_S - (time.monotonic() - t)))


if __name__ == "__main__":
    main()
