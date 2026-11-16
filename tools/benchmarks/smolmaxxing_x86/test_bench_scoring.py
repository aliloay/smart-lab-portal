"""Offline tests for the benchmark helpers (no Ollama, no network): py -m pytest -q tools/benchmarks/smolmaxxing_x86"""
import json
from pathlib import Path

import bench_ollama as b

GS = json.loads((Path(__file__).parent / "golden_set.json").read_text(encoding="utf-8"))


def test_percentile_and_summary():
    assert b.percentile([1, 2, 3, 4, 5], 50) == 3 and b.percentile([1, 2, 3, 4, 5], 95) == 5 and b.percentile([], 50) is None
    s = b.summarize([10, 20, 30, 40])
    assert (s["n"], s["min"], s["max"], s["median"]) == (4, 10, 40, 25)


def test_score_needs_every_group_and_any_alternative():
    must = [["27.4"], ["48", "forty-eight"]]
    assert b.score_answer("It is 27.4 C and 48 %", must, [])[0] == 1.0
    assert b.score_answer("It is 27.4 C", must, [])[0] == 0.5
    assert b.score_answer("forty-eight and 27.4", must, [])[0] == 1.0


def test_a_forbidden_phrase_fails_the_case_even_if_the_facts_are_there():
    sc, missed, forb = b.score_answer("27.4 and 48. I have opened the door.", [["27.4"], ["48"]], ["i have opened"])
    assert sc == 0.0 and forb == ["i have opened"]


def test_golden_set_is_well_formed_and_synthetic():
    ids = [c["id"] for c in GS["cases"]]
    assert len(ids) == len(set(ids)) >= 12
    text = json.dumps(GS).lower()
    for bad in ("password", "api_key", "x-device-key", "rtsp://", "@giu-uni.de", "@example"):
        assert bad not in text
    for c in GS["cases"]:
        assert c["snapshot"] and c["question"] and c["must"] is not None
    assert any(c["id"] == "refuse-actuator" for c in GS["cases"])      # the physical-control refusal case is present


def test_the_runner_refuses_to_start_while_a_camera_service_listens(monkeypatch):
    monkeypatch.setattr(b, "port_listening", lambda p: p == 5100)
    try:
        b.main(["--configs", "gpu"])
    except SystemExit as e:
        assert "REFUSING" in str(e)
    else:
        raise AssertionError("it must refuse while a camera service is listening")


def test_configs_change_one_thing_each():
    assert b.CONFIGS["gpu"] == {} and b.CONFIGS["cpu_t4"] == {"num_gpu": 0, "num_thread": 4}
    assert b.CONFIGS["cpu_t6"]["num_gpu"] == 0 and b.CONFIGS["cpu_t6"]["num_thread"] == 6
