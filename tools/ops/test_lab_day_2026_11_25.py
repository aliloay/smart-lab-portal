"""Gemini audit 24 Nov 2026: a buffered frame is not a recovered camera; a help text is not a network capture."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location("lab_day", os.path.join(os.path.dirname(__file__), "lab_day.py"))
ld = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ld)


def run(rows):
    r, back = [], None
    for t, picture, age, ft in rows:
        r = ld.recovery_run(r, {"t": t, "cam2_picture": picture, "frame_age": age}, ft)
        if back is None and ld.recovered(r):
            back = r[0][0]
    return back


def test_buffered_bursts_are_not_recovery():
    burst = [(5.5 + k * .25, True, .3, 100 + k) for k in range(4)] + [(6.5, True, 3.0, 103)]
    again = [(10.6 + k * .25, True, .3, 110 + k) for k in range(4)] + [(15.3 + k, False, None, None) for k in range(280)]
    assert run(burst + again) is None


def test_a_repeated_frame_no_picture_or_a_future_stamp_is_not_recovery():
    assert run([(k * .25, True, .2, 100) for k in range(80)]) is None
    assert run([(k * .25, False, .2, 100 + k) for k in range(80)]) is None
    assert run([(k * .25, True, -30.0, 100 + k) for k in range(80)]) is None


def test_five_seconds_of_new_frames_is_recovery_from_the_first_one():
    assert run([(0, True, 4.0, 99)] + [(20 + k * .25, True, .2, 200 + k * .25) for k in range(30)]) == 20


def test_network_capture():
    assert ld.valid_network_text("Ethernet adapter Ethernet:
   IPv4 Address. . . : 192.168.1.200(Preferred)")
    assert not ld.valid_network_text("Error: unrecognized or incomplete command line.

USAGE:
    ipconfig [/all] IPv4 127.0.0.1")
