---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_two_cameras.py"
source_hash: "969569377047cdfd822049882cd4e9eaf97ec87ced373fe1a19d0420c62fefe9"
generated: true
updated: "2026-11-04T00:02:39+02:00"
redactions: ["rtsp-credentials"]
---
> Read-only mirror of `tools/security_vision/test_two_cameras.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_security_vision.py]] - tests
- [[docs_camera-identity_TWO_CAMERAS.md]] - mentioned by docs

```py
"""Two-camera preparation (2026-10-14), software only - no camera hardware, no credentials.
Each camera is its own process (start_security_vision.bat <env file>); these check the parts that
must not collide between them. Simulated two-process runs are documented in
docs/camera-identity/TWO_CAMERAS.md (labelled simulated, not hardware proof)."""
import os
import re
import subprocess
import types

import security_vision as sv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def test_identity_log_file_is_per_camera(tmp_path, monkeypatch):
    monkeypatch.setattr(sv, "HERE", str(tmp_path))
    a = types.SimpleNamespace(args=types.SimpleNamespace(device="SECCAM_LAB01"))
    b = types.SimpleNamespace(args=types.SimpleNamespace(device="SECCAM_LAB02"))
    sv.Service._persist_identity(a, {"kind": "X", "label": "USER1"})
    sv.Service._persist_identity(b, {"kind": "X", "label": "USER2"})
    files = sorted(os.listdir(tmp_path / "recordings"))
    assert files == ["identity_log_SECCAM_LAB01.jsonl", "identity_log_SECCAM_LAB02.jsonl"]


def test_camera2_example_has_its_own_id_and_port_and_no_secret():
    txt = open(os.path.join(HERE, "camera2.env.example"), encoding="utf-8").read()
    vals = dict(re.findall(r"^set (\w+)=(.*)$", txt, re.M))
    assert vals["DEVICE"] == "SECCAM_LAB02" and vals["PORT"] == "5101" and vals["SOURCE"] == ""


def test_every_camera_env_file_is_git_ignored_but_the_examples_are_not():
    def ignored(p):
        return subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT).returncode == 0
    for f in ("camera.env", "camera2.env", "camera3.env"):
        assert ignored(f"tools/security_vision/{f}"), f
    assert not ignored("tools/security_vision/camera2.env.example")


def test_start_script_takes_the_env_file_and_guards_its_own_port():
    bat = open(os.path.join(HERE, "start_security_vision.bat"), encoding="utf-8").read()
    assert 'set "CAMFILE=%~1"' in bat and '127.0.0.1:%PORT% .*LISTENING' in bat
    assert "--port %PORT%" in bat and "--device %DEVICE%" in bat
    assert 'set "SECURITY_CAMERA_SOURCE=%SOURCE%"' in bat and "--source" not in bat   # never on the command line


def test_masked_hides_credentials_of_any_camera():
    assert sv.masked("[REDACTED:rtsp-credentials]10.0.0.9:554/stream2") == "rtsp://***@10.0.0.9:554/stream2"

```
