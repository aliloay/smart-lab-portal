"""The door TEST watcher only trusts a face the door camera agrees on (lab 2026-10-21: USER5, USER1, USER3
within 25 s for one person became three entries and a wrong name)."""
from door_test_entry import stable_name


def test_one_answer_is_not_enough():
    assert stable_name([("USER1", 100.0)], 100.5) is None


def test_the_same_name_twice_is_agreed():
    assert stable_name([("USER1", 100.0), ("USER1", 101.0)], 101.2) == "USER1"


def test_a_flipping_face_gives_nobody():
    seq = [("USER5", 90.0), ("USER1", 99.0), ("USER3", 100.0), ("USER1", 101.0)]
    assert stable_name(seq, 101.2) is None          # USER3 / USER5 were said within 10 s


def test_old_other_names_do_not_block_and_old_agreement_does_not_count():
    assert stable_name([("USER3", 80.0), ("USER1", 100.0), ("USER1", 101.0)], 101.5) == "USER1"
    assert stable_name([("USER1", 90.0), ("USER1", 101.0)], 101.5) is None   # 11 s apart: not agreeing
