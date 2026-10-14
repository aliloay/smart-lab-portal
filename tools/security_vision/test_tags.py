"""Name tags never cover each other (lab 2026-10-14: Nour's tag was drawn over by the neighbour's 'Unknown')."""
import numpy as np

import vision


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay - ah < by and by - bh < ay


def test_side_by_side_tags_do_not_overlap_and_stay_inside():
    f = np.zeros((540, 960, 3), np.uint8)
    placed = []
    # the lab case: Nour at x 693 (long tag), neighbour 'Unknown' at x 778, same height
    a = vision._tag_clear(f, "nour ramy (Student) USER6 - not entered 71%", 693, 340, 449, (0, 200, 255), placed)
    b = vision._tag_clear(f, "Unknown", 778, 347, 514, (0, 200, 255), placed)
    assert not overlap(placed[0], placed[1])
    for x, y, w, h in placed:
        assert 0 <= x and x + w <= 960 and y - h >= 0 and y <= 540


def test_tag_at_the_top_edge_goes_below_the_box_when_needed():
    f = np.zeros((540, 960, 3), np.uint8)
    placed = []
    vision._tag_clear(f, "Ali Loay (Student) USER1", 100, 5, 120, (0, 200, 255), placed)
    vision._tag_clear(f, "Unknown", 110, 5, 130, (0, 200, 255), placed)
    assert not overlap(placed[0], placed[1])
