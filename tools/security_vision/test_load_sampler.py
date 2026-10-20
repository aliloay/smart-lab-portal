"""2026-10-18: /metrics process CPU was always 0 (a new psutil.Process per call). The sampler keeps one
object and samples on a fixed period; nvidia-smi output is parsed into numbers."""
import types

import latency


def test_sampler_keeps_one_process_object_and_starts_once():
    s = latency._LoadSampler()
    assert s.start() and s.start()
    assert s._proc is s._proc


def test_busy_process_shows_nonzero_cpu():
    s = latency._LoadSampler()
    s.start()
    import time
    end = time.time() + 0.6
    x = 0
    while time.time() < end:
        x += 1
    snap = s.sample()                       # deterministic: one reading right after the busy loop
    assert snap is not None and snap["cpu_percent"] > 0 and snap["private_mb"] > 0


def test_nvidia_smi_parsed(monkeypatch):
    out = "NVIDIA GeForce GTX 1650, 37, 612, 4096, 54, P2\n"
    monkeypatch.setattr("subprocess.run", lambda *a, **k: types.SimpleNamespace(stdout=out))
    g = latency.nvidia_smi()
    assert g["util_percent"] == 37 and g["mem_used_mb"] == 612 and g["pstate"] == "P2"


def test_nvidia_smi_missing_is_none(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr("subprocess.run", boom)
    assert latency.nvidia_smi() is None
