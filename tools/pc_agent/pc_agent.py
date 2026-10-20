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
# Windows 7 PCs run at most Python 3.8, which would evaluate `str | None` at import and crash.
from __future__ import annotations

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
POLL_S = 1.0            # mode / screen view / messages (1 s: a viewer sees the first frame within ~1-1.5 s)
FRAME_S = 0.5           # screen view: about two frames a second
FRAME_WIDTH = 1280      # downscaled: enough to read a screen, small to send

WINDOWS = sys.platform == "win32"
AGENT_VERSION = "0.8"


def identity_info() -> dict:
    """What the admin's fleet view shows (2026-10-18): host name, this PC's own IPv4 addresses (from its
    network adapters - never inferred from the router), agent version, boot time, and the agent's
    clock, so the portal can see a PC whose clock has drifted."""
    import socket
    ips = []
    try:
        for name, addrs in psutil.net_if_addrs().items():
            if any(v in name.lower() for v in ("vethernet", "vmware", "virtualbox", "hyper-v", "loopback", "bluetooth")):
                continue                        # virtual adapters (WSL / VMs) are not how the lab reaches this PC
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.")):
                    ips.append(a.address)
    except Exception:
        pass
    return {"hostname": socket.gethostname(), "ips": sorted(set(ips))[:4], "agent_version": AGENT_VERSION,
            "boot_time": int(psutil.boot_time()), "agent_time": round(time.time(), 3)}
if WINDOWS:
    # Real pixels: without this, a 125 % display reports 1536x864 instead of 1920x1080 and the
    # monitor rectangles do not match what is captured.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)        # per-monitor DPI aware
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


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


def foreground_app() -> str | None:
    """The program in front (e.g. MATLAB.exe) - the program name only, never the window title."""
    if not WINDOWS:
        return None
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name() if pid.value else None
    except (psutil.Error, OSError):
        return None


def open_share_page(url: str) -> None:
    """Students' PCs: open the portal's presentation page in the default browser."""
    import webbrowser
    try:
        webbrowser.open(url, new=1)
    except Exception as e:
        print(f"[share] could not open the browser: {e}")


def monitors() -> list[dict]:
    """The PC's monitors (virtual-desktop coordinates), primary first. Re-read every time, so a
    plugged / unplugged screen or a resolution change is picked up by the next frame."""
    if not WINDOWS:
        return []
    from ctypes import wintypes
    out = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.POINTER(wintypes.RECT), ctypes.c_double)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", ctypes.c_ulong)]

    def cb(hmon, _hdc, _rect, _data):
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi))
        r = mi.rcMonitor
        out.append({"left": r.left, "top": r.top, "right": r.right, "bottom": r.bottom, "primary": bool(mi.dwFlags & 1)})
        return 1
    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(cb), 0)
    except OSError:
        return []
    out.sort(key=lambda m: (not m["primary"], m["left"]))
    return [{"index": i + 1, "width": m["right"] - m["left"], "height": m["bottom"] - m["top"], "primary": m["primary"],
             "bbox": (m["left"], m["top"], m["right"], m["bottom"])} for i, m in enumerate(out)]


def _virtual_screen() -> tuple[int, int, int, int]:
    u = ctypes.windll.user32
    x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)          # SM_X/YVIRTUALSCREEN
    return x, y, x + u.GetSystemMetrics(78), y + u.GetSystemMetrics(79)


