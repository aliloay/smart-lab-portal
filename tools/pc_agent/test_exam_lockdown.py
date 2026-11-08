"""Exam lockdown decisions (2026-10-21), with fake windows / processes - no real program is touched."""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exam_lockdown as L                                   # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows window handling")


class FakeProc:
    def __init__(self, pid):
        self.pid = pid
        self.alive = True

    def poll(self):
        return None if self.alive else 0


def make(monkeypatch, windows, names):
    reports, launched = [], []
    monkeypatch.setattr(L.Lockdown, "_name", staticmethod(lambda pid: names.get(pid, "")))
    monkeypatch.setattr(L.Lockdown, "_ours", lambda self: {9000, 777} | ({self.proc.pid} if self.proc else set()))
    monkeypatch.setattr(L.ctypes.windll.user32, "PostMessageW", lambda *a: 1, raising=False)
    lk = L.Lockdown(lambda k, d: reports.append((k, d)), windows=lambda: windows,
                    launcher=lambda args: launched.append(args) or FakeProc(777), chrome="C:/chrome.exe", my_pid=9000)
    return lk, reports, launched


def test_entering_closes_other_programs_and_opens_one_kiosk_window(monkeypatch):
    wins = [(1, 100, "Notepad", "notes.txt"), (2, 200, "Shell_TrayWnd", "taskbar"), (3, 300, "CabinetWClass", "Documents")]
    lk, reports, launched = make(monkeypatch, wins, {100: "notepad.exe", 200: "explorer.exe", 300: "explorer.exe"})
    lk.enter("https://exam.example/test")
    assert launched and launched[0][:3] == ["C:/chrome.exe", "--kiosk", "--app=https://exam.example/test"]
    assert set(lk.pending) == {100, 300}                         # notepad + the folder window, not the taskbar
    assert reports[-1][0] == "EXAM_STARTED"


def test_anything_else_is_closed_and_reported_at_once(monkeypatch):
    wins = []
    lk, reports, _ = make(monkeypatch, wins, {500: "taskmgr.exe", 600: "chrome.exe", 777: "chrome.exe"})
    lk.enter("https://exam.example/test")
    reports.clear()
    wins += [(10, 777, "Chrome_WidgetWin_1", "Exam"), (11, 500, "TaskManagerWindow", "Task Manager"),
             (12, 600, "Chrome_WidgetWin_1", "YouTube")]
    lk.check()
    kinds = [d for k, d in reports if k == "EXAM_LOCKDOWN"]
    assert any("Task Manager" in d for d in kinds) and any("another Chrome window" in d for d in kinds)
    assert lk.kiosk_hwnd == 10
    lk.check()                                                   # the same program is reported once
    assert len([d for k, d in reports if k == "EXAM_LOCKDOWN"]) == 2


def test_second_exam_window_is_closed_and_a_closed_exam_window_comes_back(monkeypatch):
    wins = [(10, 777, "Chrome_WidgetWin_1", "Exam"), (13, 777, "Chrome_WidgetWin_1", "New Tab")]
    lk, reports, launched = make(monkeypatch, wins, {777: "chrome.exe"})
    lk.enter("https://exam.example/test")
    lk.check()
    assert ("EXAM_LOCKDOWN", "closed a second window of the exam browser") in reports
    lk.proc.alive = False                                        # student closed the exam window
    lk.check()
    assert len(launched) == 2 and ("EXAM_LOCKDOWN", "the exam window was closed - it was opened again") in reports


def test_leaving_ends_the_exam_browser(monkeypatch):
    lk, reports, _ = make(monkeypatch, [], {})
    killed = []
    monkeypatch.setattr(L.psutil, "Process", lambda pid: SimpleNamespace(children=lambda recursive: [], kill=lambda: killed.append(pid)))
    lk.enter("https://exam.example/test")
    lk.leave()
    assert killed == [777] and not lk.active and reports[-1][0] == "EXAM_ENDED"


def test_the_window_hosting_the_agent_is_never_closed(monkeypatch):
    """2026-11-04 lab: the agent ran in a PowerShell window; the lockdown closed it and the agent died."""
    import os as _os
    import psutil
    lk = L.Lockdown(lambda k, d: None, windows=lambda: [], launcher=lambda a: FakeProc(777), chrome="x", my_pid=_os.getpid())
    parent = psutil.Process(_os.getpid()).parent()
    assert parent is not None and parent.pid in lk._ours()


def test_a_failed_exam_window_still_closes_other_programs(monkeypatch):
    """No browser could be opened: other programs must still be closed in the same pass."""
    wins = [(1, 100, "Notepad", "notes.txt")]
    lk, reports, launched = make(monkeypatch, wins, {100: "notepad.exe"})
    lk.enter("https://exam.example/test")
    lk.pending.clear()
    lk.proc = None                                          # the exam window is gone
    lk.check()
    assert 100 in lk.pending                                # notepad still closed


def test_edge_is_used_when_chrome_is_missing(monkeypatch, tmp_path):
    edge = tmp_path / "Microsoft" / "Edge" / "Application"
    edge.mkdir(parents=True)
    (edge / "msedge.exe").write_text("")
    for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(v, str(tmp_path))
    assert L.find_chrome().endswith("msedge.exe")
