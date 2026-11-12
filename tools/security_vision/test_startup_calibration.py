"""Automatic startup alignment (2026-11-12, owner: "boxes aligned within 2-5 minutes after the cameras start, no click").
SIMULATED: synthetic room pictures shifted by known amounts, a controllable clock and a fake portal - no camera, no PTZ.
    py -3.14 -m pytest test_startup_calibration.py -q"""
import threading
import time
import types

import numpy as np

import realign
import security_vision as sv
from test_realign import room, shifted

ZONES = [{"id": 1, "name": "PC-01", "x": 0.30, "y": 0.30, "w": 0.12, "h": 0.14},
         {"id": 2, "name": "UR5e", "x": 0.60, "y": 0.50, "w": 0.15, "h": 0.20, "alert_on_motion": False},
         {"id": 3, "name": "Shelf", "x": 0.10, "y": 0.60, "w": 0.10, "h": 0.10}]


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakePortal:
    def __init__(self):
        self.posts = []

    def post(self, url, timeout=10, json=None):
        self.posts.append(json)
        return types.SimpleNamespace(status_code=200)


def make_svc(tmp_path, frame_box, clock, connected_ago=400.0):
    """A minimal camera service: the real _check_view / view_* / calibration methods on a namespace."""
    s = types.SimpleNamespace()
    s.camera = types.SimpleNamespace(state="STREAMING", state_since=clock() - connected_ago,
                                     latest=lambda: (frame_box[0], clock()))
    s.cfg = {"zones": [dict(z) for z in ZONES], "door": None}
    s.lock, s.tracks = threading.Lock(), []
    s.view_anchor, s.view_anchor_boxes, s.view_applied, s.view_before = None, {}, {}, {}
    s.view_pending, s.view_unstable, s.view_lost_checks, s.view_pending_since, s.view_Hn = None, False, 0, 0.0, None
    s.view_state = None
    s.args = types.SimpleNamespace(device=f"CAM_{id(s)}")
    s.portal, s.http = "http://portal", FakePortal()
    s.events = []
    s.event = lambda kind, detail, **k: s.events.append(kind)
    s._anchor_path = lambda: str(tmp_path / f"{s.args.device}.npz")
    for name in ("VIEW_STARTUP_QUIET_S", "VIEW_STABLE_S", "VIEW_STARTUP_MAX_S"):
        setattr(s, name, getattr(sv.Service, name))
    for name in ("view_settling", "view_in_startup", "_set_view_state", "calibration_brief"):
        setattr(s, name, getattr(sv.Service, name).__get__(s))
    s.check = lambda: sv.Service._check_view(s)
    return s


def run(s, clock, seconds, step=3.0):
    end = clock.t + seconds
    while clock.t < end:
        clock.t += step
        sv.time.time = clock          # the service reads time.time()
        s.check()


def test_constants_are_the_promised_window():
    assert sv.Service.VIEW_STARTUP_QUIET_S <= 60 and 20 <= sv.Service.VIEW_STABLE_S <= 30
    assert sv.Service.VIEW_STARTUP_MAX_S == 300


