"""
Reusable smart bin (Robotics Lab, System 3), backend side.

Tested: return by scanning (recorded only after the lid opened); checkout
only from inside the lab, completed only by the SELECTED item's own tag
(a wrong item changes nothing); unknown tags are remembered for
assignment; one tag per item; device scope.
"""
from datetime import datetime, timezone

import pytest

from app.models import (AccessSession, Asset, AssetStatus, AssetTransaction, AuthMethod,
                        Device, DeviceType)
from tests.conftest import auth_headers


@pytest.fixture
def bin_node(db, lab) -> Device:
    d = Device(device_uid="REUSE_BIN_1", name="Reusable bin", lab_id=lab.id,
               device_type=DeviceType.SENSOR_NODE, last_seen_at=datetime.now(timezone.utc),
               component_state={"reusable_bin": True})
    db.add(d)
    db.commit()
    return d


@pytest.fixture
def arduino(db, lab) -> Asset:
    a = Asset(asset_tag="ARDUINO-001", name="Arduino Uno", category="board",
              lab_id=lab.id, nfc_uid="04A1B2C3D4E5F6")
    db.add(a)
    db.commit()
    return a


@pytest.fixture
def breadboard(db, lab) -> Asset:
    a = Asset(asset_tag="BREADBOARD-001", name="Breadboard", lab_id=lab.id,
              nfc_uid="04FFEEDDCCBBAA")
    db.add(a)
    db.commit()
    return a


def _scan(client, headers, uid, dev="REUSE_BIN_1"):
    return client.post("/api/reusable/scan", headers=headers,
                       json={"device_uid": dev, "nfc_uid": uid}).json()


def _inside(db, user, lab):
    db.add(AccessSession(lab_id=lab.id, user_id=user.id, entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()


def test_checkout_needs_presence_and_the_selected_tag(client, db, alice, lab, bin_node,
                                                      arduino, breadboard, device_headers):
    h = auth_headers(client, alice.email)
    r = client.post("/api/reusable/checkout", headers=h, json={"asset_id": arduino.id})
    assert r.status_code == 409 and "inside the lab" in r.json()["detail"]

    _inside(db, alice, lab)
    r = client.post("/api/reusable/checkout", headers=h, json={"asset_id": arduino.id})
    assert r.status_code == 200 and r.json()["command"] == "OPEN_LID"

    # The bin node fetches the request like any device command.
    nxt = client.get("/api/access/commands/next?device_uid=REUSE_BIN_1", headers=device_headers).json()
    assert nxt["command"] == "OPEN_LID" and nxt["asset_tag"] == "ARDUINO-001"

    # Wrong item scanned: nothing changes.
    assert _scan(client, device_headers, "04:FF:EE:DD:CC:BB:AA")["action"] == "WRONG_ITEM"
    db.refresh(breadboard)
    assert breadboard.status == AssetStatus.AVAILABLE

    # The selected item's own tag completes the checkout.
    assert _scan(client, device_headers, "04a1b2c3d4e5f6")["action"] == "CHECKOUT_OK"
    db.refresh(arduino)
    assert arduino.status == AssetStatus.CHECKED_OUT and arduino.holder_id == alice.id
    tx = db.query(AssetTransaction).one()
    assert tx.action == "CHECKOUT" and tx.source == "BIN" and tx.device_id == bin_node.id


def test_return_is_recorded_only_after_the_lid_opened(client, db, alice, lab, bin_node,
                                                      arduino, device_headers):
    arduino.status, arduino.holder_id = AssetStatus.CHECKED_OUT, alice.id
    db.commit()
    r = _scan(client, device_headers, arduino.nfc_uid)
    assert r["action"] == "OPEN_FOR_RETURN" and r["lcd2"] == "RETURNING..."
    body = {"device_uid": "REUSE_BIN_1", "nfc_uid": arduino.nfc_uid}
    no = client.post("/api/reusable/complete", headers=device_headers,
                     json={**body, "lid_opened": False, "lid_closed": False}).json()
    assert no["recorded"] is False
    db.refresh(arduino)
    assert arduino.status == AssetStatus.CHECKED_OUT

    ok = client.post("/api/reusable/complete", headers=device_headers,
                     json={**body, "lid_opened": True, "lid_closed": True}).json()
    assert ok["recorded"] is True and ok["lcd2"] == "RETURN RECORDED"
    db.refresh(arduino)
    assert arduino.status == AssetStatus.AVAILABLE and arduino.holder_id is None
    assert db.query(AssetTransaction).filter_by(action="RETURN", source="BIN").count() == 1


def test_available_item_scanned_without_request_is_not_released(client, arduino, bin_node,
                                                               device_headers):
    assert _scan(client, device_headers, arduino.nfc_uid)["lcd2"] == "TAKE VIA PORTAL"


def test_unknown_tag_is_remembered_and_assignable(client, db, staff, lab, bin_node, device_headers):
    assert _scan(client, device_headers, "04 11 22 33 44 55 66")["action"] == "UNKNOWN"
    h = auth_headers(client, staff.email)
    last = client.get("/api/reusable/last-unknown", headers=h).json()
    assert last["nfc_uid"] == "04112233445566"
    item = Asset(asset_tag="MULTI-001", name="Multimeter", lab_id=lab.id)
    db.add(item)
    db.commit()
    r = client.put(f"/api/reusable/assets/{item.id}/tag", headers=h, json={"nfc_uid": last["nfc_uid"]})
    assert r.status_code == 200 and r.json()["nfc_uid"] == "04112233445566"
    other = Asset(asset_tag="MULTI-002", name="Multimeter 2", lab_id=lab.id)
    db.add(other)
    db.commit()
    assert client.put(f"/api/reusable/assets/{other.id}/tag", headers=h,
                      json={"nfc_uid": "04112233445566"}).status_code == 409


def test_bin_offline_refuses_checkout(client, db, staff, lab, bin_node, arduino):
    bin_node.last_seen_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.commit()
    r = client.post("/api/reusable/checkout", headers=auth_headers(client, staff.email),
                    json={"asset_id": arduino.id})
    assert r.status_code == 409 and "offline" in r.json()["detail"]


def test_item_list_hides_holder_names_from_other_students(client, db, staff, alice, bob, lab,
                                                         bin_node, arduino):
    arduino.status, arduino.holder_id = AssetStatus.CHECKED_OUT, alice.id
    db.commit()
    def holder(user):
        body = client.get(f"/api/reusable/items?lab_id={lab.id}",
                          headers=auth_headers(client, user.email)).json()
        item = next(i for i in body["items"] if i["asset_tag"] == "ARDUINO-001")
        return item["holder"], "nfc_uid" in item
    assert holder(staff) == ("Alice", True)
    assert holder(alice) == ("you", False)
    assert holder(bob) == (None, False)


def test_only_bin_items_are_listed_not_fixed_equipment(client, db, staff, lab, bin_node):
    db.add(Asset(asset_tag="BREADBOARD-009", name="Breadboard", lab_id=lab.id, bin_item=True))
    db.add(Asset(asset_tag="AC-004", name="12V Solenoid Door Lock", lab_id=lab.id))
    db.commit()
    body = client.get(f"/api/reusable/items?lab_id={lab.id}",
                      headers=auth_headers(client, staff.email)).json()
    tags = [i["asset_tag"] for i in body["items"]]
    assert "BREADBOARD-009" in tags and "AC-004" not in tags
