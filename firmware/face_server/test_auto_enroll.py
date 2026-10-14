"""Automatic enrolment and the single-pass /enroll (2026-10-14). Synthetic inputs only - no photos of
people, nothing written to the real dataset (the store step is replaced). Run in firmware/face_server:
    py -m pytest -q test_auto_enroll.py test_enroll_quality.py"""
import numpy as np
import pytest

import face_server as fs

KEY = {"X-Device-Key": fs.DEVICE_KEY}


def unit(seed):
    v = np.random.default_rng(seed).normal(size=128)
    return v / np.linalg.norm(v)


def look(x=200.0, feat=None, n=1):
    row = np.zeros(15, dtype=np.float32)
    row[:4] = (x, 120, 160, 200)                       # a 160x200 face
    return {"row": row, "n": n, "aligned": np.zeros((112, 112, 3), np.uint8),
            "feat": unit(1) if feat is None else feat, "name": None, "score": None}


@pytest.fixture
def env(monkeypatch, tmp_path):
    saved = []
    monkeypatch.setattr(fs, "DATASET_DIR", str(tmp_path / "dataset"))
    monkeypatch.setattr(fs, "_store_sample", lambda name, img, gray, box, al, feat:
                        (saved.append((name, feat)), fs._last_sample_feat.__setitem__(name, feat), len(saved) - 1)[2])
    monkeypatch.setattr(fs, "templates", {})
    monkeypatch.setattr(fs, "_last_sample_feat", {})
    monkeypatch.setattr(fs, "enroll_quality", lambda g, n, f=None, last=None:
                        "more than one face" if n > 1 else
                        ("same as the last photo" if f is not None and last is not None and float(np.dot(f, last)) > 0.97 else None))
    clock = {"t": 1000.0}
    monkeypatch.setattr(fs.time, "time", lambda: clock["t"])
    c = fs.app.test_client()
    return c, saved, clock


def frame():
    return np.zeros((480, 640, 3), np.uint8), np.zeros((480, 640), np.uint8)


def feed(clock, lk, dt=0.15):
    clock["t"] += dt
    img, gray = frame()
    with fs._auto_lock:
        fs._auto_consider(img, gray, lk)


def test_device_key_required(env):
    c, _, _ = env
    assert c.post("/enroll/auto?name=USER5").status_code == 403


def test_steady_sharp_frames_are_saved_automatically_until_the_target(env):
    c, saved, clock = env
    assert c.post("/enroll/auto?name=USER5&target=3", headers=KEY).get_json()["active"]
    for i in range(40):
        feed(clock, look(feat=unit(100 + i)))         # steady face, a different look every frame
    st = c.get("/enroll/auto", headers=KEY).get_json()
    assert st["saved"] == 3 and not st["active"] and st["ended"] == "target reached"
    assert len(saved) == 3 and all(n == "USER5" for n, _ in saved)


def test_a_moving_face_is_not_saved(env):
    c, saved, clock = env
    c.post("/enroll/auto?name=USER5&target=3", headers=KEY)
    for i in range(20):
        feed(clock, look(x=200.0 + 30 * (i % 2), feat=unit(100 + i)))   # 30 px back and forth: moving
    assert saved == [] and c.get("/enroll/auto", headers=KEY).get_json()["hint"] == "hold still"


def test_samples_are_spaced_and_repeats_refused(env):
    c, saved, clock = env
    c.post("/enroll/auto?name=USER5&target=10", headers=KEY)
    same = unit(7)
    for _ in range(30):
        feed(clock, look(feat=same))                  # the same look every frame
    assert len(saved) == 1                            # the rest are "same as the last photo"


def test_two_faces_never_saved(env):
    c, saved, clock = env
    c.post("/enroll/auto?name=USER5&target=3", headers=KEY)
    for i in range(10):
        feed(clock, look(feat=unit(100 + i), n=2))
    assert saved == []


def test_another_enrolled_person_is_refused(env, monkeypatch):
    c, saved, clock = env
    other = unit(42)
    monkeypatch.setattr(fs, "templates", {"USER1": other})
    c.post("/enroll/auto?name=USER5&target=3", headers=KEY)
    for i in range(10):
        f = other + 0.05 * unit(200 + i); f /= np.linalg.norm(f)    # clearly USER1
        feed(clock, look(feat=f))
    assert saved == []
    assert "looks like USER1" in c.get("/enroll/auto", headers=KEY).get_json()["hint"]


def test_session_stops_when_nobody_watches(env):
    c, saved, clock = env
    c.post("/enroll/auto?name=USER5&target=3", headers=KEY)
    clock["t"] += fs.AUTO_IDLE_S + 1
    feed(clock, look())
    st = c.get("/enroll/auto", headers=KEY).get_json()
    assert not st["active"] and saved == []


def test_stop(env):
    c, _, _ = env
    c.post("/enroll/auto?name=USER5", headers=KEY)
    assert c.delete("/enroll/auto", headers=KEY).get_json()["active"] is False


def test_identity_check_does_not_block_the_same_person():
    t = unit(5)
    fs.templates["ZZ_SELF"] = t
    try:
        assert fs._identity_check("ZZ_SELF", t) is None
    finally:
        fs.templates.pop("ZZ_SELF", None)


@pytest.mark.skipif(fs.ENGINE != "sface", reason="SFace models not present")
def test_one_detector_pass_gives_the_same_face_as_before():
    rng = np.random.default_rng(3)
    img = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
    row, n = fs.yunet_faces(img)
    assert (row is None) == (fs.yunet_face(img) is None) and n == fs.yunet_count(img)
