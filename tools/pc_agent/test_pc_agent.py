"""PC agent (2026-10-17): allowlisted actions refuse anything else; capture works with or without Pillow."""
import sys

import pytest

import pc_agent as a

WIN = sys.platform == "win32"


def test_unknown_actions_and_apps_are_refused():
    if not WIN:
        assert a.run_action({"action": "lock"})[0] is False
        return
    assert a.run_action({"action": "format_disk"}) == (False, "unknown action 'format_disk'")
    ok, why = a.run_action({"action": "open_app", "app": "regedit"})
    assert ok is False and "not configured" in why


@pytest.mark.skipif(not WIN, reason="Windows screen capture")
def test_monitors_are_real_pixels_and_primary_first():
    mons = a.monitors()
    assert mons and mons[0]["primary"] and all(m["width"] > 0 and m["height"] > 0 for m in mons)


@pytest.mark.skipif(not WIN, reason="Windows screen capture")
@pytest.mark.parametrize("monitor", [0, 1])
def test_capture_returns_a_downscaled_jpeg(monitor):
    j = a.grab_jpeg(monitor, 50)
    if j is None:
        pytest.skip("no capture backend (neither Pillow nor OpenCV) or the desktop is locked")
    assert j[:2] == b"\xff\xd8" and len(j) < 1_500_000          # the portal's frame limit


@pytest.mark.skipif(not WIN, reason="Windows GDI fallback")
def test_gdi_fallback_without_pillow(monkeypatch):
    pytest.importorskip("cv2")
    j = a._grab_gdi(a.monitors()[0]["bbox"], 60)
    assert j is not None and j[:2] == b"\xff\xd8"


def test_runs_on_python_3_8_for_windows_7():
    """Windows 7 lab PCs can run at most Python 3.8 (2026-10-21, old HP laptop as PC-01). 3.8 evaluates
    annotations at import: `str | None` / `list[dict]` crash there unless annotations are postponed."""
    import ast
    import pathlib
    src = pathlib.Path(a.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src, feature_version=(3, 8))          # 3.8 syntax only (no match, no except*)
    postponed = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                    and any(x.name == "annotations" for x in n.names) for n in tree.body)

    def new_style(ann):
        return any(isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr) or
                   isinstance(x, ast.Subscript) and isinstance(x.value, ast.Name)
                   and x.value.id in ("list", "dict", "tuple", "set", "type") for x in ast.walk(ann))
    anns = [n.returns for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.returns]
    anns += [x.annotation for n in ast.walk(tree) if isinstance(n, ast.arg) for x in [n] if x.annotation]
    anns += [n.annotation for n in ast.walk(tree) if isinstance(n, ast.AnnAssign)]
    bad = [ast.unparse(x) for x in anns if new_style(x)]
    assert postponed or not bad, f"annotations that crash Python 3.8: {bad}"


def test_whoami_answers_this_pc_with_a_proof_on_localhost_only():
    """Admin sign-in on this PC (2026-10-21): the portal page asks 127.0.0.1 which PC it is."""
    import hashlib
    import hmac
    import json as _j
    import urllib.request
    srv = a.serve_whoami("PC_01", "k-123", port=0)
    host, port = srv.server_address
    assert host == "127.0.0.1"
    try:
        r = _j.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/whoami?nonce={'ab' * 16}", timeout=3))
        want = hmac.new(hashlib.sha256(b"k-123").hexdigest().encode(), ("ab" * 16).encode(), hashlib.sha256).hexdigest()
        assert r == {"device_uid": "PC_01", "proof": want}
        with pytest.raises(Exception):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/whoami?nonce=../../x", timeout=3)
    finally:
        srv.shutdown()


def test_second_copy_exits_and_reports_carry_the_start_stamp(monkeypatch):
    """Invisible agent restarted every minute by a scheduled task (2026-10-21): only one copy may run,
    and each run is stamped so the portal sees a stop without a reboot."""
    first = a.serve_whoami("PC_01", "k", port=0)
    port = first.server_address[1]
    try:
        monkeypatch.setattr(a, "WHOAMI_PORT", port)
        assert a.serve_whoami("PC_01", "k", port=port) is None           # port busy -> None -> main() returns
    finally:
        first.shutdown()
    info = a.identity_info()
    assert info["agent_started"] == a.AGENT_STARTED and info["agent_version"] == "0.9"


def test_portal_opens_once_per_windows_sign_in(monkeypatch, tmp_path):
    """Lab PCs open the portal sign-in page at Windows sign-in - not again when the task restarts the agent."""
    from types import SimpleNamespace
    opened = []
    monkeypatch.setattr(a, "open_share_page", opened.append)
    monkeypatch.setenv("USERNAME", "student1")
    monkeypatch.setattr(a.psutil, "users", lambda: [SimpleNamespace(name="student1", started=1000.0)])
    assert a.open_portal_once_per_logon("http://p/login", str(tmp_path)) is True
    assert a.open_portal_once_per_logon("http://p/login", str(tmp_path)) is False      # agent restarted: no
    monkeypatch.setattr(a.psutil, "users", lambda: [SimpleNamespace(name="student1", started=2000.0)])
    assert a.open_portal_once_per_logon("http://p/login", str(tmp_path)) is True       # new sign-in: yes
    monkeypatch.setattr(a.psutil, "users", lambda: [])
    assert a.open_portal_once_per_logon("http://p/login", str(tmp_path)) is False      # nobody signed in
    assert opened == ["http://p/login", "http://p/login"]


def test_restart_and_shutdown_force_close_after_the_warning(monkeypatch):
    """PC-01 (2026-10-21): Restart closed the windows but never restarted - Windows 7 waits on programs that
    do not close. The command must carry /f, the 60 s warning and the message."""
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(a, "WINDOWS", True)
    monkeypatch.setattr(a.subprocess, "run", lambda args, **k: calls.append(args) or SimpleNamespace(returncode=0, stderr=""))
    shown = []
    monkeypatch.setattr(a, "countdown_window", lambda s, w: shown.append((s, w)))
    for act, flag in (("restart", "/r"), ("shutdown", "/s")):
        ok, msg = a.run_action({"action": act})
        assert ok and "60 s" in msg
        assert calls[-1][:5] == ["shutdown", flag, "/f", "/t", "60"] and "/c" in calls[-1]
    assert shown == [(60, "restart"), (60, "shut down")]                   # the 60 s countdown window
