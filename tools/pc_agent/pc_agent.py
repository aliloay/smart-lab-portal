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

# Hidden start (pythonw.exe from install_autostart.bat, 2026-11-03): no console - the log goes to
# %TEMP%\smartlab_agent.log so prints and errors never fail and can still be read.
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.path.join(os.environ.get("TEMP", "."), "smartlab_agent.log"), "a",
                                   encoding="utf-8", buffering=1)

import random

import psutil
import requests

DEVICE_KEY = os.environ.get("DEVICE_KEY", "dev-device-key-change-me")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status_tray  # noqa: E402

POLL_S = 1.0            # mode / screen view / messages (1 s: a viewer sees the first frame within ~1-1.5 s)
FRAME_S = 0.5           # screen view: about two frames a second
FRAME_WIDTH = 1280      # downscaled: enough to read a screen, small to send

WINDOWS = sys.platform == "win32"
AGENT_VERSION = "1.0"
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_STARTED = round(time.time(), 3)   # this run; a new value without a reboot = the agent was stopped


def identity_info() -> dict:
    """What the admin's fleet view shows (2026-10-18): host name, this PC's own IPv4 addresses (from its
    network adapters - never inferred from the router), agent version, boot time, and the agent's
    clock, so the portal can see a PC whose clock has drifted. Also the MAC of each adapter that has
    a LAN address (2026-10-21): the lab laptop's LAN check then finds this PC by itself - no MAC list."""
    import socket
    ips, macs = [], []
    try:
        for name, addrs in psutil.net_if_addrs().items():
            if any(v in name.lower() for v in ("vethernet", "vmware", "virtualbox", "hyper-v", "loopback", "bluetooth")):
                continue                        # virtual adapters (WSL / VMs) are not how the lab reaches this PC
            lan = [a.address for a in addrs if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254."))]
            ips += lan
            if lan:
                macs += [a.address.lower().replace(":", "-") for a in addrs
                         if a.family == psutil.AF_LINK and len(a.address) == 17]
    except Exception:
        pass
    # 2026-11-03 (Gemini network audit): a dual-NIC lab PC (GIU 10.40.20.x + Smart Lab 192.168.1.x) listed its GIU
    # address first ("10..." < "192..." as text), so the portal pinged an address it cannot reach - Smart Lab first
    lab_first = sorted(set(ips), key=lambda ip: (not ip.startswith("192.168.1."), ip))
    return {"hostname": socket.gethostname(), "ips": lab_first[:4], "macs": sorted(set(macs))[:4],
            "agent_version": AGENT_VERSION,
            "boot_time": int(psutil.boot_time()), "agent_time": round(time.time(), 3),
            "agent_started": AGENT_STARTED}
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


SIGNOUT_GRACE_S = 5.0    # "Remove access": seconds of warning before the session is signed out


def sign_out() -> bool:
    """Sign this Windows session out (2026-11-04: GIU lab PCs block Win+L / LockWorkStation, so a lock
    alone does nothing there). ExitWindowsEx first, shutdown /l as the fallback."""
    if not WINDOWS:
        return False
    EWX_LOGOFF, EWX_FORCEIFHUNG = 0x0, 0x10
    if ctypes.windll.user32.ExitWindowsEx(EWX_LOGOFF | EWX_FORCEIFHUNG, 0):
        return True
    try:
        return subprocess.run(["shutdown", "/l"], capture_output=True).returncode == 0
    except OSError:
        return False


def first_time(message_id, path: str | None = None, keep: int = 300) -> bool:
    """True once per message id, across agent restarts: a message the user closed never comes back."""
    path = path or os.path.join(os.environ.get("TEMP", "."), "smartlab_seen_messages.json")
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
    except (OSError, ValueError):
        seen = []
    if message_id in seen:
        return False
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump((seen + [message_id])[-keep:], f)
    except OSError:
        pass
    return True


def popup(title: str, text: str, kind: str = "info", sender: str | None = None, countdown: int = 0,
          expires: int = 0) -> None:
    """A coloured card on this PC (notice.py); a plain message box if the card cannot be drawn."""
    if WINDOWS:
        try:
            from notice import notice
            notice(kind, text, title=title if title != "Smart Lab" else "", sender=sender, countdown=countdown, expires=expires)
            return
        except Exception:
            pass
    _plain_popup(title, text)


def _plain_popup(title: str, text: str) -> None:
    """A topmost information box that does not block the agent."""
    print(f"[{title}] {text}")
    if not WINDOWS:
        return
    MB_ICONINFORMATION, MB_TOPMOST, MB_SETFOREGROUND = 0x40, 0x40000, 0x10000
    threading.Thread(target=ctypes.windll.user32.MessageBoxW, daemon=True,
                     args=(None, text, title, MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND)
                     ).start()


_foreground = {"last": None}


def foreground_app() -> str | None:
    """The program in front (e.g. MATLAB.exe) - the program name only, never the window title."""
    if not WINDOWS:
        return None
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        # 2026-11-04 wall: every PC showed "pythonw" - the agent's own notice was in front. Say what the user was using.
        if pid.value != os.getpid():
            _foreground["last"] = psutil.Process(pid.value).name()
        return _foreground["last"]
    except (psutil.Error, OSError):
        return None


def open_share_page(url: str) -> None:
    """Students' PCs: open the portal's presentation page in the default browser."""
    import webbrowser
    try:
        webbrowser.open(url, new=1)
    except Exception as e:
        print(f"[share] could not open the browser: {e}")


def derive_web(portal: str) -> str:
    """--portal http://HOST:8000/api -> the web pages. Another machine gets https://HOST: screen sharing
    (getDisplayMedia) needs HTTPS, and port 80 may be taken on a relay PC (Gemini audit 2026-11-03)."""
    base = portal.replace(":8000/api", "").replace("/api", "").rstrip("/")
    host = base.split("://", 1)[-1].split("/")[0].split(":")[0]
    if host in ("127.0.0.1", "localhost"):
        return base
    return "https://" + base.split("://", 1)[-1]


def open_portal_once_per_logon(url: str, marker_dir: str | None = None) -> bool:
    """Lab PCs (2026-10-21): when someone signs in to Windows, the portal's sign-in page opens. The agent
    is re-started every minute by its scheduled task, so a marker (the user + their Windows logon time)
    makes it happen once per sign-in, never on a restart. Returns True when it opened the page."""
    user = os.environ.get("USERNAME") or ""
    started = next((u.started for u in psutil.users() if u.name.lower() == user.lower()), None)
    if started is None:
        return False                                  # nobody signed in (or not this user's session)
    folder = marker_dir or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "SmartLab")
    marker = os.path.join(folder, "portal_opened.txt")
    stamp = f"{user}:{int(started)}"
    try:
        if open(marker, encoding="utf-8").read().strip() == stamp:
            return False
    except OSError:
        pass
    open_share_page(url)
    try:
        os.makedirs(folder, exist_ok=True)
        open(marker, "w", encoding="utf-8").write(stamp)
    except OSError:
        pass
    return True


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


