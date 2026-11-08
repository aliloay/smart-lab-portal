---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_masking.py"
source_hash: "c719dad56fc9b6c426db5645ae36a248265357ef357574b418d907a92f36a08c"
generated: true
updated: "2026-11-04T00:02:39+02:00"
redactions: ["rtsp-credentials"]
---
> Read-only mirror of `tools/security_vision/test_masking.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_security_vision.py]] - tests

```py
"""Camera credentials never reach logs (2026-10-14)."""
from security_vision import masked


def test_rtsp_user_and_password_are_masked():
    out = masked("[REDACTED:rtsp-credentials]192.168.1.155:554/stream2")
    assert "camuser" not in out and "s3cr" not in out
    assert out == "rtsp://***@192.168.1.155:554/stream2"


def test_sources_without_credentials_are_unchanged():
    assert masked(0) == "0"
    assert masked("rtsp://192.168.1.155:554/stream2") == "rtsp://192.168.1.155:554/stream2"
    assert masked("recordings/clip.mp4") == "recordings/clip.mp4"

```
