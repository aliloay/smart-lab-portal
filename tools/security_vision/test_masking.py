"""Camera credentials never reach logs (2026-10-14)."""
from security_vision import masked


def test_rtsp_user_and_password_are_masked():
    out = masked("rtsp://camuser:s3cr%40t@192.168.1.155:554/stream2")
    assert "camuser" not in out and "s3cr" not in out
    assert out == "rtsp://***@192.168.1.155:554/stream2"


def test_sources_without_credentials_are_unchanged():
    assert masked(0) == "0"
    assert masked("rtsp://192.168.1.155:554/stream2") == "rtsp://192.168.1.155:554/stream2"
    assert masked("recordings/clip.mp4") == "recordings/clip.mp4"
