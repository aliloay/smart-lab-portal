"""
Exam lockdown on a lab PC (2026-10-21). While staff hold the PC in EXAM with an exam page:
  * on entry: every program with a window is closed (asked politely first, then ended), and the exam
    page opens in Chrome KIOSK mode - one full-screen window, no address bar, no tab strip - in its own
    browser profile, so it is a separate Chrome process from any other;
  * every check (~1 s): a window of any other program, a second window of the exam browser, Task
    Manager, a File Explorer window, or another Chrome is closed at once and reported to the portal
    (staff get an instant pop-up). The exam window itself is re-opened if it was closed.
  * on exit (mode back to NORMAL): the exam browser is closed.

Honest limit: kiosk Chrome cannot stop every keyboard shortcut and runs in the student's own session;
a fully sealed exam needs Windows Assigned Access / Safe Exam Browser (a lab IT decision). Windows-only.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
import time
from ctypes import wintypes
from typing import Callable, Optional

import psutil

# Programs that may keep a window during an exam. Everything else that shows a window is closed.
ALLOWED = {"explorer.exe",                     # the desktop and taskbar (folder windows are closed by class)
           "python.exe", "pythonw.exe", "py.exe", "pyw.exe",   # this agent (its notices, countdown)
           "conhost.exe", "dwm.exe", "logonui.exe", "lockapp.exe", "searchui.exe", "shellexperiencehost.exe",
           "startmenuexperiencehost.exe", "textinputhost.exe", "ctfmon.exe", "sihost.exe", "applicationframehost.exe"}
FOLDER_CLASSES = {"CabinetWClass", "ExploreWClass"}     # File Explorer windows (explorer.exe, but not allowed)
GRACE_S = 2.0                                            # WM_CLOSE first; ended if still there after this

WM_CLOSE = 0x0010


def find_chrome() -> Optional[str]:
    """Chrome, else Microsoft Edge (on every Windows 10/11 PC; same kiosk switches)."""
    for rel in (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe")):
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                p = os.path.join(base, *rel)
                if os.path.isfile(p):
                    return p
    return None


def visible_windows() -> list[tuple[int, int, str, str]]:
    """(hwnd, pid, class, title) of every visible top-level window with a title."""
    u = ctypes.windll.user32
    out = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) > 0:
            t = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(hwnd, t, 256)
            c = ctypes.create_unicode_buffer(128)
            u.GetClassNameW(hwnd, c, 128)
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((int(hwnd), int(pid.value), c.value, t.value))
        return True
    u.EnumWindows(proc(cb), 0)
    return out


class Lockdown:
    def __init__(self, report: Callable[[str, str], None], windows=visible_windows, launcher=subprocess.Popen,
                 chrome: Optional[str] = None, my_pid: Optional[int] = None):
        self.report, self.windows, self.launcher = report, windows, launcher
        self.chrome = chrome
        self.my_pid = my_pid or os.getpid()
        self.url: Optional[str] = None
        self.proc = None                       # the kiosk Chrome we started
        self.kiosk_hwnd: Optional[int] = None
        self.pending: dict[int, float] = {}    # pid -> when WM_CLOSE was sent

    @property
    def active(self) -> bool:
        return self.url is not None

    # ---------------------------------------------------------------- helpers ---
    def _ours(self) -> set[int]:
        """PIDs of the exam browser (its process tree) and of this agent."""
        pids = {self.my_pid}
        # 2026-11-04 lab: the agent ran in a PowerShell window; the lockdown closed that window and the
        # agent died with it. The programs that host this agent (its parent chain) are never closed.
        try:
            pids |= {p.pid for p in psutil.Process(self.my_pid).parents()}
        except psutil.Error:
            pass
        if self.proc is not None:
            try:
                root = psutil.Process(self.proc.pid)
                pids |= {root.pid} | {c.pid for c in root.children(recursive=True)}
            except psutil.Error:
                pass
        return pids

    @staticmethod
    def _name(pid: int) -> str:
        try:
            return psutil.Process(pid).name().lower()
        except psutil.Error:
            return ""

    def _close(self, hwnd: int, pid: int, why: str, now: float) -> None:
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        if pid not in self.pending:
            self.pending[pid] = now
            self.report("EXAM_LOCKDOWN", why)

    def _launch(self) -> None:
        exe = self.chrome or find_chrome()
        if not exe:
            self.report("EXAM_LOCKDOWN", "Chrome not found on this PC - the exam page could not be opened")
            return
        profile = os.path.join(tempfile.gettempdir(), "smartlab_exam_profile")
        # --app: a window with no tab strip and no address bar; a new tab (Ctrl+T / Ctrl+N) opens as a
        # SEPARATE window, which check() closes and reports. --kiosk: full screen, no way to leave it.
        self.proc = self.launcher([exe, "--kiosk", f"--app={self.url}", f"--user-data-dir={profile}", "--no-first-run",
                                   "--no-default-browser-check", "--disable-pinch", "--overscroll-history-navigation=0"])
        self.kiosk_hwnd = None

    # ------------------------------------------------------------------ public ---
    def enter(self, url: str) -> None:
        if self.url == url and self.proc is not None and self.proc.poll() is None:
            return
        self.leave(quiet=True)
        self.url = url
        now = time.monotonic()
        for hwnd, pid, cls, title in self.windows():                     # close everything first
            if self._name(pid) not in ALLOWED or cls in FOLDER_CLASSES:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                self.pending.setdefault(pid, now)
        self._launch()
        self.report("EXAM_STARTED", f"exam page opened in kiosk mode: {url}")

    def leave(self, quiet: bool = False) -> None:
        if self.proc is not None:
            try:
                root = psutil.Process(self.proc.pid)
                for p in root.children(recursive=True) + [root]:
                    p.kill()
            except psutil.Error:
                pass
        if self.url and not quiet:
            self.report("EXAM_ENDED", "exam lockdown ended - the exam browser was closed")
        self.url, self.proc, self.kiosk_hwnd = None, None, None
        self.pending.clear()

    def check(self) -> None:
        """One enforcement pass: close / end what is not allowed, keep exactly one exam window."""
        if not self.active:
            return
        now = time.monotonic()
        if self.proc is None or self.proc.poll() is not None:            # exam window closed: back it comes
            self.report("EXAM_LOCKDOWN", "the exam window was closed - it was opened again")
            self._launch()
            # no return: other programs are still closed in this same pass (a failed launch never
            # leaves the PC unenforced)
        ours = self._ours()
        exam_windows = []
        for hwnd, pid, cls, title in self.windows():
            name = self._name(pid)
            if pid in ours and name in ("chrome.exe", "msedge.exe"):
                exam_windows.append(hwnd)
                continue
            if pid in ours:
                continue
            if name not in ALLOWED or cls in FOLDER_CLASSES:
                what = "Task Manager" if name == "taskmgr.exe" else "a File Explorer window" if cls in FOLDER_CLASSES \
                    else "another Chrome window" if name == "chrome.exe" else name
                self._close(hwnd, pid, f"closed {what}" + (f" ({title[:60]})" if title else ""), now)
        if self.kiosk_hwnd not in exam_windows:
            self.kiosk_hwnd = exam_windows[0] if exam_windows else None
        for hwnd in exam_windows:                                       # a second exam-browser window / tab window
            if hwnd != self.kiosk_hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                self.report("EXAM_LOCKDOWN", "closed a second window of the exam browser")
        for pid, since in list(self.pending.items()):                  # still there after the grace: end it
            if now - since < GRACE_S:
                continue
            self.pending.pop(pid, None)
            if pid in ours or self._name(pid) in ALLOWED:
                continue
            try:
                psutil.Process(pid).kill()
            except psutil.Error:
                pass
