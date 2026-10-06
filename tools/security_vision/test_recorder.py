"""
Recorder (recorder.py) without a camera: a tiny Python script stands in for
FFmpeg (writes the output file, stops cleanly on "q").

    py -m pytest test_recorder.py -q
"""
import json
import os
import sys
import time

import recorder
from recorder import Recorder

FAKE = r'''
import sys
out = sys.argv[-1]
with open(out, "wb") as f:
    f.write(b"\x00" * 1000)
    f.flush()
    sys.stdin.read(1)          # waits for "q" (or the pipe closing)
'''


def fake_command(tmp_path):
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(FAKE)

    def cmd(ffmpeg, source, out, max_s):
        return [sys.executable, str(script), out]
    return cmd


def make(tmp_path, **kw):
    return Recorder("SECCAM_LAB01", "rtsp://cam/stream1", str(tmp_path / "rec"), ffmpeg="ffmpeg",
                    command=fake_command(tmp_path), **kw)


def test_start_stop_writes_file_and_metadata(tmp_path):
    r = make(tmp_path)
    s = r.start("Admin")
    assert s["ok"] and recorder.NAME_RE.match(s["file"])
    assert r.status()["recording"] and r.status()["started_by"] == "Admin"
    assert not r.start("Admin")["ok"]                      # one at a time
    time.sleep(0.5)
    done = r.stop("Admin")
    assert done["ok"] and done["size_bytes"] == 1000
    meta = json.loads((tmp_path / "rec" / (s["file"][:-4] + ".json")).read_text())
    assert meta["stop_reason"] == "stopped" and meta["stopped_by"] == "Admin" and meta["duration_s"] >= 0.4
    items = r.list()
    assert [i["file"] for i in items] == [s["file"]] and not items[0]["recording"]
    assert not r.stop()["ok"]


def test_refuses_without_ffmpeg_or_disk_space(tmp_path):
    r = Recorder("SECCAM_LAB01", "x", str(tmp_path / "rec"), ffmpeg="", command=fake_command(tmp_path))
    r.ffmpeg = None
    assert "FFmpeg" in r.start()["error"]
    big = make(tmp_path, min_free_gb=10 ** 9)
    assert "GB free" in big.start()["error"]


def test_a_recording_that_ends_by_itself_is_closed(tmp_path):
    r = make(tmp_path)
    s = r.start()
    r._proc.stdin.close()                                  # stream ends: the stand-in exits
    r._proc.wait(timeout=5)
    st = r.status()
    assert not st["recording"]
    meta = json.loads((tmp_path / "rec" / (s["file"][:-4] + ".json")).read_text())
    assert meta["stop_reason"] == "stream_ended"


def test_only_recording_names_are_served(tmp_path):
    r = make(tmp_path)
    s = r.start(); r.stop()
    assert r.path_of(s["file"]) and r.path_of("../security_vision.py") is None
    assert r.path_of(s["file"][:-4] + ".json") is None
    (tmp_path / "rec" / "notes.mp4").write_bytes(b"x")    # not a recording name: not listed
    assert [i["file"] for i in r.list()] == [s["file"]]


def test_ffmpeg_command_copies_video_and_converts_audio():
    c = recorder.ffmpeg_command("ffmpeg", "rtsp://cam/stream1", "out.mp4", 3600)
    assert c[c.index("-c:v") + 1] == "copy" and c[c.index("-c:a") + 1] == "aac"
    assert c[c.index("-rtsp_transport") + 1] == "tcp" and "-nostdin" not in c
    assert "+frag_keyframe" in c[c.index("-movflags") + 1] and c[c.index("-t") + 1] == "3600"
