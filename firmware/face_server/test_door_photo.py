"""Door photo picker (2026-11-21). Synthetic images only - no photos of people; everything is written to tmp_path.
Run in firmware/face_server:  py -m pytest -q test_door_photo.py"""
import json
import os

import cv2
import numpy as np
import pytest

import face_server as fs

KEY = {"X-Device-Key": fs.DEVICE_KEY}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(fs, "PORTRAIT_DIR", str(tmp_path / "portraits"))
    monkeypatch.setattr(fs, "_portrait_cache", {})
    # face detection is the real Haar cascade's job; here a "face" is any image whose top-left pixel is white
    monkeypatch.setattr(fs, "largest_face_box", lambda gray: (10, 10, 50, 50) if gray[0, 0] > 200 else None)
    return fs.app.test_client()


def img(face=True, shade=90):
    a = np.full((120, 160, 3), shade, np.uint8)
    if face:
        a[0, 0] = 255
    return a


def jpg(a):
    return cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 100])[1].tobytes()


def test_enrollment_keeps_the_best_candidates(env):
    for area in range(1, 12):
        fs.keep_best_portrait("USER9", img(shade=area * 10), area * 100)
    info = env.get("/portrait/USER9/info", headers=KEY).get_json()
    assert info["has_photo"] and info["source"] == "enrollment"
    assert len(info["candidates"]) == fs.PORTRAIT_CANDIDATES
    assert info["candidates"][0] == "1100"                    # largest face first


def test_choose_a_candidate_and_enrollment_never_replaces_it(env):
    fs.keep_best_portrait("USER9", img(shade=40), 400)
    fs.keep_best_portrait("USER9", img(shade=80), 800)
    r = env.post("/portrait/USER9/choose", headers=KEY, json={"from": "candidate", "candidate": "400"})
    assert r.status_code == 200, r.get_json()
    meta = json.load(open(os.path.join(fs.PORTRAIT_DIR, "USER9.json")))
    assert meta["source"] == "chosen"
    fs.keep_best_portrait("USER9", img(shade=200), 99999)    # a bigger face later: still the chosen one
    assert json.load(open(os.path.join(fs.PORTRAIT_DIR, "USER9.json")))["source"] == "chosen"


def test_upload_needs_a_face_and_the_key(env):
    assert env.post("/portrait/USER9/upload", data=jpg(img()), headers={"X-Device-Key": "wrong"}).status_code == 403
    assert env.post("/portrait/USER9/upload", data=jpg(img(face=False)), headers=KEY).status_code == 409
    assert env.post("/portrait/USER9/upload", data=b"not an image", headers=KEY).status_code == 400
    r = env.post("/portrait/USER9/upload", data=jpg(img()), headers=KEY)
    assert r.status_code == 200
    assert env.get("/portrait/USER9.jpg", headers=KEY).status_code == 200


def test_camera_capture_refuses_without_a_live_frame(env, monkeypatch):
    monkeypatch.setitem(fs._preview, "jpeg", None)
    assert env.post("/portrait/USER9/choose", headers=KEY, json={"from": "camera"}).status_code == 409


def test_bad_names_are_refused(env):
    assert env.get("/portrait/..%2Fx/info", headers=KEY).status_code in (400, 404)
    assert env.post("/portrait/USER9/choose", headers=KEY, json={"from": "candidate", "candidate": "../x"}).status_code == 404


def test_camera_capture_uses_the_last_frame_with_a_face(env, monkeypatch):
    monkeypatch.setitem(fs._last_face_frame, "jpeg", jpg(img(face=False)))   # the door's detector saw a face here
    monkeypatch.setitem(fs._last_face_frame, "at", fs.time.time())
    r = env.post("/portrait/USER9/choose", headers=KEY, json={"from": "camera"})
    assert r.status_code == 200, r.get_json()
    monkeypatch.setitem(fs._last_face_frame, "at", fs.time.time() - 60)       # too old, and no live frame
    monkeypatch.setitem(fs._preview, "jpeg", None)
    assert env.post("/portrait/USER9/choose", headers=KEY, json={"from": "camera"}).status_code == 409


def test_training_photos_are_offered_and_can_be_chosen(env, monkeypatch, tmp_path):
    monkeypatch.setattr(fs, "DATASET_DIR", str(tmp_path / "dataset"))
    monkeypatch.setattr(fs, "SFACE_DATASET_DIR", str(tmp_path / "dataset_sface"))
    os.makedirs(tmp_path / "dataset" / "USER9")
    os.makedirs(tmp_path / "dataset_sface" / "USER9")
    cv2.imwrite(str(tmp_path / "dataset" / "USER9" / "3.jpg"), np.full((200, 200), 120, np.uint8))
    cv2.imwrite(str(tmp_path / "dataset_sface" / "USER9" / "7.png"), np.full((112, 112, 3), 90, np.uint8))
    info = env.get("/portrait/USER9/info", headers=KEY).get_json()
    assert info["training"] == ["s7", "g3"]
    assert env.get("/portrait/USER9/candidate/s7.jpg", headers=KEY).status_code == 200
    r = env.post("/portrait/USER9/choose", headers=KEY, json={"from": "candidate", "candidate": "g3"})
    assert r.status_code == 200, r.get_json()
    meta = json.load(open(os.path.join(fs.PORTRAIT_DIR, "USER9.json")))
    assert meta["source"] == "chosen" and "grey" in meta["how"]
    assert env.get("/portrait/USER9/candidate/x9.jpg", headers=KEY).status_code == 400
