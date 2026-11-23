"""2026-11-23: unchanged screens are not re-uploaded / re-downloaded (ETag, X-Frame-Unchanged, frame_hint)."""
from app.services import pc_control
from app.ws.manager import Client, manager
from tests.conftest import auth_headers
from tests.test_equipment import JPEG, _pc

U = {"X-Frame-Unchanged": "1"}


def _post(client, dh, content=JPEG, extra=None):
    return client.post("/api/equipment/pc/frame", params={"device_uid": "PC_01"},
                       headers={**dh, "Content-Type": "image/jpeg", **(extra or {})}, content=content)


def test_unchanged_frame_is_kept_and_revalidated(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    url = f"/api/equipment/{d.id}/screen.jpg"
    assert _post(client, device_headers, b"", U).status_code == 409          # nobody watching: same rule as a frame
    client.post(f"/api/equipment/{d.id}/screen/start", headers=h)
    assert _post(client, device_headers, b"", U).status_code == 428          # nothing stored yet
    assert _post(client, device_headers, b"").status_code == 422             # empty without the header: still refused
    assert _post(client, device_headers).status_code == 204
    r = client.get(url, headers=h)
    etag = r.headers["etag"]
    assert _post(client, device_headers, b"", U).status_code == 204
    r = client.get(url, headers={**h, "If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""
    assert _post(client, device_headers, JPEG + b"x").status_code == 204     # a new picture: new stamp
    r = client.get(url, headers={**h, "If-None-Match": etag})
    assert r.status_code == 200 and r.headers["etag"] != etag


def test_unchanged_keeps_an_old_picture_alive_but_never_revives_an_expired_one(monkeypatch):
    pc_control.reset()
    t = [1000.0]
    monkeypatch.setattr(pc_control.time, "monotonic", lambda: t[0])
    pc_control.put_frame(7, JPEG)
    t[0] += 4
    assert pc_control.touch_frame(7)
    t[0] += 4
    assert pc_control.latest_frame(7) == JPEG
    t[0] += 9
    assert pc_control.latest_frame(7) is None and not pc_control.touch_frame(7)
    pc_control.reset()


def test_broadcast_touch_keeps_the_stamp_and_respects_the_session():
    pc_control.broadcast_reset()
    s = pc_control.broadcast_start("Staff", 1, "browser")
    n = pc_control.broadcast_state()["session"]
    assert pc_control.broadcast_touch(n) is False                            # no picture yet
    assert pc_control.broadcast_put(JPEG, n)
    _, a = pc_control.broadcast_frame_stamped()
    assert pc_control.broadcast_touch(n) and pc_control.broadcast_frame_stamped()[1] == a
    assert pc_control.broadcast_touch(n + 1) is False
    assert pc_control.broadcast_put(JPEG + b"x", n) and pc_control.broadcast_frame_stamped()[1] != a
    pc_control.broadcast_reset()


def test_broadcast_route_answers_304(client, staff):
    pc_control.broadcast_reset()
    pc_control.broadcast_start("Staff", staff.id, "browser")
    pc_control.broadcast_put(JPEG)
    h = auth_headers(client, staff.email)
    r = client.get("/api/equipment/broadcast/frame.jpg", headers=h)
    assert r.status_code == 200
    r2 = client.get("/api/equipment/broadcast/frame.jpg", headers={**h, "If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304
    pc_control.broadcast_reset()


def test_pc_frame_hints_reach_staff_only():
    student = Client(user_id=1, is_staff=False, lab_filter=None)
    boss = Client(user_id=2, is_staff=True, lab_filter=None)
    pc = {"type": "frame_hint", "scope": "pc", "device_id": 3, "stamp": 1}
    share = {"type": "frame_hint", "scope": "broadcast", "stamp": 1}
    assert not manager._wants(student, pc) and manager._wants(boss, pc)
    assert manager._wants(student, share) and manager._wants(boss, share)
