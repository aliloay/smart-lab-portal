"""2026-11-18 (Gemini handoff P2): partial / pose_visibility from the camera survive the backend, validated."""
from app.api.routes.security import _visibility


def test_valid_metadata_is_kept():
    a = {"partial": True, "pose_visibility": {
        "head": {"state": "OBSERVED", "confidence": 0.9, "xy": [120.5, 40.2]},
        "knees": {"state": "OCCLUDED", "confidence": 0.5, "xy": None}}}
    v = _visibility(a)
    assert v["partial"] is True
    assert v["pose_visibility"]["head"] == {"state": "OBSERVED", "confidence": 0.9, "xy": [120.5, 40.2]}
    assert v["pose_visibility"]["knees"] == {"state": "OCCLUDED", "confidence": 0.5}


def test_legacy_payload_without_fields_is_unchanged():
    assert _visibility({"track_id": 1, "text": "x"}) == {}


def test_malformed_entries_are_dropped_not_guessed():
    a = {"partial": "yes", "pose_visibility": {
        "tail": {"state": "OBSERVED", "confidence": 1.0},                       # unknown joint
        "head": {"state": "VISIBLE", "confidence": 0.9},                        # unknown state
        "torso": {"state": "PREDICTED", "confidence": float("nan")},            # NaN
        "hips": {"state": "PREDICTED", "confidence": 1.5},                      # out of range
        "wrists": {"state": "OUT_OF_FRAME", "confidence": 0.2, "xy": [float("inf"), 1]}}}
    v = _visibility(a)
    assert "partial" not in v
    assert v["pose_visibility"] == {"wrists": {"state": "OUT_OF_FRAME", "confidence": 0.2}}


def test_huge_payload_is_bounded():
    a = {"pose_visibility": {f"j{i}": {"state": "OBSERVED", "confidence": 0.5} for i in range(10000)}}
    assert _visibility(a) == {}