def test_power_on_shift_is_aligned_after_a_steady_view_and_within_five_minutes(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    img = room()
    box = [img]
    s = make_svc(tmp_path, box, clock)
    s.check()                                    # long-running camera: takes its anchor
    assert s.view_anchor is not None and s.view_state["state"] == "calibrated"
    # power cycle: reconnect now, the picture comes back shifted (pan settled slightly off)
    s.camera.state_since = clock.t
    box[0] = shifted(img, 40, -18)
    run(s, clock, 40)                            # inside the 45 s quiet time: nothing happens
    assert s.http.posts == [] and s.view_state["state"] == "settling"
    run(s, clock, 15)                            # quiet time over: the move is seen, but not yet steady 20 s
    assert s.http.posts == [] and s.view_state["state"] == "calibrating"
    run(s, clock, 30)                            # steady > 20 s -> one atomic re-alignment of every box
    assert len(s.http.posts) == 1
    sent = {b["id"]: b for b in s.http.posts[0]["boxes"]}
    assert set(sent) == {1, 2, 3}
    assert abs(sent[1]["x"] - (0.30 + 40 / 960)) < 0.01 and abs(sent[1]["y"] - (0.30 - 18 / 540)) < 0.01
    assert s.view_state["state"] == "calibrated" and s.view_state["boxes_moved"] == 3
    assert clock.t - s.camera.state_since < 300


def test_moving_view_never_moves_boxes(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    img = room()
    box = [img]
    s = make_svc(tmp_path, box, clock)
    s.check()
    s.camera.state_since = clock.t
    for k in range(60):                          # the camera keeps panning for 3 minutes
        box[0] = shifted(img, 10 + 4 * (k % 12), 0)
        run(s, clock, 3)
    assert s.http.posts == []
    assert s.view_state["state"] in ("settling", "calibrating")


def test_weak_match_after_startup_needs_review_and_changes_nothing(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    box = [room(seed=7)]
    s = make_svc(tmp_path, box, clock)
    s.check()
    zones_before = [dict(z) for z in s.cfg["zones"]]
    box[0] = room(seed=99)                       # a different picture: the room cannot be matched
    run(s, clock, 30)
    assert s.http.posts == [] and s.cfg["zones"] == zones_before
    assert s.view_state["state"] == "needs_review" and "matched" in s.view_state["reason"]


def test_no_new_anchor_during_startup(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    box = [room()]
    s = make_svc(tmp_path, box, clock, connected_ago=60)   # just (re)connected, no anchor on disk
    run(s, clock, 60)
    assert s.view_anchor is None                 # anchors are taken only after the startup window


def test_cameras_keep_separate_anchors_and_states(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    a_img, b_img = room(seed=7), room(seed=11)
    a, b = make_svc(tmp_path, [a_img], clock), make_svc(tmp_path, [b_img], clock)
    a.check(); b.check()
    assert a._anchor_path() != b._anchor_path()
    b.camera.state_since = clock.t               # only camera 2 restarts
    run(a, clock, 0.1); run(b, clock, 0.1)
    assert a.calibration_brief()["state"] == "calibrated"
    assert b.calibration_brief()["state"] == "settling"


def test_repeated_checks_do_not_drift_or_resend(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sv.time, "time", clock)
    img = room()
    box = [img]
    s = make_svc(tmp_path, box, clock)
    s.check()
    box[0] = shifted(img, 30, 0)
    run(s, clock, 30)                            # long-running camera: two agreeing looks move the boxes
    assert len(s.http.posts) == 1
    moved = {b["id"]: (b["x"], b["y"], b["w"], b["h"]) for b in s.http.posts[0]["boxes"]}
    for z in s.cfg["zones"]:                     # the portal now has the moved boxes
        z.update(dict(zip(("x", "y", "w", "h"), moved[z["id"]])))
    s.view_before = {}
    run(s, clock, 60)                            # ten more checks of the same view
    assert len(s.http.posts) == 1                # nothing sent again, nothing compounded


def test_seats_follow_the_same_transform_from_the_recorded_seats():
    Hn = np.array([[1, 0, 0.05], [0, 1, -0.02], [0, 0, 1]], np.float64)   # 5 % right, 2 % up
    seats = {"PC-01": [0.30, 0.40, 0.10, 0.15]}
    once = realign.move_seats(Hn, seats)
    twice = realign.move_seats(Hn, seats)        # always from the recorded seats: identical, no drift
    assert abs(once["PC-01"][0] - 0.35) < 1e-6 and abs(once["PC-01"][1] - 0.38) < 1e-6 and once == twice
    assert realign.move_seats(None, seats) == seats


def test_monitor_screens_and_robot_cells_are_masked():
    regions = realign.dynamic_regions(ZONES)
    kinds = {(r[4] > 0) for r in regions}
    assert len(regions) == 2 and kinds == {True, False}          # PC inset mask + robot full mask, shelf kept
    img = room()
    _, mask, _ = realign._prepare(img, [], regions)
    h, w = mask.shape
    pc = ZONES[0]
    cx, cy = int((pc["x"] + pc["w"] / 2) * w), int((pc["y"] + pc["h"] / 2) * h)
    assert mask[cy, cx] == 0                                    # screen centre masked
    assert mask[int(pc["y"] * h) + 1, int(pc["x"] * w) + 1] == 255   # bezel corner kept as an anchor
    shelf = ZONES[2]
    assert mask[int((shelf["y"] + 0.05) * h), int((shelf["x"] + 0.05) * w)] == 255


def test_masks_keep_enough_room_features_for_a_strong_match():
    img = room()
    regions = realign.dynamic_regions(ZONES)
    ref = realign.make_reference(img, [], "", regions)
    m = realign.compare(ref, shifted(img, 25, 10), [], regions)
    assert m.confident and m.inliers >= realign.APPLY_MIN_INLIERS


def test_no_ptz_or_camera_control_in_the_alignment_path():
    import inspect
    src = inspect.getsource(realign) + inspect.getsource(sv.Service._check_view)
    for word in ("ptz", "onvif", "continuousmove", "absolutemove", "gotopreset"):
        assert word not in src.lower()
