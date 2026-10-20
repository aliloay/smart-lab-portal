"""
Same-desk mapping between the two cameras (2026-10-19) - VALIDATION ONLY, the same-desk rule stays OFF.

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
