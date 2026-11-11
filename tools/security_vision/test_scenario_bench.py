"""The simulated identity scenarios (scenario_bench.py) as a regression test - SIMULATED evidence:
in every defined scenario nobody is ever shown with someone else's name, names never switch, and a
confirmed name crosses to the second camera (2026-10-18)."""
import pytest

import scenario_bench as B


@pytest.mark.parametrize("name", list(B.SCENARIOS))
@pytest.mark.parametrize("noise,miss", [(0.10, 0.04), (0.18, 0.10)])
def test_no_false_names_and_no_name_switches(name, noise, miss):
    for seed in range(3):
        r = B.run(name, B.SCENARIOS[name], seed=seed, miss=miss, deep_noise=noise)
        assert r["false_names"] == 0 and r["name_switches"] == 0, (seed, r)


def test_two_entering_together_on_one_badge_stay_unknown_and_are_flagged():
    r = B.run("02", B.SCENARIOS["02 two enter together, one badge"])
    assert r["named_share"] == 0.0 and r["review"] >= 1


def test_a_confirmed_name_reaches_the_second_camera_and_never_the_stranger():
    cam1, cam2 = B.run_two_cameras()
    assert cam2["named_share"] > 0.5 and cam2["false_names"] == 0 and cam1["false_names"] == 0


@pytest.mark.parametrize("name", ["07c dead zone 25 s", "07d dead zone 25 s, look-alike walks there",
                                  "11 leaves view 3 min, returns"])
def test_the_name_comes_back_after_a_dead_zone_or_a_return(name):
    """2026-11-11 (owner): the label must come back to the person after a dead zone and after leaving and returning.
    Measured 0.97 with HANDBACK_S 60 s (was 0.81-0.90 at 20 s)."""
    for seed in (1, 2, 3):
        r = B.run(name, B.SCENARIOS[name], seed=seed)
        assert r["false_names"] == 0 and r["named_share"] > 0.9, (seed, r)     # never coming back = ~0.58
