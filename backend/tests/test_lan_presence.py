"""
Lab PCs seen on the LAN without an agent (tools/lan_presence, 2026-10-21).

Tested: a PC that answers on the LAN shows present (its device row is made on first sight, linked to
its asset); unplugging is a change, repeating the same state is not; every change is audited; a
report older than STALE_S is "unknown", never a stale "present"; only the lab's shared key may
report (a PC's own key must not speak for the others); a never-seen absent PC creates nothing.
"""
from datetime import datetime, timedelta, timezone

from app.models import Asset, AuditLog, Device
from app.services import lan_presence
from tests.conftest import auth_headers


def _report(client, headers, lab, present, uid="PC_01", tag="PC-01", ip="192.168.1.101",
            mac="60-eb-69-6b-c8-50", via="arp"):
    return client.post("/api/equipment/pc/presence", headers=headers, json={
        "lab_id": lab.code, "pcs": [{"device_uid": uid, "asset_tag": tag, "present": present,
                                     "ip": ip, "mac": mac, "via": via}]})


def _lan(client, staff, uid="PC_01"):
    rows = client.get("/api/equipment", headers=auth_headers(client, staff.email)).json()
    return next(r for r in rows if r["device_uid"] == uid)


def _audit(db, action):
    return db.query(AuditLog).filter_by(action=action).count()


def test_cable_in_out_is_seen_and_audited(client, db, staff, lab, device_headers):
    lan_presence.clear()
    db.add(Asset(asset_tag="PC-01", name="PC-01", lab_id=lab.id))
    db.commit()
    r = _report(client, device_headers, lab, True)
    assert r.status_code == 200 and r.json()["changes"] == 1
    d = db.query(Device).filter_by(device_uid="PC_01").one()
    assert d.asset_id is not None and d.last_seen_at is None       # LAN sight is not an agent heartbeat
    row = _lan(client, staff)
    assert row["lan"]["present"] is True and row["lan"]["ip"] == "192.168.1.101"
    assert row["online"] is None                                    # the agent never reported
    assert _audit(db, "PC_LAN_CONNECTED") == 1

    assert _report(client, device_headers, lab, True).json()["changes"] == 0     # same state: no news
    assert _report(client, device_headers, lab, False).json()["changes"] == 1    # cable out / shut down
    assert _lan(client, staff)["lan"]["present"] is False
    assert _audit(db, "PC_LAN_DISCONNECTED") == 1 and _audit(db, "PC_LAN_CONNECTED") == 1


def test_old_report_is_unknown_not_present(client, db, staff, lab, device_headers):
    lan_presence.clear()
    _report(client, device_headers, lab, True)
    old = datetime.now(timezone.utc) - timedelta(seconds=lan_presence.STALE_S + 5)
    lan_presence.update("PC_01", True, "192.168.1.101", "60-eb-69-6b-c8-50", "arp", now=old)
    assert _lan(client, staff)["lan"] is None                       # collector stopped: unknown


def test_only_the_shared_key_may_report(client, db, admin, lab, device_headers):
    lan_presence.clear()
    assert _report(client, {}, lab, True).status_code == 401
    _report(client, device_headers, lab, True)
    d = db.query(Device).filter_by(device_uid="PC_01").one()
    key = client.post(f"/api/devices/{d.id}/key", headers=auth_headers(client, admin.email)).json()["device_key"]
    r = _report(client, {"X-Device-Key": key}, lab, False)
    assert r.status_code == 403
    assert lan_presence.get("PC_01")["present"] is True             # unchanged


def test_absent_unknown_pc_creates_nothing(client, db, lab, device_headers):
    lan_presence.clear()
    assert _report(client, device_headers, lab, False, uid="PC_09", tag="PC-09").status_code == 200
    assert db.query(Device).filter_by(device_uid="PC_09").count() == 0


def test_students_cannot_read_lan_state(client, alice):
    assert client.get("/api/equipment", headers=auth_headers(client, alice.email)).status_code == 403