def countdown_window(seconds: int, word: str) -> None:
    """A topmost window on the PC counting 60, 59, ... 1 (owner 2026-10-21: the student sees exactly how long
    is left to save). Display only: Windows' own shutdown timer, started at the same moment, is what acts at
    0 - even if this window or the agent is closed. Falls back to a message box without tkinter."""
    if WINDOWS:
        popup(f"This PC will {word}", "Lab staff: save your work now - this PC will "
              f"{word} when the counter reaches 0.", kind="warn", countdown=seconds)
        return

    def run():
        try:
            import tkinter as tk
        except ImportError:
            print(f"[countdown] {word} in {seconds} s")
            return
        root = tk.Tk()
        root.title("Smart Lab")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", lambda: None)          # stays until the PC goes down
        tk.Label(root, text=f"Lab staff: this PC will {word} in", font=("Segoe UI", 13), padx=30, pady=(12)).pack()
        n = tk.Label(root, text=str(seconds), font=("Segoe UI", 54, "bold"), fg="#c0392b")
        n.pack()
        tk.Label(root, text="seconds. Save your work now.", font=("Segoe UI", 13), padx=30, pady=12).pack()
        end = time.monotonic() + seconds

        def tick():
            left = max(0, int(round(end - time.monotonic())))
            n.config(text=str(left))
            root.after(250, tick)
        tick()
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
        root.mainloop()
    threading.Thread(target=run, daemon=True).start()


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
        popup("Signing out", "Lab staff are signing this session out in 10 seconds. Save your work now.", kind="warn")
        time.sleep(10)
        r = subprocess.run(["shutdown", "/l"], capture_output=True, text=True)
        return r.returncode == 0, "signing out" if r.returncode == 0 else r.stderr.strip()[:180]
    if act in ("restart", "shutdown"):
        flag, word = ("/r", "restart") if act == "restart" else ("/s", "shut down")
        # /f: after the 60 s on-screen warning, programs that do not close by themselves (an open dialog,
        # Internet Download Manager...) are closed - without it Windows 7 only closed the windows and
        # then waited on "programs still running", never restarting (seen on PC-01, 2026-10-21).
        r = subprocess.run(["shutdown", flag, "/f", "/t", str(WARN_S), "/c", msg.format(word)], capture_output=True, text=True)
        if r.returncode == 0:
            countdown_window(WARN_S, word)
        return r.returncode == 0, (f"{word} in {WARN_S} s (countdown shown)" if r.returncode == 0 else r.stderr.strip()[:180])
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


