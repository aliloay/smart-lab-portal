---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_walk_handback.py"
source_hash: "20e69bc869b61a2b742e0580a4409fedc5ce53a964580040891f70eaaaf21d3a"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_walk_handback.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_vision.py]] - tests

```py
"""Lab 2026-10-19: Nour named by the door, her track broke 2.4 s later while walking, the new track
started a step ahead -> name dropped. A walking person's name follows along their path - look must agree."""
import vision


def _lab(monkeypatch, d):
    lab = vision.Labeler()
    monkeypatch.setattr(lab, "_distance", lambda t, label: d)
    return lab


def _named(lab, box, vel, now):
    t = vision.Track(id=1, box=box, first_seen=now - 3, last_seen=now, label="USER6", name="Nour",
                     role="Student", source="door", vel=vel)
    lab._hand_back([t], {"USER6": {}}, now)
    return t


def test_walking_person_gets_name_back_further_along_their_path(monkeypatch):
    lab = _lab(monkeypatch, 0.10)
    _named(lab, (100, 100, 60, 150), (120.0, 0.0), 10.0)       # walking right, 120 px/s
    lab._hand_back([], {"USER6": {}}, 12.0)                     # track ends
    new = vision.Track(id=2, box=(400, 100, 60, 150), first_seen=12.5, last_seen=12.5)
    lab._hand_back([new], {"USER6": {}}, 12.5)
    assert new.label == "USER6"


def test_walking_person_with_a_different_look_stays_unknown(monkeypatch):
    lab = _lab(monkeypatch, 0.40)
    _named(lab, (100, 100, 60, 150), (120.0, 0.0), 10.0)
    lab._hand_back([], {"USER6": {}}, 12.0)
    new = vision.Track(id=2, box=(400, 100, 60, 150), first_seen=12.5, last_seen=12.5)
    lab._hand_back([new], {"USER6": {}}, 12.5)
    assert new.label is None


def test_still_person_is_not_handed_back_far_away(monkeypatch):
    lab = _lab(monkeypatch, 0.10)
    _named(lab, (100, 100, 60, 150), (0.0, 0.0), 10.0)
    lab._hand_back([], {"USER6": {}}, 12.0)
    new = vision.Track(id=2, box=(400, 100, 60, 150), first_seen=12.5, last_seen=12.5)
    lab._hand_back([new], {"USER6": {}}, 12.5)
    assert new.label is None

```
