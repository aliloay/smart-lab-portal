"""
Recorder (recorder.py) without a camera: a tiny Python script stands in for
FFmpeg - it writes parts named by strftime (like FFmpeg's segment muxer),
and stops cleanly on "q".

    py -m pytest test_recorder.py -q
"""
import json
import sys
import time

import recorder
from recorder import Recorder

FAKE = r'''
import sys, time
pattern, parts = sys.argv[-2], int(sys.argv[-1])
for i in range(parts):
    if i:
        time.sleep(1.1)                       # the next part starts a second later
    with open(time.strftime(pattern), "wb") as f:
        f.write(b"\x00" * 1000)
sys.stdin.read(1)                            # waits for "q" (or the pipe closing)
'''


def fake_command(tmp_path, parts=1):
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(FAKE)

    def cmd(ffmpeg, source, pattern, segment_s):
        return [sys.executable, str(script), pattern, str(parts)]
    return cmd


def make(tmp_path, parts=1, **kw):
    return Recorder("SECCAM_LAB01", "rtsp://cam/stream1", str(tmp_path / "rec"), ffmpeg="ffmpeg",
                    command=fake_command(tmp_path, parts), **kw)


def meta(tmp_path, name):
    return json.loads((tmp_path / "rec" / (name[:-4] + ".json")).read_text())


def test_start_stop_one_part(tmp_path):
    r = make(tmp_path)
    assert r.start("Admin")["ok"]
    assert not r.start("Admin")["ok"]                      # one at a time
    time.sleep(0.6)
    st = r.status()
    assert st["recording"] and st["started_by"] == "Admin" and st["parts"] == 1
    done = r.stop("Admin")
    assert done["ok"] and done["parts"] == 1 and done["size_bytes"] == 1000
    name = done["file"]
    assert recorder.NAME_RE.match(name)
    m = meta(tmp_path, name)
    assert (m["part"], m["parts"], m["stop_reason"], m["stopped_by"]) == (1, 1, "stopped", "Admin")
    assert [i["file"] for i in r.list()] == [name] and not r.list()[0]["recording"]
    assert not r.stop()["ok"]


def test_a_long_recording_is_split_into_parts_until_stop(tmp_path):
    r = make(tmp_path, parts=2)
    r.start("Admin")
    time.sleep(2.0)
    st = r.status()
    assert st["recording"] and st["parts"] == 2
    items = r.list()                                       # newest first
    assert [i["recording"] for i in items] == [True, False]   # only the part being written
    done = r.stop("Admin")
    assert done["parts"] == 2 and done["size_bytes"] == 2000
    first, second = sorted(i["file"] for i in r.list())
    m1, m2 = meta(tmp_path, first), meta(tmp_path, second)
    assert (m1["part"], m2["part"], m1["parts"]) == (1, 2, 2)
    assert m1["stopped_at"] == m2["started_at"]            # no gap between the parts
    assert m1["recording_started_at"] == m2["recording_started_at"]


def test_refuses_without_ffmpeg_or_disk_space(tmp_path):
    r = make(tmp_path)
    r.ffmpeg = None
    assert "FFmpeg" in r.start()["error"]
    big = make(tmp_path, min_free_gb=10 ** 9)
    assert "GB free" in big.start()["error"]


def test_a_recording_that_ends_by_itself_is_closed(tmp_path):
    r = make(tmp_path)
    r.start()
    time.sleep(0.5)
    r._proc.stdin.close()                                  # stream ends: the stand-in exits
    r._proc.wait(timeout=5)
    assert not r.status()["recording"]
    assert meta(tmp_path, r.list()[0]["file"])["stop_reason"] == "stream_ended"


def test_only_recording_names_are_served(tmp_path):
    r = make(tmp_path)
    r.start(); time.sleep(0.5)
    name = r.stop()["file"]
    assert r.path_of(name) and r.path_of("../security_vision.py") is None
    assert r.path_of(name[:-4] + ".json") is None
    (tmp_path / "rec" / "notes.mp4").write_bytes(b"x")    # not a recording name: not listed
    assert [i["file"] for i in r.list()] == [name]


def test_ffmpeg_command_splits_copies_video_and_converts_audio():
    c = recorder.ffmpeg_command("ffmpeg", "rtsp://cam/stream1", "out_%Y.mp4", 3600)
    assert c[c.index("-c:v") + 1] == "copy" and c[c.index("-c:a") + 1] == "aac"
    assert c[c.index("-f") + 1] == "segment" and c[c.index("-segment_time") + 1] == "3600"
    assert c[c.index("-strftime") + 1] == "1" and "-t" not in c and "-nostdin" not in c
    assert "+frag_keyframe" in c[c.index("-segment_format_options") + 1]
