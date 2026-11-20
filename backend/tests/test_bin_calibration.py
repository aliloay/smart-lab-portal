"""
Guided bin calibration (2026-11-20): the portal drives the steps, the node's LCD shows them.
Clear (held 10 s) -> node zeroes -> empty container (held 10 s) -> parts -> count -> saved.
Nothing is booked while it runs; the result counts the parts exactly afterwards.
"""
from datetime import datetime, timezone

import pytest

from app.models import AuditLog, Device, DeviceType, InventoryBin, InventoryTransaction
from app.services import bin_calibration as cal
from app.services import inventory as inv
from tests.conftest import auth_headers


@pytest.fixture
def node(db, lab) -> Device:
    d = Device(device_uid="BIN_NODE_1", name="Consumable node", lab_id=lab.id, firmware_version="bin-0.6",
               device_type=DeviceType.SENSOR_NODE, last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


@pytest.fixture
def screws(db, lab) -> InventoryBin:
    b = InventoryBin(code="BIN-R10K", lab_id=lab.id, item_name="10k resistors",
                     tare_g=125.644, unit_mass_g=0.204)          # tonight's wrong calibration
    db.add(b)
    db.commit()
    return b


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1000.0}
    monkeypatch.setattr(cal, "_now", lambda: t["now"])
    cal.SESSIONS.clear()
    yield t
    cal.SESSIONS.clear()
    inv.LIVE.clear()                 # in-memory live counts are keyed by bin id; test bins reuse ids


def _send(client, headers, mass):
    r = client.post("/api/inventory/measurements", headers=headers,
                    json={"device_uid": "BIN_NODE_1", "readings": [{"bin_code": "BIN-R10K", "mass_g": mass}]})
    assert r.status_code == 200, r.text
    return r.json()["bins"][0]


def _hold(client, headers, clock, mass, seconds):
    """The node sends a settled reading every second while the weight is steady."""
    last = None
    for _ in range(int(seconds) + 1):
        last = _send(client, headers, mass)
        clock["now"] += 1.0
    return last


def test_full_guided_calibration(client, db, staff, lab, node, screws, device_headers, clock):
    h = auth_headers(client, staff.email)
    s = client.post(f"/api/inventory/bins/{screws.id}/calibration", headers=h, json={"item_name": "Screw M3"}).json()
    assert s["step"] == "CLEAR" and s["active"]

    # 1. platform empty (drifted -5.89 g): the LCD counts down, then the reply tells the node to zero itself
    first = _send(client, device_headers, -5.89)
    assert first["calibrating"] and first["lcd1"] == "SCREW M3 SETUP" and first["lcd2"].startswith("Empty scale")
    assert "tare" not in first
    clock["now"] += 1.0
    replies = [_send(client, device_headers, -5.89) for _ in range(1)]
    for _ in range(10):
        clock["now"] += 1.0
        replies.append(_send(client, device_headers, -5.89))
    assert any(r.get("tare") for r in replies)                 # the node zeroes itself
    assert cal.get(screws.id).step == "ZEROING"

    # 2. the node now reads 0 g: two readings -> container step
    _send(client, device_headers, 0.0); clock["now"] += 1
    r = _send(client, device_headers, 0.01); clock["now"] += 1
    assert cal.get(screws.id).step == "CONTAINER" and r["lcd2"] == "Put empty bin on"

    # 3. empty container held 10 s -> m0
    _hold(client, device_headers, clock, 125.863, 10)
    st = client.get(f"/api/inventory/bins/{screws.id}/calibration", headers=h).json()
    assert st["step"] == "PIECES" and st["m0_g"] == pytest.approx(125.863)

    # 4. 30 parts in; Calibrate refused until steady
    _send(client, device_headers, 131.828)
    early = client.post(f"/api/inventory/bins/{screws.id}/calibration/finish", headers=h, json={"pieces": 30})
    assert early.status_code == 409
    last = _hold(client, device_headers, clock, 131.828, 3)
    assert last["lcd2"] == "Enter count now"
    fin = client.post(f"/api/inventory/bins/{screws.id}/calibration/finish", headers=h, json={"pieces": 30})
    assert fin.status_code == 200, fin.text
    res = fin.json()["result"]
    assert res["unit_mass_g"] == pytest.approx(0.19883, abs=1e-4) and res["tare_g"] == pytest.approx(125.863)

    db.expire_all()
    b = db.get(InventoryBin, screws.id)
    assert b.item_name == "Screw M3" and b.unit_mass_g == pytest.approx(0.19883, abs=1e-4)
    assert db.query(AuditLog).filter_by(action="INVENTORY_BIN_CALIBRATED").count() == 1
    # nothing was booked while calibrating (container on/off, parts in)
    assert db.query(InventoryTransaction).count() == 0

    # 5. LCD shows the result, then the bin counts normally: 30 exactly
    done = _send(client, device_headers, 131.828)
    assert done["lcd1"] == "CALIBRATED" and done["lcd2"].startswith("30 pcs")
    clock["now"] += cal.DONE_SHOW_S + 1
    back = _send(client, device_headers, 131.828)
    assert "calibrating" not in back and back["qty_est"] == 30


