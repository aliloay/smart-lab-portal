"""POST /detect - one phone frame from "Scan the lab" (2026-10-26): device key, JPEG only, person boxes normalised to
0-1 and never named, and ONE frame at a time (a second one meanwhile gets 429, nothing queues)."""
import threading
import types

import cv2
import numpy as np

import security_vision as sv
from vision import Detection


def jpeg(w=640, h=360):
    ok, b = cv2.imencode(".jpg", np.full((h, w, 3), 120, np.uint8))
    return b.tobytes()


class SlowDet:
    def __init__(self, gate=None):
        self.gate, self.calls = gate, 0

    def detect(self, img):
        self.calls += 1
        if self.gate:
            self.gate.wait(2)
        return [Detection(0, 0.81, (64.0, 36.0, 64.0, 144.0)), Detection(56, 0.9, (0.0, 0.0, 10.0, 10.0)),
                Detection(63, 0.72, (320.0, 180.0, 128.0, 72.0)), Detection(62, 0.2, (0.0, 0.0, 64.0, 36.0))]


def app(det):
    svc = types.SimpleNamespace(key="k", zoom_detector=det, detector_engine=lambda: "test", demo=None)
    return sv.make_app(svc).test_client()


def test_needs_the_device_key_and_a_jpeg():
    c = app(SlowDet())
    assert c.post("/detect", data=jpeg()).status_code == 401
    assert c.post("/detect", data=b"png?", headers={"X-Device-Key": "k"}).status_code == 422


def test_person_boxes_only_normalised_and_without_names():
    r = app(SlowDet()).post("/detect", data=jpeg(), headers={"X-Device-Key": "k"}).get_json()
    assert r["class"] == "person" and len(r["boxes"]) == 1                     # the chair (class 56) is dropped
    b = r["boxes"][0]
    assert (b["x"], b["y"], b["w"], b["h"]) == (0.1, 0.1, 0.1, 0.4) and b["score"] == 0.81 and "name" not in b


def test_one_frame_at_a_time_second_gets_429():
    gate = threading.Event()
    det = SlowDet(gate)
    c = app(det)
    first = {}
    t = threading.Thread(target=lambda: first.update(r=c.post("/detect", data=jpeg(), headers={"X-Device-Key": "k"})))
    t.start()
    for _ in range(100):                                     # wait until the first one holds the slot
        if det.calls:
            break
        threading.Event().wait(0.01)
    assert c.post("/detect", data=jpeg(), headers={"X-Device-Key": "k"}).status_code == 429
    gate.set(); t.join()
    assert first["r"].status_code == 200
    assert c.post("/detect", data=jpeg(), headers={"X-Device-Key": "k"}).status_code == 200   # slot released


def test_equipment_comes_as_a_generic_class_only():
    r = app(SlowDet()).post("/detect", data=jpeg(), headers={"X-Device-Key": "k"}).get_json()
    assert r["objects"] == [{"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2, "score": 0.72, "label": "laptop"}]   # weak monitor dropped
    assert all("name" not in o for o in r["objects"])
