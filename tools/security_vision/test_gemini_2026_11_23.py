"""
Regression tests for the Gemini independent audit of 23 Nov 2026 (reports/gemini-independent-claude-closure-audit-2026-11-23).

    py -3.14 -m pytest test_gemini_2026_11_23.py -q
"""
import inspect
import time

import pose
from crosscam import CrossCam
from vision import Labeler, Track

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": 0.0}


def test_peer_without_a_fresh_picture_is_not_live():          # V-F1
    cc, now = CrossCam(None, "k", None), time.time()
    cc.peer = {"t": now, "tracks": [], "frame_t": None}        # stream dead: answers, no frame at all
    assert not cc.peer_live(now)
    cc.peer = {"t": now, "tracks": [], "frame_t": now - 10.0}  # stream frozen 10 s ago
    assert not cc.peer_live(now)
    cc.peer = {"t": now, "tracks": [], "frame_t": now - 0.2}   # live
    assert cc.peer_live(now)
    cc.peer = {"t": now, "tracks": []}                         # older peer build without frame_t: "t" decides
    assert cc.peer_live(now)
    cc.peer = {"t": now - 5.0, "tracks": [], "frame_t": now}   # silent peer
    assert not cc.peer_live(now)


def test_blind_peer_memory_is_not_handed_out():                # V-F1
    cc, now = CrossCam(None, "k", None), time.time()
    cc.seen = {"USER1": {"deep": None, "floor": None, "t": now - 1.0, "name": "Ali", "role": "STUDENT"}}
    cc.hstreak = {(7, "USER1"): 5}
    cc.peer = {"t": now, "tracks": [], "frame_t": now - 30.0}
    cc._handoff([Track(7, (100, 100, 60, 200), now, now)], 640, 480, now, Labeler())
    assert cc.hstreak == {}                                    # treated as silent: streaks dropped, nothing named


def test_seat_deferral_needs_a_live_peer_picture():           # V-F1
    import security_vision as sv
    src = inspect.getsource(sv.Service.zones_with_seats)
    assert "peer_live" in src


def test_look_guess_is_a_reacquire_not_a_confirmation():      # V-F3
    lab = Labeler()
    t = Track(3, (100, 100, 60, 200), 0.0, 0.0)
    lab.assign([t], [ALI], None, now=0.0)
    lab._give(t, ALI, "look", how="came back (same look) - guess")
    lab.events = []
    lab.assign([t], [ALI], None, now=0.1)
    kinds = [e.kind for e in lab.events]
    assert "PERSON_IDENTITY_CONFIRMED" not in kinds
    assert t.label == "USER1" and t.identity_state != "DOOR_CONFIRMED"


def test_look_guess_only_for_people_the_labeler_keeps():      # V-F3
    import security_vision as sv
    src = inspect.getsource(sv.Service.analyse)
    assert "labeler.look_back(" in src            # S-3: the only way a returning look becomes a name


def test_crowded_track_shows_no_old_joints():                 # V-F7
    t = Track(1, (0, 0, 10, 10), 0.0, 0.0)
    t.kp, t.kp_at = [(1.0, 1.0, 0.9)] * 17, time.time()
    assert pose.fresh_kps(t) is not None
    t.crowded = True
    assert pose.fresh_kps(t) is None


def test_pose_stays_fresh_across_one_missed_pass():           # V-F7
    t = Track(1, (0, 0, 10, 10), 0.0, 0.0)
    t.kp = [(1.0, 1.0, 0.9)] * 17
    t.kp_at = time.time() - 1.6                                # 1 Hz pass + latency: still shown
    assert pose.fresh_kps(t) is not None


def test_capture_loop_restarts_after_an_exception():          # V-F5
    import security_vision as sv
    cam = sv.Camera.__new__(sv.Camera)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("ffmpeg")
        raise SystemExit                                       # stop the test loop on the second run

    cam._run_loop = boom
    sv.time.sleep, real = (lambda s: None), sv.time.sleep
    try:
        try:
            cam._run()
        except SystemExit:
            pass
    finally:
        sv.time.sleep = real
    assert calls["n"] == 2 and cam.capture_restarts == 1