SHARE_OFFLINE_S = 20.0  # portal unreachable this long: the full-screen share closes
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


# ------------------------------------------- "which PC is this?" for the admin's sign-in ---
WHOAMI_PORT = 47123


def whoami_proof(device_key: str, nonce: str) -> str:
    """HMAC-SHA256 of the portal's one-time nonce, keyed with the SHA-256 of this PC's device key
    (the portal stores only that hash, so it can check the proof; the key itself never leaves)."""
    import hashlib
    import hmac
    return hmac.new(hashlib.sha256(device_key.encode()).hexdigest().encode(), nonce.encode(),
                    hashlib.sha256).hexdigest()


DPAPI_PREFIX = "DPAPI1:"


def _dpapi(data: bytes, protect: bool) -> bytes:
    """Windows DPAPI, current-user scope: only this Windows account on this PC can read the result."""
    import ctypes
    from ctypes import wintypes as w

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", w.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    src, dst = BLOB(len(data), buf), BLOB()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    ok = fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(dst))     # CRYPTPROTECT_UI_FORBIDDEN
    if not ok:
        raise OSError(f"DPAPI failed ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        ctypes.WinDLL("kernel32").LocalFree(dst.pbData)


def write_secret(path: str, value: str) -> None:
    """Protected with DPAPI on Windows. Elsewhere (tests, development) it stays plain text behind file permissions."""
    import base64
    text = value
    if WINDOWS:
        text = DPAPI_PREFIX + base64.b64encode(_dpapi(value.encode(), True)).decode()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def read_key(path: str) -> str:
    """A protected file (installer, enrollment) or a plain one from an older kit, which is protected on first read."""
    import base64
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read().strip()
    except OSError:
        return ""
    if text.startswith(DPAPI_PREFIX):
        try:
            return _dpapi(base64.b64decode(text[len(DPAPI_PREFIX):]), False).decode()
        except (OSError, ValueError) as e:
            print(f"[key] {os.path.basename(path)} cannot be read by this Windows account: {e}")
            return ""
    if text and WINDOWS and os.path.basename(path) == "device.key":
        try:
            write_secret(path, text)
        except OSError as e:
            print(f"[key] could not protect the key file: {e}")
    return text


def account_id() -> str:
    """Identifies this Windows account to the portal without naming it: one PC key per account."""
    import hashlib
    who = (os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")).lower()
    return hashlib.sha256(who.encode()).hexdigest()[:32]


def protect_key(path: str) -> None:
    """Only the Windows user this agent runs as (plus SYSTEM and administrators) may read this PC's key.
    icacls.exe is a plain Windows program, no cmd involved. Best effort: the key still only speaks for this PC."""
    if not WINDOWS:
        return
    user = (os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")).lstrip("\\")
    try:
        subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", f"{user}:(R,W,D)", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)"],
                       capture_output=True, timeout=20, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[enroll] could not restrict the key file: {e}")


def enroll(portal: str, device: str, lab: str, enroll_file: str, key_file: str,
           post=None, sleep=time.sleep, protect: bool = True) -> str:
    """First start on this PC: swap the kit's one-purpose enrollment code for this PC's OWN key, keep trying until
    the portal answers (the relay may not be up yet), then remove the code from this PC. The shared key of the door
    boards never reaches a PC (Gemini + Claude audit, 2026-11-04)."""
    post = post or requests.post
    code, said = read_key(enroll_file), 0.0
    while True:
        why = ""
        try:
            r = post(portal + "/equipment/pc/enroll", headers={"X-Enroll-Key": code},
                     json={"device_uid": device, "lab_id": lab, "account": account_id()}, timeout=10)
            if r.status_code == 200:
                key = r.json()["device_key"]
                write_secret(key_file, key)
                if protect:
                    protect_key(key_file)
                try:
                    os.remove(enroll_file)
                except OSError:
                    pass
                print(f"[enroll] {device} has its own key now")
                return key
            why = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError, KeyError, OSError) as e:
            why = e.__class__.__name__
        if time.monotonic() - said > 60:
            said = time.monotonic()
            print(f"[enroll] waiting for the portal ({why})")
        sleep(10)


def share_fetcher(device_key: str, portal: str):
    """Returns fetch() -> a NEW JPEG of the share, or None when there is nothing new. ETag: an unchanged picture costs
    a few bytes, not ~100 KB per PC several times a second through the relay. Renews the watch token when it expires."""
    s = requests.Session()
    s.headers["X-Device-Key"] = device_key
    state = {"token": None, "etag": None}

    def fetch():
        if state["token"] is None:
            r = s.get(portal + "/equipment/pc/watch-token", timeout=5)
            state["token"] = r.json().get("token") if r.status_code == 200 else None
            if state["token"] is None:
                return None
        r = s.get(portal + "/equipment/broadcast/watch/frame.jpg", params={"t": state["token"]}, timeout=5,
                  headers={"If-None-Match": state["etag"]} if state["etag"] else None)
        if r.status_code == 401:
            state["token"] = None
            return None
        if r.status_code == 200 and r.content[:2] == b"\xff\xd8":
            state["etag"] = r.headers.get("ETag")
            return r.content
        return None
    return fetch


def serve_whoami(device_uid: str, device_key: str, port: int = WHOAMI_PORT):
    """127.0.0.1 only: the portal page in THIS PC's browser asks which PC it runs on when an admin
    signs in (the admin who signs in is the master; the PC they sit at becomes the master PC).
    Answers only GET /whoami?nonce=<hex>; reachable from this PC alone, never from the LAN."""
    import re
    import threading as _t
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    class H(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET")
            self.send_header("Access-Control-Allow-Private-Network", "true")   # Chrome: page -> 127.0.0.1

        def do_OPTIONS(self):
            self.send_response(204); self._cors(); self.end_headers()

        def do_GET(self):
            u = urlparse(self.path)
            nonce = (parse_qs(u.query).get("nonce") or [""])[0]
            if u.path != "/whoami" or not re.fullmatch(r"[0-9a-f]{16,64}", nonce):
                self.send_response(404); self._cors(); self.end_headers(); return
            body = json.dumps({"device_uid": device_uid, "proof": whoami_proof(device_key, nonce)}).encode()
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    class Exclusive(ThreadingHTTPServer):
        # HTTPServer sets SO_REUSEADDR, which on Windows lets a SECOND process bind the same port:
        # no single-instance guard, and another program could answer for this PC. Claim it exclusively.
        allow_reuse_address = False

        def server_bind(self):
            import socket as _s
            if hasattr(_s, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(_s.SOL_SOCKET, _s.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    try:
        srv = Exclusive(("127.0.0.1", port), H)
    except OSError as e:
        print(f"[master] port {port} busy - this PC cannot be recognised at an admin sign-in ({e})")
        return None
    _t.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser(description="Smart Lab PC agent")
    ap.add_argument("--device", required=True, help="device id in the portal, e.g. PC_01")
    ap.add_argument("--asset", default=None, help="asset tag, e.g. PC-01")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://192.168.1.200:8000/api")
    ap.add_argument("--period", type=float, default=30.0, help="usage report period (s)")
    ap.add_argument("--web", default=None, help="portal web address for the share page (default: from --portal)")
    ap.add_argument("--open-portal", action="store_true", help="lab PCs: open the portal sign-in page once per Windows sign-in")
    ap.add_argument("--no-lockdown", action="store_true", help="control PC (portal laptop / lab engineer): never close programs in exam mode")
    ap.add_argument("--key-file", default=None, help="read the device key from this file (start-up shortcut, no cmd needed)")
    ap.add_argument("--enroll-file", default=None, help="no key yet: the kit's enrollment code, swapped once for this PC's own key")
    ap.add_argument("--key-for-all-users", action="store_true", help="installed by an administrator for every Windows account: all may read the key")
    ap.add_argument("--supervised", action="store_true", help="started by agent_boot.py: may update itself from the portal")
    args = ap.parse_args()
    global DEVICE_KEY
    if args.key_file:
        DEVICE_KEY = read_key(args.key_file)
        if not DEVICE_KEY and args.enroll_file and os.path.isfile(args.enroll_file):
            DEVICE_KEY = enroll(args.portal, args.device, args.lab, args.enroll_file, args.key_file,
                                protect=not args.key_for_all_users)
        if not DEVICE_KEY:
            print(f"[key] no device key in {args.key_file} and no enrollment code - run INSTALL_SMARTLAB.ps1 again")
            sys.exit(3)
    http = requests.Session()
    http.headers["X-Device-Key"] = DEVICE_KEY
    rep = Reporter(args, http)
    if serve_whoami(args.device, DEVICE_KEY) is None:
        # Port taken = this agent already runs (the lab PCs' scheduled task re-starts it every minute,
        # so a second copy must quietly leave).
        print("Another Smart Lab agent is already running on this PC - exiting.")
        return
    print(f"Smart Lab PC agent for {args.device}. Reports usage; follows the portal's "
          f"lock / screen view / messages; in exam mode reports prohibited programs. Ctrl+C stops.")

    web = (args.web or derive_web(args.portal)).rstrip("/")
    if args.open_portal and open_portal_once_per_logon(web + "/login"):
        print("[portal] sign-in page opened for this Windows sign-in")
    mode, mirroring, last_report, last_lock = "NORMAL", False, 0.0, 0.0
    watching_share = False
    presenting = False
    maintenance_on = False
    cover_mode = None           # which full-screen cover is shown: None / "MAINTENANCE" / "LOCKED"
    share_viewer, down_since = False, 0.0
    signout_at, signed_out = None, False     # "Remove access": when this session is signed out
    started = time.monotonic()
    said_down = 0.0
    updater, update_state, healthy = None, {}, False
    update_due, update_after = None, 0.0
    if args.supervised:
        import agent_update as updater
        update_state = updater.read_state(AGENT_DIR)

    def report_violation(kind: str, detail: str) -> None:
        print(f"[exam] {kind}: {detail}")
        try:
            http.post(args.portal + "/equipment/violations", timeout=5,
                      json={"device_uid": args.device, "kind": kind, "detail": detail[:250], "os_user": logged_in_user()})
        except requests.RequestException:
            pass
    lockdown = None
    # 2026-11-03 lab: ADMIN-LAPTOP was left in Exam mode and its own agent closed VS Code, Docker and every
    # service window on each launch. The control PCs (the portal laptop, the lab engineer's PC) never lock
    # down, whatever the portal says: --no-lockdown, SMARTLAB_NO_LOCKDOWN=1, or a device id ADMIN / ENG.
    no_lockdown = (args.no_lockdown or os.environ.get("SMARTLAB_NO_LOCKDOWN") == "1"
                   or any(k in args.device.upper() for k in ("ADMIN", "_ENG")))
    if no_lockdown:
        print("Control PC: exam lockdown is OFF on this PC (programs are never closed here).")
    if WINDOWS and not no_lockdown:
        from exam_lockdown import Lockdown
        lockdown = Lockdown(report_violation)
    while True:
        now = time.monotonic()
        try:
            if now - last_report >= args.period:
                last_report = now
                mode = rep.report(mode == "LOCKED").get("mode", mode)
            r = http.get(args.portal + "/equipment/pc/poll", params={"device_uid": args.device}, timeout=5)
            if r.status_code in (401, 403):
                raise ValueError(f"the portal refused this PC's key (HTTP {r.status_code})")
            p = r.json()
        except (requests.RequestException, ValueError) as e:
            status_tray.write_state("offline")
            if now - said_down > 60:              # a PC off the network for a weekend must not fill its log
                said_down = now
                print(f"[portal] unreachable: {e}")
            # Portal gone while a share fills the screen: free the PC; it re-opens when the portal is back.
            down_since = down_since or now
            if share_viewer and now - down_since > SHARE_OFFLINE_S:
                from notice import share_off
                share_off()
                share_viewer, watching_share = False, False
            time.sleep(POLL_S)
            continue
        down_since = 0.0
        if updater and not healthy:
            updater.mark_healthy(AGENT_DIR)       # this version reached the portal: agent_boot.py keeps it
            healthy = True
        # A newer signed agent on the portal: taken only while nothing on this PC depends on the agent,
        # at a random moment so that the whole lab does not download in the same second.
        if updater and updater.wanted(update_state, (p.get("agent_bundle") or {}).get("seq")) and now >= update_after \
                and p.get("mode", "NORMAL") == "NORMAL" and not (mirroring or presenting or watching_share or share_viewer):
            if update_due is None:
                update_due = now + random.uniform(1, 45)
            elif now >= update_due:
                update_due = None
                try:
                    b = http.get(args.portal + "/equipment/pc/agent-bundle", timeout=30).json()
                    seq = updater.apply_bundle(AGENT_DIR, b)
                except (requests.RequestException, ValueError, KeyError, OSError, updater.BundleRefused) as e:
                    print(f"[update] not installed: {e}")
                    update_after = now + 600
                else:
                    # The new files are in place: nothing may stop this restart, not even a failing log.
                    try:
                        print(f"[update] bundle {seq} installed, restarting", flush=True)
                    except OSError:
                        pass
                    os._exit(updater.EXIT_UPDATED)

        exam = p.get("exam") or {}
        if lockdown is not None:
            if exam.get("lockdown"):
                if not lockdown.active:
                    popup("Exam mode enabled", "All programs are being closed. Only the exam page opens now - "
                          "other programs, windows and tabs are closed and reported to lab staff.", kind="exam")
                lockdown.enter(exam.get("url") or web + "/")          # no exam page given: the portal
                lockdown.check()
            elif lockdown.active:
                lockdown.leave()
                popup("Exam mode ended", "You can use this PC normally again.", kind="ok")
        # Full-screen cover: MAINTENANCE, and LOCKED too (2026-11-04: Windows lock (Win+L) can be turned
        # off by the university's policy, so "Remove access" also covers the screen until access is given).
        want = "MAINTENANCE" if p.get("mode") == "MAINTENANCE" else None    # LOCKED: countdown + sign-out instead
        maint = want is not None
        if no_lockdown:              # control PCs (portal laptop, lab engineer) are never covered
            want = None
        if WINDOWS and want != cover_mode:
            try:
                from notice import cover
                if cover_mode is not None:
                    cover(False)
                if want == "MAINTENANCE":
                    cover(True)
                elif want == "LOCKED":
                    cover(True, title="Access removed",
                          text="Lab staff removed access to this PC. Please ask the lab engineer.")
            except Exception as e:
                print(f"[cover] failed: {e}")
            cover_mode = want
        maintenance_on = maint
        if WINDOWS and maint:
            for proc in psutil.process_iter(["name"]):           # no Task Manager behind the cover
                if (proc.info.get("name") or "").lower() == "taskmgr.exe":
                    try:
                        proc.kill()
                    except psutil.Error:
                        pass
        new_mode = p.get("mode", "NORMAL")
        if new_mode != mode:
            print(f"[mode] {mode} -> {new_mode}")
            if mode == "LOCKED":
                if WINDOWS:
                    from notice import clear as clear_cards
                    clear_cards("warn")      # the sign-out countdown, if it is still on the screen
                popup("Access given", "Lab staff gave this PC access again. Welcome back!", kind="ok")
            mode = new_mode
        if mode == "LOCKED" and not no_lockdown:
            if signout_at is None:       # access removed (or the PC signed in again while still removed)
                grace = 2.0 if now - started < 60 else SIGNOUT_GRACE_S      # signed in again while removed: 2 s
                signout_at = now + grace
                print(f"[access] removed - signing out in {grace:.0f} s")
                popup("Access removed", f"Lab staff removed access to this PC. This session signs out in "
                      f"{grace:.0f} seconds - save your work now.", kind="warn", countdown=int(grace))
            if now - last_lock >= POLL_S:
                last_lock = now
                lock_pc()                # where Win+L is allowed it locks at once
            if now >= signout_at and not signed_out:
                signed_out = sign_out()
                print(f"[access] sign-out {'started' if signed_out else 'FAILED'}")
        else:
            signout_at, signed_out = None, False
        if p.get("clear_messages") and WINDOWS:
            from notice import clear as clear_cards
            clear_cards("message")
        m = p.get("message")
        if m and first_time(m.get("id")):
            popup("Message from lab staff", m["text"], kind="message", sender=m.get("from"),
                  expires=int(m.get("expires_s") or 0))
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
            native = WINDOWS and not no_lockdown and not p.get("broadcast_capture") and not (lockdown and lockdown.active)
            if native:
                from notice import can_show_share
                native = can_show_share()
            if not native:
                popup(f"{b.get('by') or 'Lab staff'} is sharing their screen",
                      (f"\u201c{b['title']}\u201d - " if b.get("title") else "") + "it opens in your browser now.",
                      kind="share", sender=b.get("by"))
            # 2026-11-03: a watch-only link (this PC's device key), so the PC does not ask for a portal
            # sign-in again; an older portal without it: the plain page as before.
            share = web + "/share"
            try:
                r = http.get(args.portal + "/equipment/pc/watch-token", timeout=5)
                if r.status_code == 200 and r.json().get("token"):
                    share += "?t=" + r.json()["token"]
            except (requests.RequestException, ValueError):
                pass
            if native:                   # 2026-11-04: full screen above everything, no browser needed
                from notice import share_on
                share_on(share_fetcher(DEVICE_KEY, args.portal), f"{b.get('by') or 'Lab staff'} is sharing their screen")
                share_viewer = True
            else:
                open_share_page(share)
        elif watching_share and not b.get("active"):
            print("[share] presentation ended")
            if share_viewer:
                from notice import share_off
                share_off()
                share_viewer = False
        watching_share = bool(b.get("active"))
        if bool(p.get("broadcast_capture")) != presenting:
            presenting = bool(p.get("broadcast_capture"))
            if presenting:
                popup("You are presenting", "Your screen is now being shared from this PC (approved by lab staff).", kind="share")
        if p.get("broadcast_capture"):           # this PC presents: the master PC, or a student's accepted share
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
        status_tray.write_state("viewed" if watched else "connected")
        if watched and not mirroring:
            popup("Your screen is being viewed", "Lab staff are viewing this screen from the Smart Lab portal.", kind="view")
        elif mirroring and not watched:
            print("[screen] viewing stopped")
        mirroring = watched
        if not mirroring:
            # exam lockdown: the 1 s loop (as LOCKED), so another program is closed within ~1 s
            idle_wait(http, args, "LOCKED" if (lockdown is not None and lockdown.active) or maintenance_on else mode,
                      last_report)
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
