---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/deskmap.py"
source_hash: "2ead6abd319acab39db6671d63517f1040be248000434dc1cf5919714a17d579"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/deskmap.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_test_crosscam_desk.py]] - tests
- [[tools_security_vision_test_deskmap.py]] - tests
- [[tools_security_vision_security_vision.py]] - imports

```py
"""
Same-desk mapping between the two cameras (2026-10-19; used by crosscam.py since 2026-10-21 once the owner
named both cameras' PC boxes by the real lab numbers and verified the file - see link_for).

Camera 1 names the lab PCs PC-01..PC-11; camera 2's PC boxes are provisional letters (PC-B..PC-L). The
same-desk rule ("the person seated at PC-08 on camera 1 is the person seated at the same PC on camera 2")
may only run on an explicit mapping the owner supplied and verified - never a guessed or sequential one.

anchors/desk_map.json:  {"verified_by": "<owner>", "verified_at": "<date>", "pairs": {"PC-C": "PC-08", ...}}

validate() rejects: unknown camera-2 box, unknown camera-1 PC, a camera-1 PC used twice, a non-PC box,
a mapping not marked verified. A camera-2 box that is not mapped is allowed (that PC is simply not
paired) - but nothing is inferred for it. A desk match may support an identity; it never proves one.
"""
from __future__ import annotations

import json
import os
from typing import Optional


def validate(mapping: dict, cam1_pcs: set[str], cam2_pcs: set[str]) -> list[str]:
    """Problems with a mapping (empty list = valid)."""
    errors = []
    pairs = mapping.get("pairs")
    if not isinstance(pairs, dict) or not pairs:
        return ["no pairs"]
    if not mapping.get("verified_by") or not mapping.get("verified_at"):
        errors.append("not marked as verified by the owner (verified_by / verified_at)")
    seen: dict[str, str] = {}
    for c2, c1 in pairs.items():
        if not str(c2).startswith("PC") or not str(c1).startswith("PC"):
            errors.append(f"{c2} -> {c1}: only PC boxes can be paired")
        if c2 not in cam2_pcs:
            errors.append(f"{c2}: no such PC box on camera 2")
        if c1 not in cam1_pcs:
            errors.append(f"{c1}: no such PC box on camera 1")
        if c1 in seen:
            errors.append(f"{c1} is mapped twice ({seen[c1]} and {c2})")
        seen[c1] = c2
    return errors


def load(folder: str, cam1_pcs: set[str], cam2_pcs: set[str]) -> tuple[Optional[dict], list[str]]:
    """(pairs, problems): pairs only when the file exists AND is valid; otherwise None (rule stays off)."""
    path = os.path.join(folder, "desk_map.json")
    if not os.path.isfile(path):
        return None, ["no desk_map.json - the same-desk rule is off"]
    try:
        with open(path, encoding="utf-8") as f:
            mapping = json.load(f)
    except (OSError, ValueError) as e:
        return None, [f"desk_map.json unreadable: {e}"]
    errors = validate(mapping, cam1_pcs, cam2_pcs)
    return (None, errors) if errors else (dict(mapping["pairs"]), [])


def link_for(folder: str, device: str) -> tuple[dict, str]:
    """(other camera's PC name -> this camera's, why) for crosscam's same-desk pairing (2026-10-21).
    desk_map.json names its cameras ("camera1" / "camera2" device ids); pairs are camera 2 -> camera 1.
    Empty unless the file is owner-verified and names this device. Box names are checked at use: a
    linked name with no box on a camera simply never matches."""
    path = os.path.join(folder, "desk_map.json")
    try:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return {}, "no readable desk_map.json - same-desk pairing off"
    pairs = m.get("pairs") or {}
    if not m.get("verified_by") or not m.get("verified_at") or not isinstance(pairs, dict) or not pairs:
        return {}, "desk_map.json not owner-verified - same-desk pairing off"
    if len(set(pairs.values())) != len(pairs):
        return {}, "desk_map.json maps a camera-1 PC twice - same-desk pairing off"
    if device == m.get("camera1"):
        return {c2: c1 for c2, c1 in pairs.items()}, f"{len(pairs)} linked PCs"
    if device == m.get("camera2"):
        return {c1: c2 for c2, c1 in pairs.items()}, f"{len(pairs)} linked PCs"
    return {}, f"desk_map.json is not for {device} - same-desk pairing off"

```
