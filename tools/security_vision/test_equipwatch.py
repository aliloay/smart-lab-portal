"""
Equipment watch (equipwatch.py) without a camera: detections as plain boxes.

    py -m pytest test_equipwatch.py -q
"""
import equipwatch as ew
from equipwatch import EquipmentWatch, Found

PC1 = (0.10, 0.40, 0.08, 0.10)
PC2 = (0.40, 0.40, 0.08, 0.10)


def mon(box, score=0.6):
    return Found("Monitor", score, box)


def test_a_box_slightly_off_is_nudged_after_two_agreeing_scans():
    w = EquipmentWatch()
    off = (0.13, 0.42, 0.08, 0.10)                       # the monitor is a bit right of the box
    assert w.update({1: PC1}, [mon(off)], []).nudge == {}     # once: wait
    assert w.update({1: PC1}, [mon(off)], []).nudge == {1: off}


def test_a_box_on_its_item_is_left_alone():
    w = EquipmentWatch()
    for _ in range(3):
        assert w.update({1: PC1}, [mon((0.101, 0.401, 0.08, 0.10))], []).nudge == {}


def test_two_candidates_or_a_size_mismatch_never_nudge():
    w = EquipmentWatch()
    two = [mon((0.12, 0.40, 0.08, 0.10)), mon((0.08, 0.41, 0.08, 0.10))]
    big = [mon((0.12, 0.40, 0.20, 0.25))]
    for _ in range(3):
        assert w.update({1: PC1}, two, []).nudge == {}
        assert w.update({1: PC1}, big, []).nudge == {}


def test_an_item_with_no_box_is_reported_once_after_two_scans():
    w = EquipmentWatch()
    new = (0.70, 0.40, 0.08, 0.10)
    assert w.update({1: PC1}, [mon(PC1), mon(new)], []).unnamed == []
    r = w.update({1: PC1}, [mon(PC1), mon(new)], [])
    assert [f.box for f in r.unnamed] == [new]
    assert w.update({1: PC1}, [mon(PC1), mon(new)], []).unnamed == []    # not again


def test_a_laptop_on_a_person_is_not_equipment():
    w = EquipmentWatch()
    lap = Found("Laptop", 0.32, (0.45, 0.60, 0.08, 0.10))
    person = (0.40, 0.30, 0.20, 0.60)
    for _ in range(3):
        assert w.update({1: PC1}, [mon(PC1), lap], [person]).unnamed == []


def test_missing_only_after_being_seen_before_and_never_when_someone_is_at_it():
    w = EquipmentWatch()
    for _ in range(ew.SEEN_BEFORE):
        w.update({1: PC1, 2: PC2}, [mon(PC1), mon(PC2)], [])
    person_at_pc2 = (0.38, 0.30, 0.15, 0.50)
    out = []
    for _ in range(ew.NOT_SEEN_SCANS):
        out += w.update({1: PC1, 2: PC2}, [], [person_at_pc2]).not_seen
    assert out == [1]                                    # PC2 hidden by a person: in use
    assert w.update({1: PC1, 2: PC2}, [], []).not_seen == []           # once per incident
    assert w.update({1: PC1, 2: PC2}, [mon(PC1)], []).seen_again == [1]


def test_never_seen_box_is_not_reported_missing():
    w = EquipmentWatch()
    out = []
    for _ in range(ew.NOT_SEEN_SCANS * 2):
        out += w.update({1: PC1}, [], []).not_seen
    assert out == []                                     # the detector may simply not see that one