def test_moving_weight_restarts_the_countdown(client, staff, lab, node, screws, device_headers, clock):
    h = auth_headers(client, staff.email)
    client.post(f"/api/inventory/bins/{screws.id}/calibration", headers=h, json={})
    _hold(client, device_headers, clock, 0.4, 6)
    clock["now"] += 5                       # no settled reading for 5 s: someone is touching it
    r = _send(client, device_headers, 0.4)
    assert r["lcd2"] == "Empty scale 10s" and cal.get(screws.id).step == "CLEAR"


def test_cancel_and_staff_only(client, alice, staff, lab, node, screws, device_headers, clock):
    assert client.post(f"/api/inventory/bins/{screws.id}/calibration", headers=auth_headers(client, alice.email),
                       json={}).status_code == 403
    h = auth_headers(client, staff.email)
    client.post(f"/api/inventory/bins/{screws.id}/calibration", headers=h, json={})
    assert client.delete(f"/api/inventory/bins/{screws.id}/calibration", headers=h).json()["cancelled"] is True
    r = _send(client, device_headers, 131.8)
    assert "calibrating" not in r


def test_one_scale_several_items(client, db, staff, lab, node, screws, device_headers, clock):
    """Calibrating screws on the resistor bin keeps the resistors as a saved item; switching back restores
    their calibration; switching with a count anchors it to the current reading."""
    h = auth_headers(client, staff.email)
    client.post(f"/api/inventory/bins/{screws.id}/calibration", headers=h, json={"item_name": "Screw M3"})
    _hold(client, device_headers, clock, -1.0, 11)
    _send(client, device_headers, 0.0); clock["now"] += 1
    _send(client, device_headers, 0.0); clock["now"] += 1
    _hold(client, device_headers, clock, 125.86, 10)
    _hold(client, device_headers, clock, 130.86, 3)          # 10 screws = 5.00 g
    assert client.post(f"/api/inventory/bins/{screws.id}/calibration/finish", headers=h,
                       json={"pieces": 10}).status_code == 200

    items = {i["item_name"]: i for i in client.get(f"/api/inventory/bins/{screws.id}/items", headers=h).json()}
    assert set(items) == {"10k resistors", "Screw M3"}
    assert items["Screw M3"]["is_selected"] and items["Screw M3"]["unit_mass_g"] == pytest.approx(0.5)
    assert items["10k resistors"]["unit_mass_g"] == pytest.approx(0.204) and not items["10k resistors"]["is_selected"]

    # a calibration is not running any more (DONE shows for a while): wait it out, then switch to the resistors
    clock["now"] += cal.DONE_SHOW_S + 1
    r = client.post(f"/api/inventory/bins/{screws.id}/items/{items['10k resistors']['id']}/select", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["item_name"] == "10k resistors" and r.json()["unit_mass_g"] == pytest.approx(0.204)

    # back to screws, telling the portal 10 are in the box: anchored to the latest reading (130.86 g)
    r = client.post(f"/api/inventory/bins/{screws.id}/items/{items['Screw M3']['id']}/select", headers=h,
                    json={"count": 10}).json()
    assert r["item_name"] == "Screw M3" and r["tare_g"] == pytest.approx(130.86 - 10 * 0.5)

    # the counted item cannot be removed; the other can (hidden, not deleted)
    assert client.post(f"/api/inventory/bins/{screws.id}/items/{items['Screw M3']['id']}/remove",
                       headers=h).status_code == 409
    left = client.post(f"/api/inventory/bins/{screws.id}/items/{items['10k resistors']['id']}/remove", headers=h).json()
    assert [i["item_name"] for i in left] == ["Screw M3"]
