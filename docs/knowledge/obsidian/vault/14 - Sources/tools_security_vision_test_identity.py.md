---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_identity.py"
source_hash: "0939266d14ac5ce00820590fe26908a25f89ed9e6358312a1692a6b4ce427256"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_identity.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[backend_app_services_identity.py]] - tests
- [[tools_security_vision_vision.py]] - tests

```py
"""
Identity evidence / state / confidence (identity.py, through vision.Labeler).

    py -m pytest test_identity.py -q
"""
from identity import IdentityConfig, IdentityLedger
from vision import Labeler, Track

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "STUDENT", "entered_at": 0.0}
KNOWN = [{"auth_subject": "USER1", "name": "Ali", "role": "STUDENT"},
         {"auth_subject": "USER6", "name": "Nour", "role": "STUDENT"}]


def door_track(tid=1):
    return Track(tid, (100, 100, 60, 200), 0.0, 0.0, label="USER1", name="Ali", role="STUDENT",
                 source="door", named_by="door")


def kinds(lab):
    return [e.kind for e in lab.events]


def test_door_name_is_confirmed_then_decays_but_is_never_dropped():
    lab = Labeler()
    t = door_track()
    lab.assign([t], [ALI], None, now=0.0)
    assert t.identity_state == "DOOR_CONFIRMED" and t.identity_confidence == 0.9
    assert kinds(lab) == ["PERSON_IDENTITY_CONFIRMED"]
    lab.assign([t], [ALI], None, now=600.0)             # 10 min, nothing new (no look: no top-up)
    assert t.identity_state == "IDENTITY_UNCERTAIN" and t.identity_confidence < 0.5
    assert "PERSON_IDENTITY_UNCERTAIN" in kinds(lab)
    lab.assign([t], [ALI], None, now=3600.0)
    assert t.label == "USER1"                           # the door is the authority: kept, shown uncertain


def test_face_only_name_is_dropped_when_never_confirmed_again():
    lab = Labeler()
    t = Track(1, (100, 100, 60, 200), 0.0, 0.0)
    lab.face_vote(1, "USER1", 0.0, 0.62)
    lab.face_vote(1, "USER1", 1.0, 0.64)
    lab.assign([t], [], None, now=1.0, known=KNOWN)
    assert t.label == "USER1" and t.identity_state == "FACE_CONFIRMED"
    lab.assign([t], [], None, now=60.0, known=KNOWN)
    assert t.identity_state in ("REID_CONFIRMED", "IDENTITY_UNCERTAIN")
    lab.assign([t], [], None, now=1000.0, known=KNOWN)
    assert t.label is None and "PERSON_IDENTITY_DROPPED" in kinds(lab)   # Unknown, not wrong


def test_a_face_saying_someone_else_raises_a_conflict_and_never_renames():
    lab = Labeler()
    t = door_track()
    lab.assign([t], [ALI], None, now=0.0)
    lab.face_vote(1, "USER6", 1.0, 0.7)
    lab.assign([t], [ALI], None, now=1.0)
    assert t.label == "USER1" and t.identity_state != "IDENTITY_CONFLICT"   # one face is not enough
    lab.face_vote(1, "USER6", 2.0, 0.7)
    lab.assign([t], [ALI], None, now=2.0)
    assert t.label == "USER1" and t.identity_state == "IDENTITY_CONFLICT"
    assert kinds(lab) == ["PERSON_IDENTITY_CONFLICT"]
    lab.assign([t], [ALI], None, now=3.0)
    assert "PERSON_IDENTITY_CONFLICT" not in kinds(lab)                    # raised once, not every frame


def test_touching_someone_is_occluded():
    lab = Labeler()
    t = door_track()
    lab.assign([t], [ALI], None, now=0.0)
    t.crowded = True
    lab.assign([t], [ALI], None, now=1.0)
    assert t.identity_state == "OCCLUDED" and t.label == "USER1"


def test_face_matches_top_confidence_back_up():
    lab = Labeler()
    t = door_track()
    lab.assign([t], [ALI], None, now=0.0)
    lab.assign([t], [ALI], None, now=300.0)
    low = t.identity_confidence
    lab.face_vote(1, "USER1", 300.5, 0.8)
    lab.face_vote(1, "USER1", 301.0, 0.8)
    lab.assign([t], [ALI], None, now=301.0)
    assert t.identity_confidence > low
    assert t.identity_state in ("FACE_CONFIRMED", "FUSED_CONFIRMED")


def test_explain_lists_the_evidence():
    lab = Labeler()
    t = door_track()
    lab.assign([t], [ALI], None, now=0.0)
    ex = lab.ledger.explain(1)
    assert ex["state"] == "DOOR_CONFIRMED" and ex["evidence"][0]["kind"] == "door"


def test_config_is_adjustable():
    led = IdentityLedger(IdentityConfig(half_life_s=10.0))
    assert led.cfg.half_life_s == 10.0

```
