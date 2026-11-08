"""Who is driving the UR5e - pure classification (no robot) + the reader refuses non-queries."""
import pytest

from control_source import DashboardReader, classify


def test_hand_guiding_wins():
    assert classify({"robot_status_bits": 0b111, "remote_control": True}, True)[0] == "HAND_GUIDING"


def test_local_mode_alone_never_means_the_pendant():
    """Owner 2026-11-04: nobody touched the pendant, a person moved the arm - it was shown as the pendant."""
    loc = {"remote_control": False}
    assert classify(loc, True)[0] == "MANUAL_UNCONFIRMED"
    assert classify(loc, True, 1)[0] == "MANUAL_UNCONFIRMED"            # one joint, commanded speed not reported
    assert classify(loc, True, 4)[0] == "MANUAL_UNCONFIRMED"
    assert classify(loc, False)[0] == "IDLE"


def test_program_needs_playing_and_commanded_motion():
    p = {"remote_control": False, "program_state": "PLAYING x", "loaded_program": "pick.urp"}
    assert classify({**p, "target_qd_max": 0.3}, True, 6)[0] == "PROGRAM"
    assert classify({**p, "target_qd_max": 0.0}, True, 2)[0] == "MANUAL_UNCONFIRMED"
    assert classify(p, True, 2)[0] == "MANUAL_UNCONFIRMED"
    assert classify({"remote_control": False, "robot_status_bits": 0b11, "target_qd_max": 0.3}, True, 3)[0] == "MANUAL_UNCONFIRMED"
    assert classify({**p, "loaded_program": "external_control.urp"}, True, 6)[0] == "EXTERNAL_CONTROL"
    assert classify({"remote_control": True, "program_state": "PLAYING x", "loaded_program": "ros_control.urp"}, True)[0] == "EXTERNAL_CONTROL"
    assert "pendant" not in classify({**p, "target_qd_max": 0.3}, True, 6)[1].lower()

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


def test_pendant_needs_commanded_motion_on_exactly_one_joint():
    local = {"remote_control": False, "robot_status_bits": 1, "program_state": "STOPPED"}
    assert classify({**local, "target_qd_max": 0.3}, True, 1)[0] == "PENDANT"
    assert classify({**local, "target_qd_max": 0.3}, True, 4)[0] == "MANUAL_UNCONFIRMED"
    assert classify({**local, "target_qd_max": 0.0}, True, 1)[0] == "MANUAL_UNCONFIRMED"
    assert classify({**local, "target_qd_max": 0.0}, False, 0)[0] == "IDLE"