"""2026-10-21 18:37 lab, replayed: Ali seated at the UR5e table next to Nour. Camera 2 named Ali (USER1) but
marked him touching Nour; camera 1's floor put Nour 0.59 m from him (look 0.69) and Ali 1.50 m away (look
0.30) - camera 1 left both Unknown. With measured look thresholds: Nour is vetoed, Ali gets his name.
SIMULATED (synthetic looks with the live look distances)."""
import numpy as np

from crosscam import STABLE_PASSES, CrossCam, FloorMap
from vision import Labeler, Look, Track

W, H = 1000, 1000
FLOOR = FloorMap([{"px": [0, 0], "floor": [0, 0]}, {"px": [1, 0], "floor": [10, 0]},
                  {"px": [1, 1], "floor": [10, 10]}, {"px": [0, 1], "floor": [0, 10]}])


def unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


# deep_distance = (1 - a.b) / 1.2: ALI_THERE vs ALI_HERE 0.30, vs NOUR_HERE 0.69
ALI_THERE = unit([1, 0, 0])
ALI_HERE = unit([1 - 0.36, np.sqrt(1 - (1 - 0.36) ** 2), 0])
NOUR_HERE = unit([1 - 0.828, 0, np.sqrt(1 - (1 - 0.828) ** 2)])


def track(i, x, y, deep, crowded=False):
    t = Track(i, (x * 100 - 40, y * 100 - 200, 80, 200), 0, 0, hits=10, crowded=crowded)
    t.look = Look(np.zeros(3, np.float32))
    t.look.deep = deep
    return t


def peer(now, crowded=True):
    return {"t": now, "calibrated": True, "tracks": [
        {"id": 16, "floor": [4.7, 4.4], "label": "USER1", "name": "Ali Loay", "role": "STUDENT", "source": "peer",
         "state": "REID_CONFIRMED", "crowded": crowded, "deep": [float(v) for v in ALI_THERE]}]}


def run(mine, pf, passes=STABLE_PASSES + 2):
    cc, lab = CrossCam(None, "k", FLOOR), Labeler()
    for k in range(passes):
        now = 1000.0 + 0.2 * k
        cc.peer = pf(now)
        cc.share(mine, W, H, now, lab)
    return cc


def test_the_look_names_ali_and_not_nour_who_the_floor_puts_closer():
    nour, ali = track(27, 5.3, 4.5, NOUR_HERE), track(28, 5.9, 5.3, ALI_HERE)
    run([nour, ali], peer)
    assert ali.label == "USER1" and nour.label is None


def test_without_a_clear_look_touching_still_blocks():
    a = track(28, 5.9, 5.3, unit([0.4, np.sqrt(1 - 0.16), 0]))  # look 0.50 from Ali there: not clear
    run([a], peer)
    assert a.label is None


def test_a_clearly_different_look_vetoes_even_on_the_same_spot():
    nour = track(27, 4.7, 4.4, NOUR_HERE)                      # exactly where camera 2 has Ali
    run([nour], lambda now: peer(now, crowded=False))
    assert nour.label is None
