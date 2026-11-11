"""The watchdog only watches: state changes, counted from results that are passed in (no service needed)."""
import inspect

import watchdog
from watchdog import DOWN_AFTER, Watch, snapshot

SVC = [("api", 8000, "/api/health", True), ("camera", 5100, "/health", False)]


def snap(api=True, camera=True):
    return snapshot(SVC, probe=lambda port, path: ((api if port == 8000 else camera), "test"))


def test_down_only_after_several_failures_and_recovered_with_the_time_away():
    w = Watch()
    assert w.update(snap(), 0.0) == []
    for k in range(DOWN_AFTER - 1):
        assert w.update(snap(camera=False), 15.0 * (k + 1)) == []          # one slow answer is not an outage
    ev = w.update(snap(camera=False), 45.0)
    assert [(e["event"], e["service"]) for e in ev] == [("DOWN", "camera")] and "launch.bat" in ev[0]["fix"]
    assert w.update(snap(camera=False), 60.0) == []                        # said once, not every 15 s
    ev = w.update(snap(), 165.0)
    assert ev == [{"event": "RECOVERED", "service": "camera", "port": 5100, "down_s": 120}]


def test_a_single_miss_between_good_answers_is_never_reported():
    w = Watch()
    for k, cam in enumerate([True, False, True, False, False, True]):
        assert w.update(snap(camera=cam), 15.0 * k) == []


def test_snapshot_marks_required_services_and_never_restarts_anything():
    s = snap(api=False)
    assert [(x["service"], x["up"], x["required"]) for x in s] == [("api", False, True), ("camera", True, False)]
    src = inspect.getsource(watchdog)
    for word in ("subprocess", "os.system", "Popen", "taskkill", "Start-Process"):
        assert word not in src, word                                       # monitor only, by construction
