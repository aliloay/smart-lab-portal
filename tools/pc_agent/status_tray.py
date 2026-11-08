"""
A small icon in the notification area, so the person at a lab PC can see that the Smart Lab agent is running and when
the screen is being viewed (2026-11-07). It reads the status file the agent writes and has no controls. Windows only;
anywhere else, or if the shell refuses the icon, the agent simply carries on without it.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time

STATUS_FILE = os.path.join(os.environ.get("TEMP", "."), "smartlab_status.txt")
TEXT = {"connected": "Smart Lab agent: running, connected to the portal",
        "offline": "Smart Lab agent: running, waiting for the portal",
        "viewed": "Smart Lab agent: lab staff are viewing this screen",
        "starting": "Smart Lab agent: starting"}
# Stock Windows icons: information, warning, and the "application" icon while starting.
ICON = {"connected": 32516, "offline": 32515, "viewed": 32515, "starting": 32512}


def tooltip(state: str, device: str) -> str:
    """Windows keeps at most 127 characters of a tooltip."""
    return f"{TEXT.get(state, TEXT['starting'])} ({device})"[:127]


def read_state(path: str = STATUS_FILE) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            state = f.read().strip()
    except OSError:
        return "starting"
    return state if state in TEXT else "starting"


def write_state(state: str, path: str = STATUS_FILE) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(state)
        os.replace(tmp, path)
    except OSError:
        pass                     # the indicator must never be able to stop the agent


def _run(device: str, stop: threading.Event) -> None:
    from ctypes import wintypes as w

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT),
                    ("uCallbackMessage", w.UINT), ("hIcon", w.HICON), ("szTip", w.WCHAR * 128)]

    user32, shell32 = ctypes.WinDLL("user32"), ctypes.WinDLL("shell32")
    user32.CreateWindowExW.restype = w.HWND
    user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD] + [ctypes.c_int] * 4 + \
        [w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user32.LoadIconW.restype = w.HICON
    user32.LoadIconW.argtypes = [w.HINSTANCE, w.LPCWSTR]
    shell32.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    hwnd = user32.CreateWindowExW(0, "STATIC", "SmartLabStatus", 0, 0, 0, 0, 0, None, None, None, None)
    if not hwnd:
        return
    nid = NOTIFYICONDATAW()
    nid.cbSize, nid.hWnd, nid.uID, nid.uFlags = ctypes.sizeof(NOTIFYICONDATAW), hwnd, 1, 0x2 | 0x4   # NIF_ICON | NIF_TIP
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    shown = None
    while not stop.is_set():
        state = read_state()
        nid.hIcon = user32.LoadIconW(None, ctypes.cast(ICON.get(state, 32512), w.LPCWSTR))
        nid.szTip = tooltip(state, device)
        # Modify fails after Explorer restarts or before the taskbar exists at sign-in: add it (again) then.
        if not shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)):
            shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        shown = state
        stop.wait(3)
    if shown is not None:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))


def start(device: str, stop: threading.Event) -> threading.Thread | None:
    if sys.platform != "win32":
        return None

    def guarded() -> None:
        try:
            _run(device, stop)
        except Exception as e:   # noqa: BLE001 - a failed icon is logged and nothing else happens
            print(time.strftime("%Y-%m-%d %H:%M:%S"), f"[tray] not shown: {e}", flush=True)
    t = threading.Thread(target=guarded, daemon=True)
    t.start()
    return t
