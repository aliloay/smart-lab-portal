---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_crosscam_desk.py"
source_hash: "2e441925366a0c8f16642c9d665a65a4f7663f48668a59ba3d72882d8a2e7ea3"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_crosscam_desk.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_deskmap.py]] - tests
- [[tools_security_vision_crosscam.py]] - tests
- [[tools_security_vision_vision.py]] - tests

```py
"""Same-desk pairing between the two cameras (2026-10-21, SIMULATED). Seated at a desk the feet are
hidden, so only the owner-verified PC link (desk_map.json) can pair the person in both views."""
import json

import deskmap
from crosscam import STABLE_PASSES, CrossCam, peer_view
from vision import Labeler, Track

W, H = 1000, 1000
DESK = {"PC-08": (0.40, 0.40, 0.10, 0.10), "PC-09": (0.70, 0.40, 0.10, 0.10)}
SEATED = (410, 380, 100, 150)            # 1.5 x as tall as wide: sitting, overlaps PC-08
STANDING = (410, 250, 100, 300)          # 3 x: standing in front of PC-08


def peer(now, *tracks):
    """tracks: (id, desk, label, source, state, crowded) - no floor position (feet hidden)."""
    return {"t": now, "calibrated": False, "tracks": [
        {"id": i, "floor": None, "desk": d, "label": lab, "name": lab, "role": "STUDENT", "source": src,
         "state": st, "crowded": cr} for i, d, lab, src, st, cr in tracks]}


def cam(link=None):
    cc = CrossCam(None, "k", None)               # no floor map at all: only the desk can pair
    cc.desk_link = {"PC-08": "PC-08", "PC-09": "PC-09"} if link is None else link
    cc.desks = dict(DESK)
    return cc


def run(cc, tracks, lab, pf, passes, t0=1000.0):
    for k in range(passes):
        now = t0 + k * 0.2
        cc.peer = pf(now)
        cc.share(tracks, W, H, now, lab)


def test_confirmed_name_crosses_to_the_person_seated_at_the_same_desk():
    cc, lab = cam(), Labeler()
    t = Track(1, SEATED, 0, 0, hits=10)
    pf = lambda now: peer(now, (7, "PC-08", "USER1", "face", "FACE_CONFIRMED", False))
    run(cc, [t], lab, pf, STABLE_PASSES - 1)
    assert t.label is None                          # the pairing must hold first
    run(cc, [t], lab, pf, 1, t0=2000.0)
    assert t.label == "USER1" and t.source == "peer"
    assert any("seated alone at PC-08" in n["detail"] for n in cc.notes)


def test_other_desk_standing_or_unlinked_is_not_paired():
    for box, their_desk, link in ((SEATED, "PC-09", None), (STANDING, "PC-08", None), (SEATED, "PC-08", {})):
        cc, lab = cam(link), Labeler()
        t = Track(1, box, 0, 0, hits=10)
        run(cc, [t], lab, lambda now: peer(now, (7, their_desk, "USER1", "door", "DOOR_CONFIRMED", False)), 10)
        assert t.label is None, (box, their_desk, link)


def test_two_people_at_one_desk_in_either_view_pairs_nobody():
    cc, lab = cam(), Labeler()
    a, b = Track(1, SEATED, 0, 0, hits=10), Track(2, (420, 390, 100, 150), 0, 0, hits=10)
    run(cc, [a, b], lab, lambda now: peer(now, (7, "PC-08", "USER1", "face", "FACE_CONFIRMED", False)), 10)
    assert a.label is None and b.label is None
    cc, lab = cam(), Labeler()
    t = Track(1, SEATED, 0, 0, hits=10)
    run(cc, [t], lab, lambda now: peer(now, (7, "PC-08", "USER1", "face", "FACE_CONFIRMED", False),
                                       (8, "PC-08", None, None, "UNKNOWN", False)), 10)
    assert t.label is None


def test_guessed_names_and_conflicts_follow_the_floor_rules():
    cc, lab = cam(), Labeler()
    t = Track(1, SEATED, 0, 0, hits=10)
    run(cc, [t], lab, lambda now: peer(now, (7, "PC-08", "USER1", "look", "CONFIRMED", False)), 10)
    assert t.label is None                          # only a door / face name travels
    t2 = Track(2, SEATED, 0, 0, hits=10, label="USER2", name="Nour", source="door")
    run(cc, [t2], lab, lambda now: peer(now, (9, "PC-08", "USER1", "door", "DOOR_CONFIRMED", False)), 10)
    assert t2.label == "USER2"
    assert any(n["kind"] == "CROSSCAM_CONFLICT" for n in cc.notes)


def test_peer_view_reports_the_desk_only_when_seated():
    a, b = Track(1, SEATED, 0, 0), Track(2, STANDING, 0, 0)
    v = peer_view([a, b], None, W, H, 1.0, DESK)
    assert [t["desk"] for t in v["tracks"]] == ["PC-08", None]


def test_link_for_needs_owner_verification_and_maps_each_side(tmp_path):
    m = {"verified_by": "owner", "verified_at": "2026-10-21", "camera1": "CAM1", "camera2": "CAM2",
         "pairs": {"PC-C": "PC-08"}}
    (tmp_path / "desk_map.json").write_text(json.dumps(m))
    assert deskmap.link_for(str(tmp_path), "CAM1")[0] == {"PC-C": "PC-08"}     # camera 2's name -> mine
    assert deskmap.link_for(str(tmp_path), "CAM2")[0] == {"PC-08": "PC-C"}
    assert deskmap.link_for(str(tmp_path), "OTHER")[0] == {}
    (tmp_path / "desk_map.json").write_text(json.dumps({**m, "verified_by": ""}))
    assert deskmap.link_for(str(tmp_path), "CAM1")[0] == {}

```
