"""Who is driving the UR5e - pure classification (no robot) + the reader refuses non-queries."""
import pytest

from control_source import DashboardReader, classify


def test_hand_guiding_wins():
    assert classify({"robot_status_bits": 0b111, "remote_control": True}, True)[0] == "HAND_GUIDING"


def test_local_mode_is_the_pendant():
    code, text = classify({"remote_control": False}, True)
    assert code == "PENDANT" and "jogging" in text
    code, text = classify({"remote_control": False, "program_state": "PLAYING home.urp", "loaded_program": "home.urp"}, True)
    assert code == "PENDANT_PROGRAM" and "home.urp" in text


def test_local_mode_tells_jogging_programs_and_a_computer_apart():
    """2026-10-21: 'Moving - by teach pendant' while another person moved it."""
    loc = {"remote_control": False}
    assert classify(loc, True, 1) == ("PENDANT", "Teach pendant (Local mode) - jogging")
    assert classify(loc, True, 4)[0] == "MULTI_JOINT"
    assert classify(loc, True, None)[0] == "PENDANT"                     # joints not known: as before
    assert classify({**loc, "program_state": "PLAYING x", "loaded_program": "external_control.urp"}, True, 6)[0] == "EXTERNAL_CONTROL"
    assert classify({**loc, "program_state": "PLAYING x", "loaded_program": "pick.urp"}, True, 6)[0] == "PENDANT_PROGRAM"
    assert classify({"remote_control": True, "program_state": "PLAYING x", "loaded_program": "ros_control.urp"}, True)[0] == "EXTERNAL_CONTROL"


def test_remote_program_vs_direct_commands():
    assert classify({"remote_control": True, "program_state": "PLAYING x", "loaded_program": "home.urp"}, True)[0] == "REMOTE_PROGRAM"
    assert classify({"remote_control": True, "program_state": "STOPPED x", "robot_status_bits": 1}, True)[0] == "REMOTE_DIRECT"
    assert classify({"remote_control": True, "program_state": "STOPPED x"}, False)[0] == "IDLE"


def test_unknown_when_dashboard_not_readable():
    assert classify({}, True)[0] == "UNKNOWN"
    assert classify({}, False)[0] == "IDLE"


def test_reader_refuses_commands():
    r = DashboardReader("127.0.0.1")
    for cmd in ("play", "stop", "load home.urp", "power off", "unlock protective stop"):
        with pytest.raises(ValueError):
            r.ask(cmd)
