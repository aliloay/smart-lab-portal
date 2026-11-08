---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_deskmap.py"
source_hash: "03fe4954be62a2bc16250439b700dc9d58ac7487f1e7327332309b96585b5611"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_deskmap.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_deskmap.py]] - tests

```py
"""Same-desk mapping validation (2026-10-19): the rule stays off unless an explicit, verified mapping is valid."""
import json

import deskmap

CAM1 = {f"PC-{i:02d}" for i in range(1, 12)}
CAM2 = {f"PC-{c}" for c in "BCDFGIJKL"}
OK = {"verified_by": "owner", "verified_at": "2026-10-19", "pairs": {"PC-C": "PC-08", "PC-D": "PC-07"}}


def test_valid_partial_mapping_is_accepted():
    assert deskmap.validate(OK, CAM1, CAM2) == []


def test_unverified_duplicate_unknown_and_non_pc_are_rejected():
    assert any("verified" in e for e in deskmap.validate({**OK, "verified_by": ""}, CAM1, CAM2))
    dup = {**OK, "pairs": {"PC-C": "PC-08", "PC-D": "PC-08"}}
    assert any("twice" in e for e in deskmap.validate(dup, CAM1, CAM2))
    assert any("camera 2" in e for e in deskmap.validate({**OK, "pairs": {"PC-Z": "PC-08"}}, CAM1, CAM2))
    assert any("camera 1" in e for e in deskmap.validate({**OK, "pairs": {"PC-C": "PC-12"}}, CAM1, CAM2))
    assert any("only PC" in e for e in deskmap.validate({**OK, "pairs": {"UR5e": "PC-08"}}, CAM1, CAM2))
    assert deskmap.validate({**OK, "pairs": {}}, CAM1, CAM2) == ["no pairs"]


def test_load_is_off_without_a_file_or_with_an_invalid_one(tmp_path):
    pairs, why = deskmap.load(str(tmp_path), CAM1, CAM2)
    assert pairs is None and "off" in why[0]
    (tmp_path / "desk_map.json").write_text(json.dumps({**OK, "pairs": {"PC-C": "PC-99"}}))
    pairs, why = deskmap.load(str(tmp_path), CAM1, CAM2)
    assert pairs is None and why
    (tmp_path / "desk_map.json").write_text(json.dumps(OK))
    pairs, why = deskmap.load(str(tmp_path), CAM1, CAM2)
    assert pairs == {"PC-C": "PC-08", "PC-D": "PC-07"} and why == []

```
