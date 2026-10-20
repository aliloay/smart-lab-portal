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
