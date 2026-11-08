"""Short shared cache (app/core/ttl.py): one computation per key per TTL, concurrent callers share it."""
import threading
import time

from app.core import ttl


def test_shared_once_per_ttl_and_concurrent_callers_wait_for_one(monkeypatch):
    monkeypatch.setattr(ttl, "OFF", False)
    ttl.clear()
    calls = []

    def slow():
        calls.append(1); time.sleep(0.2); return len(calls)
    out = []
    ts = [threading.Thread(target=lambda: out.append(ttl.cached("k", 5, slow))) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(calls) == 1 and out == [1] * 8
    assert ttl.cached("k", 0.0, slow) == 2                 # expired -> recomputed
    ttl.clear()
