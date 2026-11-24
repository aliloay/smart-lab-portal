"""S-3 (returning-look guess) and S-5 (staff confirmation visible at once), 24 Nov 2026."""
import copy
import inspect
import threading
import types

from vision import Labeler, Track

ALI = {"auth_subject": "USER1", "name": "Ali", "role": "ENGINEER", "entered_at": 0.0}


def _t(i=3):
    return Track(i, (100, 100, 60, 200), 0.0, 0.0)


def test_guess_survives_for_someone_not_checked_in_then_expires():
    lab, t = Labeler(), _t()
    lab.look_back(t, ALI, 10.0)
    lab.assign([t], [], None, now=10.2)
    assert t.label == "USER1" and t.source == "look"
    assert "USER1" not in lab.face_named                       # never stored as a face name
    lab.assign([t], [], None, now=10.0 + lab.LOOK_BACK_KEEP_S + 1)
    assert t.label is None and not lab.look_guessed


def test_guess_is_not_desk_evidence():
    lab, t, seated = Labeler(), _t(), _t(4)
    lab.look_back(t, ALI, 10.0)
    t.label = None
    lab.home_desk([seated], {"USER1": ["PC-09"]}, {"PC-09": (90, 90, 100, 250)}, [], {}, 11.0)
    assert seated.label is None


def test_a_later_door_entry_takes_the_name_from_the_guess():
    lab, t = Labeler(), _t()
    lab.look_back(t, ALI, 10.0)
    lab.assign([t], [{**ALI, "entered_at": 20.0}], None, now=20.1)
    assert t.label is None


def test_plain_look_without_look_back_is_still_dropped():
    lab, t = Labeler(), _t()
    lab._give(t, ALI, "look")
    lab.assign([t], [], None, now=1.0)
    assert t.label is None


def test_confirm_updates_the_published_copies():
    import security_vision as sv
    src = inspect.getsource(sv)
    body = src[src.index('@app.post("/confirm")'):src.index('@app.post("/record/<action>")')]
    assert "with svc.label_lock, svc.lock:" in body and "svc.tracks" in body
    # run the locked block itself
    a, b = _t(1), _t(2)
    Labeler._give(b, ALI, "face")
    svc = types.SimpleNamespace(label_lock=threading.Lock(), lock=threading.Lock(), labeler=Labeler(),
                                tracker=types.SimpleNamespace(tracks=[a, b]), tracks=[copy.copy(a), copy.copy(b)])
    block = body[body.index("        with svc.label_lock, svc.lock:"):body.index("        by = str(")]
    ns = {"svc": svc, "tid": 1, "label": "USER1", "k": ALI, "jsonify": lambda x: x}
    exec("def go():\n" + block + "\ngo()", ns)
    assert a.label == svc.tracks[0].label == "USER1" and svc.tracks[0].source == "operator"
    assert b.label is None and svc.tracks[1].label is None
