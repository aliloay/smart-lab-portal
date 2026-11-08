"""
Emergency tab: administrators only, behind the emergency password.

Tested: who may open it, the password and the lockout after wrong tries,
that the session token is not a login, that each action changes what the
door controller reads (with a new version) and is audited and announced,
timed unlocks running out, back to normal, PC actions sparing the lab
engineer's master PC, and changing the password.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models import AuditLog, Device, DeviceType, LabEmergency, Notification
from tests.conftest import auth_headers

PW = "giu_safe"


@pytest.fixture(autouse=True)
def emergency_password(monkeypatch):
    monkeypatch.setattr(settings, "EMERGENCY_PASSWORD", PW)


@pytest.fixture
def controller(db, lab):
    d = Device(device_uid="MASTER_EMG", name="Master", lab_id=lab.id,
               device_type=DeviceType.MASTER_CONTROLLER, is_online=True,
               last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


def _open(client, admin, password=PW):
    h = auth_headers(client, admin.email)
    r = client.post("/api/emergency/session", headers=h, json={"password": password})
    if r.status_code == 200:
        h["X-Emergency-Token"] = r.json()["token"]
    return r, h


def _door(client, device_headers):
    return client.get("/api/access/emergency?device_uid=MASTER_EMG", headers=device_headers).json()


def test_only_admins_and_only_with_the_password(client, db, admin, staff, lab, controller):
    assert client.post("/api/emergency/session", headers=auth_headers(client, staff.email),
                       json={"password": PW}).status_code == 403
    r, h = _open(client, admin, "wrong")
    assert r.status_code == 403 and "tries left" in r.json()["detail"]
    # Logged in as admin but no emergency session: refused.
    assert client.post(f"/api/emergency/labs/{lab.id}", headers=auth_headers(client, admin.email),
                       json={"door": "UNLOCKED"}).status_code == 403
    r, h = _open(client, admin)
    assert r.status_code == 200
    # The emergency token is not a login token.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 401


def test_lockout_after_wrong_passwords(client, db, admin):
    for _ in range(5):
        _open(client, admin, "nope")
    r, _ = _open(client, admin)                       # even the right one, for 15 min
    assert r.status_code == 429


def test_unlock_message_alarm_reach_the_controller(client, db, admin, staff, lab, controller, device_headers):
    assert _door(client, device_headers)["door"] == "NORMAL"
    _, h = _open(client, admin)
    r = client.post(f"/api/emergency/labs/{lab.id}", headers=h,
                    json={"door": "UNLOCKED", "minutes": 10, "message": 'Fire drill "now" — leave ✓',
                          "message_minutes": 30, "alarm": True})
    assert r.status_code == 200, r.text
    v = _door(client, device_headers)
    assert v["door"] == "UNLOCKED" and 590 <= v["remaining_s"] <= 600 and v["alarm"] is True
    assert v["message"] == "Fire drill 'now'  leave"           # what an LCD can show
    assert v["message_remaining_s"] > 1700 and v["version"] == 1
    assert db.query(AuditLog).filter_by(action="EMERGENCY_ACTION").count() == 1
    assert db.query(Notification).filter_by(user_id=staff.id, kind="EMERGENCY").count() == 1

    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"door": "UNLOCKED"})
    v = _door(client, device_headers)
    assert v["remaining_s"] == -1 and v["version"] == 2       # until back to normal

    client.post(f"/api/emergency/labs/{lab.id}/normal", headers=h)
    v = _door(client, device_headers)
    assert v == {"version": 3, "door": "NORMAL", "remaining_s": 0, "message": "",
                 "message_remaining_s": 0, "alarm": False, "speak": False}


def test_timed_unlock_runs_out(client, db, admin, lab, controller, device_headers):
    _, h = _open(client, admin)
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"door": "UNLOCKED", "minutes": 5})
    e = db.get(LabEmergency, lab.id)
    e.door_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    v = _door(client, device_headers)
    assert v["door"] == "NORMAL" and v["version"] == 2


def test_lockdown_and_status_shows_applied(client, db, admin, lab, controller, device_headers):
    _, h = _open(client, admin)
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"door": "LOCKDOWN"})
    st = next(l for l in client.get("/api/emergency/status", headers=h).json()["labs"] if l["lab_id"] == lab.id)
    assert st["door_mode"] == "LOCKDOWN" and st["applied"] is False
    controller.component_state = {"relay_locked": True, "emergency_version": st["version"]}
    db.commit()
    st = next(l for l in client.get("/api/emergency/status", headers=h).json()["labs"] if l["lab_id"] == lab.id)
    assert st["applied"] is True
    tile = next(t for t in client.get("/api/monitor", headers=h).json()["labs"] if t["lab_id"] == lab.id)
    assert tile["state"] == "ALERT" and tile["emergency"]["door_mode"] == "LOCKDOWN"


def test_pc_actions_spare_the_engineers_pc_and_staff_cannot_touch_it(client, db, admin, staff, lab):
    pcs = []
    for uid, master in (("PC_A", False), ("PC_B", False), ("PC_ENG", True)):
        d = Device(device_uid=uid, name=uid, lab_id=lab.id, device_type=DeviceType.PC, is_master_pc=master)
        db.add(d)
        pcs.append(d)
    db.commit()
    _, h = _open(client, admin)
    assert client.post("/api/emergency/pcs", headers=h, json={"action": "LOCK"}).json()["done"] == 2
    db.expire_all()
    assert [d.mode for d in pcs] == ["LOCKED", "LOCKED", None]
    client.post("/api/emergency/pcs", headers=h, json={"action": "LOCK", "include_master": True})
    db.expire_all()
    assert pcs[2].mode == "LOCKED"
    # Lab staff control lab PCs, not the engineer's master PC; the admin can.
    hs = auth_headers(client, staff.email)
    assert client.put(f"/api/equipment/{pcs[0].id}/mode", headers=hs, json={"mode": "NORMAL"}).status_code == 200
    # 2026-11-03 (Gemini ACT-02): the lab engineer now controls the master PC too (his own)
    assert client.put(f"/api/equipment/{pcs[2].id}/mode", headers=hs, json={"mode": "NORMAL"}).status_code == 200
    assert client.post(f"/api/equipment/{pcs[2].id}/screen/start", headers=hs).status_code == 200
    assert client.put(f"/api/equipment/{pcs[2].id}/mode", headers=h, json={"mode": "NORMAL"}).status_code == 200
    # Only an admin marks the master PC.
    # 2026-11-03: the lab engineer may now mark a master PC (owner); marked and released again here.
    assert client.put(f"/api/equipment/{pcs[0].id}/master", headers=hs, json={"is_master": True}).status_code == 200
    assert client.put(f"/api/equipment/{pcs[0].id}/master", headers=auth_headers(client, admin.email),
                      json={"is_master": False}).status_code == 200
    assert client.put(f"/api/equipment/{pcs[0].id}/master", headers=h, json={"is_master": True}).json()["is_master_pc"]


def test_change_password(client, db, admin):
    _, h = _open(client, admin)
    assert client.put("/api/emergency/password", headers=h, json={"new_password": "new-safe-1"}).status_code == 200
    assert _open(client, admin, PW)[0].status_code == 403           # the .env one no longer works
    assert _open(client, admin, "new-safe-1")[0].status_code == 200


# ------------------------------------------- n8n workflow 23 (automation) ---
def test_emergency_reaches_n8n_and_names_who_to_warn(client, db, admin, alice, lab, controller,
                                                     device_headers, monkeypatch):
    from app.models import AccessSession, AuthMethod, IntegrationEvent
    monkeypatch.setattr(settings, "AUTOMATION_API_KEY", "k")
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()
    _, h = _open(client, admin)
    client.post(f"/api/emergency/labs/{lab.id}", headers=h,
                json={"door": "UNLOCKED", "alarm": True, "message": "Fire drill"})
    ev = db.query(IntegrationEvent).filter_by(event_type="emergency.set").one()
    assert ev.lab_id == lab.id and ev.payload["alarm"] is True

    key = {"X-Automation-Key": "k"}
    st = client.get(f"/api/automation/emergency/{lab.id}", headers=key).json()
    assert st["active"] and st["applied"] is False             # the door has not confirmed yet
    (n,) = st["notices"]
    assert n["user_id"] == alice.id and n["title"].startswith("EVACUATE") and "Fire drill" in n["body"]
    assert n["severity"] == "critical" and n["dedupe_key"].endswith(f":{alice.id}")

    # The controller reports the version it applied: now "applied".
    controller.component_state = {"emergency_version": st["version"]}
    db.commit()
    assert client.get(f"/api/automation/emergency/{lab.id}", headers=key).json()["applied"] is True

    client.post(f"/api/emergency/labs/{lab.id}/normal", headers=h)
    assert client.get(f"/api/automation/emergency/{lab.id}",
                      headers=key).json()["notices"][0]["title"].endswith("back to normal")
    assert client.get(f"/api/automation/emergency/{lab.id}").status_code == 401


def test_evacuation_alarm_sounds_on_every_portal_screen(client, db, admin, alice, lab, controller, monkeypatch):
    """The alarm is not only the door buzzer: every signed-in page (students too)
    gets the full-screen alarm and siren, live and on a page opened later."""
    from app.ws.manager import manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    student = auth_headers(client, alice.email)
    _, h = _open(client, admin)

    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"alarm": True})
    raised = [m for m in sent if m["type"] == "hazard"]
    assert len(raised) == 1 and raised[0]["state"] == "raised" and raised[0]["metric"] == "evacuation"
    active = client.get("/api/labs/hazards/active", headers=student).json()
    assert [(a["metric"], a["lab_code"]) for a in active] == [("evacuation", lab.code)]
    first_id = active[0]["alert_id"]

    sent.clear()
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"message": "Leave now"})
    assert [m["state"] for m in sent if m["type"] == "hazard"] == ["raised"]
    assert client.get("/api/labs/hazards/active", headers=student).json()[0]["alert_id"] != first_id

    sent.clear()
    client.post(f"/api/emergency/labs/{lab.id}/normal", headers=h)
    assert [(m["state"], m["lab_code"]) for m in sent if m["type"] == "hazard"] == [("cleared", lab.code)]
    assert client.get("/api/labs/hazards/active", headers=student).json() == []

    sent.clear()
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"door": "LOCKDOWN"})
    assert [m for m in sent if m["type"] == "hazard"] == []          # no alarm, no siren


def test_message_reaches_everyone_and_is_read_aloud_until_sound_cleared(
        client, db, admin, alice, lab, controller, device_headers, monkeypatch):
    """An emergency message goes to every user (not only staff), is shown and
    read aloud on every screen and the door tablet; Clear sound stops the
    alarm and the voice but keeps the message; Clear all ends everything."""
    from app.ws.manager import manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    student = auth_headers(client, alice.email)
    _, h = _open(client, admin)

    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"message": "Leave by the stairs", "alarm": True})
    b = [m for m in sent if m["type"] == "emergency_broadcast"]
    assert len(b) == 1 and b[0]["message"] == "Leave by the stairs" and b[0]["speak"] and b[0]["alarm"]
    assert db.query(Notification).filter_by(user_id=alice.id, kind="EMERGENCY").count() == 1
    active = client.get("/api/emergency/active", headers=student).json()
    assert [(a["lab_code"], a["speak"], a["alarm"]) for a in active] == [(lab.code, True, True)]
    v = _door(client, device_headers)
    assert v["speak"] is True and v["alarm"] is True

    # Clear sound: buzzer and voices off, the message stays on the screens.
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"alarm": False, "speak": False})
    a = client.get("/api/emergency/active", headers=student).json()[0]
    assert (a["message"], a["speak"], a["alarm"]) == ("Leave by the stairs", False, False)
    v = _door(client, device_headers)
    assert v["speak"] is False and v["alarm"] is False and v["message"] == "Leave by the stairs"

    # A new message is read aloud again.
    client.post(f"/api/emergency/labs/{lab.id}", headers=h, json={"message": "Meet at gate 2"})
    assert client.get("/api/emergency/active", headers=student).json()[0]["speak"] is True

    # Clear all.
    sent.clear()
    client.post(f"/api/emergency/labs/{lab.id}/normal", headers=h)
    assert client.get("/api/emergency/active", headers=student).json() == []
    last = [m for m in sent if m["type"] == "emergency_broadcast"][-1]
    assert last["message"] == "" and not last["active"]
