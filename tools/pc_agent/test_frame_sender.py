"""2026-11-23: FrameSender - unchanged screens are skipped, with fallbacks for older / restarted portals."""
import pc_agent as a


class Http:
    def __init__(self, *codes):
        self.codes, self.calls = list(codes), []

    def post(self, url, params=None, data=None, headers=None, timeout=None):
        self.calls.append((data, headers))
        return type("R", (), {"status_code": self.codes.pop(0)})()


def _clock(monkeypatch):
    t = [100.0]
    monkeypatch.setattr(a.time, "monotonic", lambda: t[0])
    return t


def test_same_screen_is_not_sent_again_until_the_keepalive(monkeypatch):
    t = _clock(monkeypatch)
    h, s = Http(204, 204, 204), a.FrameSender()
    s.send(h, "u", {}, b"A")
    t[0] += 0.5
    assert s.send(h, "u", {}, b"A") == 204 and len(h.calls) == 1
    t[0] += 2
    s.send(h, "u", {}, b"A")
    assert h.calls[1] == (b"", {"X-Frame-Unchanged": "1"})
    s.send(h, "u", {}, b"B")
    assert h.calls[2][0] == b"B"


def test_old_portal_gets_full_frames_for_the_rest_of_the_run(monkeypatch):
    t = _clock(monkeypatch)
    h, s = Http(204, 422, 204, 204), a.FrameSender()
    s.send(h, "u", {}, b"A")
    t[0] += 3
    s.send(h, "u", {}, b"A")
    s.send(h, "u", {}, b"A")
    assert [c[0] for c in h.calls] == [b"A", b"", b"A", b"A"]


def test_restarted_portal_gets_the_full_frame_at_once(monkeypatch):
    t = _clock(monkeypatch)
    h, s = Http(204, 428, 204), a.FrameSender()
    s.send(h, "u", {}, b"A")
    t[0] += 3
    assert s.send(h, "u", {}, b"A") == 204
    assert [c[0] for c in h.calls] == [b"A", b"", b"A"] and s.skip_ok


def test_viewer_closed_is_noticed_on_a_static_screen(monkeypatch):
    t = _clock(monkeypatch)
    h, s = Http(204, 409), a.FrameSender()
    s.send(h, "u", {}, b"A")
    t[0] += 3
    assert s.send(h, "u", {}, b"A") == 409
