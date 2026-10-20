"""Equipment box labels never cover each other (lab 2026-10-19: camera 1's eleven PC boxes side by side drew
"PC-PC-10 ok", "PC-(PC-08 ok" - unreadable)."""
from types import SimpleNamespace

import numpy as np

import vision

W, H = 960, 540
# Camera 1's real boxes (portal, 2026-10-19), normalised x, y, w, h.
CAM1 = [("PC-01", .296, .479, .016, .056), ("PC-02", .312, .487, .019, .052), ("PC-03", .327, .462, .017, .061),
        ("PC-04", .337, .493, .027, .061), ("PC-05", .370, .506, .012, .057), ("PC-06", .402, .513, .029, .040),
        ("PC-07", .437, .557, .021, .073), ("PC-08", .482, .557, .042, .076), ("PC-09", .532, .488, .038, .041),
        ("PC-10", .569, .481, .024, .048), ("PC-11", .641, .498, .033, .049), ("UR5e", .867, .468, .031, .115),
        ("Fanuc", .103, .573, .052, .104)]


def zones():
    return [{"id": i, "name": n, "x": x, "y": y, "w": w, "h": h} for i, (n, x, y, w, h) in enumerate(CAM1)]


def state(status, home=None):
    return SimpleNamespace(status=status, home=home)


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay - ah < by and by - bh < ay


def rects(tags):
    return [(t["x"], t["y"], t["w"], t["h"]) for t in tags]


def test_eleven_pcs_side_by_side_get_labels_that_do_not_overlap_and_stay_inside():
    tags = vision.zone_tags(zones(), {i: state("OK") for i in range(len(CAM1))}, W, H, [])
    assert len(tags) == len(CAM1)
    r = rects(tags)
    for i in range(len(r)):
        for j in range(i + 1, len(r)):
            assert not overlap(r[i], r[j]), (tags[i]["text"], tags[j]["text"])
    for x, y, w, h in r:
        assert 0 <= x and x + w <= W and y - h >= 0 and y <= H


def test_quiet_boxes_show_only_their_name_and_problems_keep_their_word():
    st = {i: state("OK") for i in range(len(CAM1))}
    st[5] = state("CHANGED")                        # PC-06
    st[11] = state("IN_USE")                        # UR5e
    st[12] = state("OK", home="AT_HOME")            # Fanuc
    tags = {t["zone"]: t["text"] for t in vision.zone_tags(zones(), st, W, H, [])}
    assert tags[0] == "PC-01"
    assert tags[5] == "PC-06 changed"
    assert tags[11] == "UR5e in use"
    assert tags[12] == "Fanuc - home"


def test_a_problem_label_gets_the_spot_right_under_its_own_box():
    st = {i: state("OK") for i in range(len(CAM1))}
    st[3] = state("CHANGED")                        # PC-04, in the middle of the row
    t = next(t for t in vision.zone_tags(zones(), st, W, H, []) if t["zone"] == 3)
    z = zones()[3]
    assert t["y"] == int((z["y"] + z["h"]) * H) + t["h"] and not t["moved"]


def test_labels_keep_clear_of_name_tags_already_placed():
    placed = []
    # a seated person's name tag right under the PC row (their head is at the desk)
    vision._tag_clear(np.zeros((H, W, 3), np.uint8), "Ali Loay (Student) USER1", 300, 300, 420, (0, 200, 255), placed)
    person = placed[0]
    tags = vision.zone_tags(zones(), {i: state("OK") for i in range(len(CAM1))}, W, H, placed)
    for t in tags:
        assert not overlap((t["x"], t["y"], t["w"], t["h"]), person), t["text"]


def test_draw_still_draws_everything():
    f = np.zeros((H, W, 3), np.uint8)
    track = SimpleNamespace(box=(400, 300, 60, 150), label=None, role=None, mismatch=False, entered=False,
                            name=None, source=None, identity_state=None, identity_confidence=None)
    out = vision.draw(f, [track], zones(), {i: state("OK") for i in range(len(CAM1))},
                      door_rect_norm=(.059, .301, .051, .306), door_open=False)
    assert out.shape == (H, W, 3) and out.any()


def test_robot_box_says_moving_when_the_robot_data_says_so():
    z = [{"id": 1, "name": "UR5e", "x": .1, "y": .1, "w": .1, "h": .1, "robot_state": "MOVING"}]
    t = vision.zone_tags(z, {1: state("OK", home="AT_HOME")}, W, H, [])[0]
    assert t["text"] == "UR5e moving (robot data)"
    z[0]["robot_state"] = "STATIONARY"
    assert vision.zone_tags(z, {1: state("OK", home="AT_HOME")}, W, H, [])[0]["text"] == "UR5e - home"