def _grab_gdi(bbox, quality: int) -> bytes | None:
    """Pillow-free capture: Windows GDI BitBlt + OpenCV JPEG encoding (OpenCV/numpy are already on
    the lab laptop for the camera service). Returns None if they are missing or the desktop is locked."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("[screen] neither pillow nor opencv is installed: pip install pillow")
        return None
    from ctypes import wintypes
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    # 64-bit handles: declare every signature, or ctypes truncates them to int.
    u.GetDC.restype, u.GetDC.argtypes = wintypes.HDC, [wintypes.HWND]
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    g.CreateCompatibleDC.restype, g.CreateCompatibleDC.argtypes = wintypes.HDC, [wintypes.HDC]
    g.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    g.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    g.SelectObject.restype, g.SelectObject.argtypes = wintypes.HGDIOBJ, [wintypes.HDC, wintypes.HGDIOBJ]
    g.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC,
                         ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    g.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wintypes.UINT]
    g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    g.DeleteDC.argtypes = [wintypes.HDC]
    src = u.GetDC(None)
    mem = g.CreateCompatibleDC(src)
    bmp = g.CreateCompatibleBitmap(src, w, h)
    old = g.SelectObject(mem, bmp)
    try:
        if not g.BitBlt(mem, 0, 0, w, h, src, left, top, 0x00CC0020 | 0x40000000):   # SRCCOPY | CAPTUREBLT
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                        ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                        ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)   # top-down BGRA
        buf = ctypes.create_string_buffer(w * h * 4)
        if not g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0):
            return None
        img = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
    finally:
        g.SelectObject(mem, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mem)
        u.ReleaseDC(None, src)
    if w > FRAME_WIDTH:
        img = cv2.resize(img, (FRAME_WIDTH, round(h * FRAME_WIDTH / w)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, max(20, min(90, int(quality)))])
    return jpg.tobytes() if ok else None


def grab_jpeg(monitor: int = 0, quality: int = 60) -> bytes | None:
    """monitor 0 = every screen side by side; 1.. = that monitor (1 = primary)."""
    try:
        from PIL import ImageGrab
    except ImportError:
        if not WINDOWS:
            return None
        mons = monitors() if monitor else []
        bbox = mons[monitor - 1]["bbox"] if monitor and monitor <= len(mons) else _virtual_screen()
        return _grab_gdi(bbox, quality)
    try:
        mons = monitors() if monitor else []
        if monitor and monitor <= len(mons):
            img = ImageGrab.grab(bbox=mons[monitor - 1]["bbox"], all_screens=True)
        else:
            img = ImageGrab.grab(all_screens=True)
    except OSError:                        # locked / secure desktop: nothing to grab
        return None
    if img.width > FRAME_WIDTH:
        img = img.resize((FRAME_WIDTH, round(img.height * FRAME_WIDTH / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=max(20, min(90, int(quality))))
    return buf.getvalue()


# ------------------------------------------------- staff actions (allowlisted) ---
# The portal sends only an action name and an app KEY; what each key starts is decided HERE
# (pc_apps.json next to this file overrides the defaults). Unknown keys are refused.
import json
import subprocess

DEFAULT_APPS = {
    "notepad": {"start": ["notepad.exe"], "image": "notepad.exe"},
    "browser": {"start": ["cmd", "/c", "start", "", "msedge"], "image": "msedge.exe"},
    "vscode": {"start": ["cmd", "/c", "start", "", "code"], "image": "Code.exe"},
    "matlab": {"start": ["cmd", "/c", "start", "", "matlab"], "image": "MATLAB.exe"},
    "proteus": {"start": ["cmd", "/c", "start", "", "PDS.EXE"], "image": "PDS.EXE"},
    "arduino_ide": {"start": ["cmd", "/c", "start", "", "Arduino IDE"], "image": "Arduino IDE.exe"},
}
WARN_S = 60             # restart / shut down: the user gets a minute's warning on screen


def load_apps() -> dict:
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc_apps.json")
    if os.path.isfile(p):
        try:
            return {**DEFAULT_APPS, **json.load(open(p, encoding="utf-8"))}
        except (OSError, ValueError) as e:
            print(f"[actions] pc_apps.json ignored: {e}")
    return DEFAULT_APPS


def run_action(a: dict) -> tuple[bool, str]:
    """Carry out one staff action; the returned text is reported to the portal as-is."""
    if not WINDOWS:
        return False, "not a Windows PC"
    act, apps = a.get("action"), load_apps()
    if act == "lock":
        return lock_pc(), "locked"
    if act in ("open_app", "close_app"):
        app = apps.get(a.get("app") or "")
        if app is None:
            return False, f"'{a.get('app')}' is not configured on this PC"
        if act == "open_app":
            subprocess.Popen(app["start"], creationflags=0x08000000)      # no console window
            return True, f"started {a['app']}"
        # Polite close (like clicking X): the program may ask to save; no /F.
        r = subprocess.run(["taskkill", "/IM", app["image"]], capture_output=True, text=True)
        return r.returncode == 0, (r.stdout or r.stderr).strip()[:180] or "close requested"
    msg = "Lab staff: this PC will {} in 1 minute. Save your work now."
    if act == "logoff":
        popup("Smart Lab", "Lab staff are signing this session out. Save your work.")
        time.sleep(10)
        r = subprocess.run(["shutdown", "/l"], capture_output=True, text=True)
        return r.returncode == 0, "signing out" if r.returncode == 0 else r.stderr.strip()[:180]
    if act in ("restart", "shutdown"):
        flag, word = ("/r", "restart") if act == "restart" else ("/s", "shut down")
        r = subprocess.run(["shutdown", flag, "/t", str(WARN_S), "/c", msg.format(word)], capture_output=True, text=True)
        return r.returncode == 0, (f"{word} in {WARN_S} s (warning shown)" if r.returncode == 0 else r.stderr.strip()[:180])
    return False, f"unknown action {act!r}"


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
                "firmware_version": f"pc-agent-{AGENT_VERSION}",
                "detail": {**identity_info(), "os_user": user, "locked_by_portal": locked,
                           "foreground_app": foreground_app(),
                           "monitors": [{k: m[k] for k in ("index", "width", "height", "primary")} for m in monitors()]},
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


WAIT_S = 20.0           # long-poll window while idle
_wait_ok = {"until": 0.0}


def idle_wait(http, args, mode: str, last_report: float) -> None:
    """Idle: wait on the portal's /pc/wait (returns the moment a viewer opens, a share starts, an
    action/message/mode arrives) instead of sleeping a fixed second. LOCKED keeps the 1 s loop so
    the PC is re-locked promptly; an older portal without /pc/wait falls back to the 1 s poll."""
    if mode == "LOCKED" or time.monotonic() < _wait_ok["until"]:
        time.sleep(POLL_S)
        return
    budget = max(0.5, min(WAIT_S, args.period - (time.monotonic() - last_report)))
    try:
        r = http.get(args.portal + "/equipment/pc/wait", params={"device_uid": args.device, "timeout": round(budget, 1)},
                     timeout=budget + 5)
        if r.status_code != 200:
            _wait_ok["until"] = time.monotonic() + 60       # not supported here: plain polling for a minute
            time.sleep(POLL_S)
    except requests.RequestException:
        time.sleep(POLL_S)


def main():
    ap = argparse.ArgumentParser(description="Smart Lab PC agent")
    ap.add_argument("--device", required=True, help="device id in the portal, e.g. PC_01")
    ap.add_argument("--asset", default=None, help="asset tag, e.g. PC-01")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://192.168.1.200:8000/api")
    ap.add_argument("--period", type=float, default=30.0, help="usage report period (s)")
    ap.add_argument("--web", default=None, help="portal web address for the share page (default: from --portal)")
    args = ap.parse_args()
    http = requests.Session()
    http.headers["X-Device-Key"] = DEVICE_KEY
    rep = Reporter(args, http)
    print(f"Smart Lab PC agent for {args.device}. Reports usage; follows the portal's "
          f"lock / screen view / messages; in exam mode reports prohibited programs. Ctrl+C stops.")

    web = (args.web or args.portal.replace(":8000/api", "").replace("/api", "")).rstrip("/")
    mode, mirroring, last_report, last_lock = "NORMAL", False, 0.0, 0.0
    watching_share = False
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
        if p.get("action"):
            a = p["action"]
            print(f"[action] {a}")
            try:
                ok, text = run_action(a)
            except Exception as e:                       # report the real failure, never "done"
                ok, text = False, f"{e.__class__.__name__}: {e}"[:180]
            try:
                http.post(args.portal + "/equipment/pc/action-result", timeout=5,
                          json={"device_uid": args.device, "id": a["id"], "ok": ok, "message": text})
            except requests.RequestException as e:
                print(f"[action] result not delivered: {e}")

        b = p.get("broadcast") or {}
        if b.get("active") and not watching_share:
            popup("Smart Lab", f"{b.get('by') or 'Lab staff'} is sharing their screen" +
                  (f": {b['title']}" if b.get("title") else "") + ". It opens in your browser.")
            open_share_page(web + "/share")
        elif watching_share and not b.get("active"):
            print("[share] presentation ended")
        watching_share = bool(b.get("active"))
        if p.get("broadcast_capture"):           # this is the admin's master PC and it is presenting
            until = time.monotonic() + POLL_S
            while time.monotonic() < until:
                t = time.monotonic()
                jpeg = grab_jpeg()
                if jpeg:
                    try:
                        r = http.post(args.portal + "/equipment/pc/broadcast-frame", params={"device_uid": args.device},
                                      data=jpeg, headers={"Content-Type": "image/jpeg"}, timeout=5)
                        if r.status_code == 409:    # presentation stopped
                            break
                    except requests.RequestException:
                        break
                time.sleep(max(0.0, FRAME_S - (time.monotonic() - t)))
            continue

        watched = bool(p.get("mirror"))
        if watched and not mirroring:
            popup("Smart Lab", "Lab staff are viewing this screen from the Smart Lab portal.")
        elif mirroring and not watched:
            print("[screen] viewing stopped")
        mirroring = watched
        if not mirroring:
            idle_wait(http, args, mode, last_report)
            continue
        # Viewing: send frames for one poll period, then ask again (the viewer's monitor / quality / fps).
        o = p.get("mirror_opts") or {}
        frame_s = 1.0 / max(0.5, min(5.0, float(o.get("fps", 2.0))))
        until = time.monotonic() + POLL_S
        while time.monotonic() < until:
            t = time.monotonic()
            jpeg = grab_jpeg(int(o.get("monitor", 0)), int(o.get("quality", 60)))
            if jpeg:
                try:
                    r = http.post(args.portal + "/equipment/pc/frame", params={"device_uid": args.device},
                                  data=jpeg, headers={"Content-Type": "image/jpeg"}, timeout=5)
                    if r.status_code == 409:    # viewer closed
                        break
                except requests.RequestException:
                    break
            time.sleep(max(0.0, frame_s - (time.monotonic() - t)))


if __name__ == "__main__":
    main()
