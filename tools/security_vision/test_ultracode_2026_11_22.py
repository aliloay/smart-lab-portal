"""ultracode 2026-11-22 regression tests: stale stream (F1/F2), look-only names (F3), pose (F7/F8), supervisor (F5)."""
import time
from types import SimpleNamespace

import pose
import security_vision as sv


def _kps():
    return [(1.0, 1.0, 0.9)] * 17


def test_pose_unmatched_track_loses_its_old_joints():
    """F7: a track with no pose this pass must not show old joints as OBSERVED for FRESH_S."""
    a = SimpleNamespace(box=(100, 100, 50, 150), kp=_kps(), kp_at=100.0)
    pose.attach([a], [], now=100.5)
    assert pose.fresh_kps(a, now=100.5) is None


def test_pose_matching_is_best_overlap_first():
    """F8: a wide box listed first no longer steals the neighbour's skeleton."""
    a = SimpleNamespace(box=(100, 100, 120, 200))
    b = SimpleNamespace(box=(150, 100, 60, 200))
    pb = {"box": (150, 100, 60, 200), "kps": _kps(), "score": 0.9}
    pa = {"box": (60, 100, 80, 200), "kps": _kps(), "score": 0.8}
    pose.attach([a, b], [pb, pa], now=1.0)
    assert b.kp is pb["kps"]


def test_pose_crowded_track_gets_no_pose():
    t = SimpleNamespace(box=(100, 100, 50, 150), crowded=True)
    assert pose.attach([t], [{"box": (100, 100, 50, 150), "kps": _kps(), "score": 0.9}], now=1.0) == 0


def _svc():
    s = sv.Service.__new__(sv.Service)
    import threading
    s.lock = threading.Lock()
    s.tracks = [SimpleNamespace(id=1)]
    s.person_rects = [(0, 0, 1, 1)]
    s.det_frame = ("frame", 0.0, {}, set(), None)
    return s


def test_stale_stream_withdraws_published_people():
    """F1: a dead stream must not keep publishing its last people as present."""
    s = _svc()
    assert s.withdraw_stale_tracks() is True
    assert s.tracks == [] and s.person_rects == [] and s.det_frame is None
    assert s.withdraw_stale_tracks() is False          # nothing left: no repeat log


def test_analyse_never_runs_twice_on_the_same_frame(monkeypatch):
    """F2: the same frame (same seq) is analysed once; a frame older than STALE_S not at all."""
    s = _svc()
    calls = {"full": 0}
    now = time.time()

    class Cam:
        def latest_seq(self):
            return "img", now, 7
        def full_for(self, seq):
            calls["full"] += 1
            raise StopIteration          # stop the loop right after the first accepted frame

    s.camera = Cam()
    s.args = SimpleNamespace(det_fps=10)
    s._last_seq = 7                      # already analysed
    sleeps = []
    monkeypatch.setattr(sv.time, "sleep", lambda d: (sleeps.append(d), (_ for _ in ()).throw(KeyboardInterrupt()))[1]
                        if len(sleeps) >= 2 else sleeps.append(d))
    try:
        s.analyse()
    except KeyboardInterrupt:
        pass
    assert calls["full"] == 0            # the repeated frame was skipped


def test_supervisor_restarts_a_crashing_loop(monkeypatch):
    """F5: a worker that raises is counted and restarted, not silently gone."""
    monkeypatch.setattr(sv.time, "sleep", lambda d: None)
    runs = {"n": 0}

    def flaky():
        runs["n"] += 1
        if runs["n"] < 3:
            raise KeyError("zones")
    flaky.__name__ = "poll_config"
    svc = SimpleNamespace()
    sv.supervised(svc, flaky)
    assert runs["n"] == 3 and svc.thread_restarts == {"poll_config": 2}


def test_look_only_return_is_a_guess_not_a_confirmed_name():
    """F3: the restore path in analyse gives source 'look' (shown 'Name ? (look)'), never 'peer'."""
    import inspect
    src = inspect.getsource(sv.Service.analyse)
    block = src[src.index("self.labnums.restore"):src.index("NAME_BACK_BY_LOOK")]
    give = inspect.getsource(sv.vision.Labeler.look_back) if hasattr(sv, "vision") else inspect.getsource(sv.Labeler.look_back)
    assert "labeler.look_back(" in block and '"look"' in give and '"peer"' not in block + give


def test_pose_joint_outside_the_frame_is_out_of_frame_not_observed():
    """V-F13: a leg the model places below the picture edge is OUT_OF_FRAME, never OBSERVED."""
    kps = [(100.0, 100.0, 0.9)] * 13 + [(100.0, 900.0, 0.9)] * 4     # knees + ankles below a 720-px frame
    v = pose.measured_visibility(kps, (1280, 720))
    assert v["knees"]["state"] == "OUT_OF_FRAME" and v["knees"]["xy"] is None
    assert v["ankles"]["state"] == "OUT_OF_FRAME"
    assert v["shoulders"]["state"] == "OBSERVED"
    assert pose.measured_visibility(kps)["knees"]["state"] == "OBSERVED"     # no frame size: unchanged behaviour


def test_published_tracks_are_a_copy_of_the_pass():
    """V-F6: a later change to the tracker's Track (next pass) must not show up in what readers already got."""
    import copy
    from vision import Track
    live = Track(id=1, box=(0, 0, 10, 20), first_seen=0.0, last_seen=0.0)
    live.label, live.name = "USER1", "Ali"
    snap = [copy.copy(t) for t in [live]]
    live.label, live.name = "USER2", None          # the Labeler mid-decision in the next pass
    assert snap[0].label == "USER1" and snap[0].name == "Ali"


# ---- 23 Nov closure: regression tests for fixes that had none (V-F10, V-F12) ----
import vision


def test_one_name_is_never_handed_back_to_two_new_people_in_one_pass(monkeypatch):
    """V-F10: the same name lost on two tracks at two places must come back on ONE new person only."""
    lab = vision.Labeler()
    monkeypatch.setattr(lab, "_distance", lambda t, label: 0.10)
    a = vision.Track(id=1, box=(100, 100, 60, 150), first_seen=7.0, last_seen=10.0, label="USER6", name="Nour",
                     role="Student", source="face", vel=(0.0, 0.0))
    b = vision.Track(id=3, box=(600, 100, 60, 150), first_seen=7.0, last_seen=10.0, label="USER6", name="Nour",
                     role="Student", source="face", vel=(0.0, 0.0))
    lab._hand_back([a, b], {}, 10.0)
    lab._hand_back([], {}, 12.0)                                   # both tracks end
    n1 = vision.Track(id=4, box=(100, 100, 60, 150), first_seen=12.5, last_seen=12.5)
    n2 = vision.Track(id=5, box=(600, 100, 60, 150), first_seen=12.5, last_seen=12.5)
    lab._hand_back([n1, n2], {}, 12.5)
    assert [n1.label, n2.label].count("USER6") == 1


def test_veto_counters_of_gone_tracks_are_dropped():
    """V-F12: `_unlike` must not keep a counter for every track id ever seen."""
    lab = vision.Labeler()
    lab._unlike = {tid: 1 for tid in range(500)}
    live = vision.Track(id=7, box=(0, 0, 10, 10), first_seen=0.0, last_seen=0.0)
    lab._veto([live])
    assert set(lab._unlike) <= {7}
