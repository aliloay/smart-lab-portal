"""Lab 24 Nov 2026: the recorded seats join seated people across the cameras - as a marked guess only."""
from crosscam import SEAT_PASSES, CrossCam, peer_view, seats_of
from vision import Labeler, Track

W, H = 960, 540
SEATS = {"PC-08": (0.55, 0.52, 0.06, 0.11), "PC-09": (0.60, 0.56, 0.10, 0.23), "PC-09@B": (0.30, 0.2, 0.06, 0.1)}


def px(n):
    x, y, w, h = SEATS[n]
    return (x * W, y * H, w * W, h * H)


def cam(peer_tracks, t):
    cc = CrossCam(None, "k", None)
    cc.all_seats, cc.desk_link = SEATS, {}
    for k in range(SEAT_PASSES + 1):
        now = 1000.0 + k * 0.2
        cc.peer = {"t": now, "frame_t": now, "calibrated": False, "tracks": peer_tracks}
        t.hint = None
        cc.seat_hints([t], W, H, now)
    return t


def p(label="USER10", seat="PC-08", source="operator", state="OPERATOR_CONFIRMED", i=7):
    return {"id": i, "seat": seat, "label": label, "name": "Person", "source": source, "state": state}


def test_one_person_per_seat_and_spots_share_the_pc_name():
    assert seats_of([px("PC-08"), px("PC-09")], W, H, SEATS) == ["PC-08", "PC-09"]
    assert seats_of([px("PC-08"), px("PC-08")], W, H, SEATS).count("PC-08") == 1
    assert seats_of([px("PC-09@B")], W, H, SEATS) == ["PC-09@B"]
    assert seats_of([px("PC-09"), px("PC-09@B")], W, H, SEATS) == ["PC-09", "PC-09@B"]
    assert seats_of([(100, 100, 40, 200)], W, H, SEATS) == [None]


def test_same_seat_shows_the_guess_but_never_a_name():
    t = cam([p()], Track(1, px("PC-08"), 0, 0))
    assert t.hint == "Person?" and t.hint_kind == "seat" and t.label is None
    assert peer_view([t], None, W, H, 1.0, None, SEATS)["tracks"][0]["label"] is None


def test_no_guess_for_guesses_other_seats_or_a_name_seen_twice():
    for tracks in ([p(source="look")], [p(state="IDENTITY_UNCERTAIN")], [p(seat="PC-09")],
                   [p(), p(i=8, seat="PC-09")], [p(), p("USER11", i=8)]):
        assert cam(tracks, Track(1, px("PC-08"), 0, 0)).hint is None


def test_a_named_person_is_never_changed():
    t = Track(1, px("PC-08"), 0, 0)
    Labeler._give(t, {"auth_subject": "USER1", "name": "Ali", "role": "S"}, "face")
    assert cam([p()], t).hint is None and t.label == "USER1"
