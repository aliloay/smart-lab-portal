"""Camera-first GPU admission (gpu_gate.py): offline tests, no camera or GPU needed."""
import gpu_gate
from gpu_gate import IDLE_S, MIN_GPU_GAP_S, NEED_FREE_MB, Gate


def cam(state, port=5100, free=3500.0, fps=0.0):
    return {"port": port, "state": state, "fps": fps, "gpu_free_mb": free}


IDLE = [cam("idle", 5100), cam("idle", 5101)]


def test_starts_on_cpu_and_needs_a_full_idle_period():
    g = Gate()
    assert g.decide(0, IDLE) == "cpu"
    assert g.decide(IDLE_S - 1, IDLE) == "cpu" and "GPU offered in" in g.reason
    assert g.decide(max(IDLE_S, MIN_GPU_GAP_S), IDLE) == "gpu"


def test_a_live_camera_takes_the_gpu_back_at_once():
    g = Gate()
    t = max(IDLE_S, MIN_GPU_GAP_S)
    g.decide(0, IDLE)
    assert g.decide(t, IDLE) == "gpu"
    assert g.decide(t + 1, [cam("live", 5100, fps=7.0), cam("idle", 5101)]) == "cpu"
    assert "5100 live" in g.reason and "cameras first" in g.reason


def test_no_flapping_back_to_gpu():
    """A camera that blinks live for a moment does not cause a reload every few seconds."""
    g = Gate()
    t = max(IDLE_S, MIN_GPU_GAP_S)
    g.decide(0, IDLE)
    g.decide(t, IDLE)
    g.decide(t + 1, [cam("live")])                      # -> cpu at t+1
    assert g.decide(t + 1 + IDLE_S, IDLE) == "cpu"      # idle long enough, but the gap is not over
    assert g.decide(t + 1 + MIN_GPU_GAP_S + IDLE_S, IDLE) == "gpu"


def test_unknown_camera_state_is_not_safe():
    g = Gate()
    g.decide(0, IDLE)
    assert g.decide(10_000, [cam("unknown"), cam("idle", 5101)]) == "cpu"


def test_camera_services_not_running_leave_the_gpu_free():
    g = Gate()
    down = [cam("down", 5100, free=None), cam("down", 5101, free=None)]
    g.decide(0, down)
    assert g.decide(max(IDLE_S, MIN_GPU_GAP_S), down) == "gpu"


def test_too_little_gpu_memory_stays_on_cpu():
    g = Gate()
    low = [cam("idle", free=NEED_FREE_MB - 1)]
    g.decide(0, low)
    assert g.decide(10_000, low) == "cpu" and "MB GPU memory free" in g.reason


def test_refused_reads_as_down_and_timeout_as_unknown(monkeypatch):
    import urllib.error

    def refuse(*a, **k):
        raise urllib.error.URLError(ConnectionRefusedError(10061, "refused"))

    def slow(*a, **k):
        raise urllib.error.URLError(TimeoutError("timed out"))   # Windows: a closed port can look like this

    monkeypatch.setattr(gpu_gate.urllib.request, "urlopen", refuse)
    assert gpu_gate.camera_state(5100, "k")["state"] == "down"
    monkeypatch.setattr(gpu_gate.urllib.request, "urlopen", slow)
    assert gpu_gate.camera_state(5100, "k")["state"] == "unknown"          # -> CPU


def test_live_camera_metrics_parse(monkeypatch):
    import io
    import json as _json

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    body = {"analysis": {"fps": 6.9}, "stream": {"state": "LIVE"}, "gpu": {"mem_total_mb": 4096.0, "mem_used_mb": 1100.0}}
    monkeypatch.setattr(gpu_gate.urllib.request, "urlopen", lambda *a, **k: R(_json.dumps(body).encode()))
    c = gpu_gate.camera_state(5100, "k")
    assert c["state"] == "live" and c["fps"] == 6.9 and c["gpu_free_mb"] == 2996.0
    # security_vision.py Camera.status() reports state="STREAMING" (not "LIVE"); even when fps is 0.0 at startup,
    # STREAMING must be recognised as live so the GPU stays reserved for the camera.
    body_streaming = {"analysis": {"fps": 0.0}, "stream": {"state": "STREAMING"}, "gpu": {"mem_total_mb": 4096.0, "mem_used_mb": 900.0}}
    monkeypatch.setattr(gpu_gate.urllib.request, "urlopen", lambda *a, **k: R(_json.dumps(body_streaming).encode()))
    c2 = gpu_gate.camera_state(5100, "k")
    assert c2["state"] == "live" and c2["gpu_free_mb"] == 3196.0


def test_default_policy_is_unchanged():
    assert gpu_gate.use_gpu({"llm_on_cpu": True}) is False
    assert gpu_gate.use_gpu({"llm_on_cpu": False}) is True
    assert gpu_gate.use_gpu({}) is False


def test_own_model_memory_does_not_push_the_assistant_off_the_gpu(monkeypatch):
    """2026-11-21 audit F-05: with qwen3 on the GPU (1420 MB) the cameras' metrics showed 1673 MB free, below
    NEED_FREE_MB, and the gate flipped to CPU. Memory Ollama holds is the assistants' own and is added back."""
    idle = {"port": 5100, "state": "idle", "fps": 0.0, "gpu_free_mb": 1673.0}
    monkeypatch.setattr(gpu_gate, "camera_state", lambda p, k, timeout=1.5: dict(idle, port=p))
    monkeypatch.setattr(gpu_gate, "device_key", lambda repo: "k")
    monkeypatch.setattr(gpu_gate, "ollama_vram_mb", lambda *a, **k: 1420.0)
    g = gpu_gate.Gate()
    g.mode = "gpu"                                   # already on the GPU, cameras idle
    monkeypatch.setattr(gpu_gate, "_GATE", g)
    monkeypatch.setattr(gpu_gate, "_LAST", {"at": 0.0, "body": None})
    body = gpu_gate.current(".", now=1000.0)
    assert body["device"] == "gpu"
    assert body["cameras"][0]["gpu_free_mb"] == 3093.0 and body["cameras"][0]["gpu_free_raw_mb"] == 1673.0
    # nothing held by Ollama and really too little memory: still CPU
    monkeypatch.setattr(gpu_gate, "ollama_vram_mb", lambda *a, **k: 0.0)
    monkeypatch.setattr(gpu_gate, "_LAST", {"at": 0.0, "body": None})
    assert gpu_gate.current(".", now=2000.0)["device"] == "cpu"


def test_ollama_vram_unreachable_is_zero(monkeypatch):
    assert gpu_gate.ollama_vram_mb("http://127.0.0.1:9", timeout=0.3) == 0.0
