"""
Reusable smart bin (Robotics Lab, System 4), backend side.

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


# ---------------------------------------------- load cell: third proof ---
from app.api.routes.reusable import weight_check  # noqa: E402
from app.models import Alert  # noqa: E402


def test_weight_check_rules():
    assert weight_check(None, None) == "NO_SCALE"
    assert weight_check(None, 25.0) == "LEARNED"            # first return teaches the mass
    assert weight_check(None, 0.4) == "MISMATCH"            # nothing went in
    assert weight_check(25.0, 26.5) == "MATCH"
    assert weight_check(25.0, 0.3) == "MISMATCH"
    assert weight_check(25.0, 50.0) == "MISMATCH"           # two boards
    assert weight_check(200.0, 225.0) == "MATCH"            # 15 % of a heavy item


def _return(client, device_headers, uid, before, after):
    _scan(client, device_headers, uid)
    return client.post("/api/reusable/complete", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "nfc_uid": uid, "lid_opened": True, "lid_closed": True,
        "mass_before_g": before, "mass_after_g": after}).json()


def test_return_learns_the_mass_then_flags_an_empty_return(client, db, alice, lab, bin_node,
                                                           arduino, device_headers):
    arduino.status, arduino.holder_id = AssetStatus.CHECKED_OUT, alice.id
    db.commit()
    r = _return(client, device_headers, arduino.nfc_uid, 100.0, 125.2)
    assert r["recorded"] and r["weight_check"] == "LEARNED"
    db.refresh(arduino)
    assert arduino.unit_mass_g == 25.2

    # Next time only the tag is scanned, the board stays in the pocket.
    arduino.status, arduino.holder_id = AssetStatus.CHECKED_OUT, alice.id
    db.commit()
    r = _return(client, device_headers, arduino.nfc_uid, 125.2, 125.4)
    assert r["recorded"] and r["weight_check"] == "MISMATCH" and r["lcd2"] == "CHECK WEIGHT"
    alert = db.query(Alert).one()
    assert "ARDUINO-001" in alert.title and "may not be in the bin" in alert.detail
    tx = db.query(AssetTransaction).filter_by(action="RETURN").order_by(AssetTransaction.id).all()[-1]
    assert tx.weight_check == "MISMATCH" and tx.mass_delta_g == 0.2


def test_checkout_that_removes_two_items_is_flagged(client, db, alice, lab, bin_node,
                                                    arduino, device_headers):
    arduino.unit_mass_g = 25.0
    db.commit()
    _inside(db, alice, lab)
    h = auth_headers(client, alice.email)
    assert client.post("/api/reusable/checkout", headers=h, json={"asset_id": arduino.id}).status_code == 200
    client.get("/api/access/commands/next?device_uid=REUSE_BIN_1", headers=device_headers)
    r = client.post("/api/reusable/scan", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "nfc_uid": arduino.nfc_uid, "mass_delta_g": -50.4}).json()
    assert r["action"] == "CHECKOUT_OK" and r["weight_check"] == "MISMATCH"
    db.refresh(arduino)
    assert arduino.status == AssetStatus.CHECKED_OUT          # the tag decides; the scale alerts
    assert db.query(Alert).count() == 1


def test_checkout_matching_one_item_is_quiet(client, db, alice, lab, bin_node, arduino, device_headers):
    arduino.unit_mass_g = 25.0
    db.commit()
    _inside(db, alice, lab)
    h = auth_headers(client, alice.email)
    client.post("/api/reusable/checkout", headers=h, json={"asset_id": arduino.id})
    client.get("/api/access/commands/next?device_uid=REUSE_BIN_1", headers=device_headers)
    r = client.post("/api/reusable/scan", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "nfc_uid": arduino.nfc_uid, "mass_delta_g": -24.1}).json()
    assert r["weight_check"] == "MATCH" and r["lcd2"] == "CHECKED OUT"
    assert db.query(Alert).count() == 0
    tx = db.query(AssetTransaction).one()
    assert tx.mass_delta_g == -24.1


def test_staff_set_the_mass(client, db, staff, alice, arduino):
    assert client.put(f"/api/reusable/assets/{arduino.id}/mass", headers=auth_headers(client, alice.email),
                      json={"unit_mass_g": 30}).status_code == 403
    r = client.put(f"/api/reusable/assets/{arduino.id}/mass", headers=auth_headers(client, staff.email),
                   json={"unit_mass_g": 30})
    assert r.status_code == 200 and r.json()["unit_mass_g"] == 30


# ------------------------------------------------ checkout by weight ---
from app.models import DeviceCommand, Notification  # noqa: E402


def _take(client, db, alice, arduino):
    h = auth_headers(client, alice.email)
    r = client.post("/api/reusable/checkout", headers=h, json={"asset_id": arduino.id})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _done(client, device_headers, cid, before, after, opened=True):
    return client.post("/api/reusable/checkout-complete", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "command_id": cid, "lid_opened": opened, "lid_closed": True,
        "mass_before_g": before, "mass_after_g": after}).json()


def test_checkout_confirmed_by_the_weight_drop(client, db, alice, staff, lab, bin_node, arduino,
                                               device_headers):
    _inside(db, alice, lab)
    cid = _take(client, db, alice, arduino)
    r = _done(client, device_headers, cid, 105.9, 70.6)
    assert r["recorded"] is True
    db.expire_all()
    a = db.get(Asset, arduino.id)
    assert a.status == AssetStatus.CHECKED_OUT and a.holder_id == alice.id
    assert db.get(DeviceCommand, cid).status == "DONE"
    tx = db.query(AssetTransaction).one()
    assert tx.action == "CHECKOUT" and tx.mass_delta_g == -35.3
    mine = [n.title for n in db.query(Notification).filter_by(user_id=alice.id)]
    assert "Taken: Arduino Uno" in mine
    assert any(n.title == "Arduino Uno taken" for n in db.query(Notification).filter_by(user_id=staff.id))


def test_no_weight_drop_means_nothing_was_taken(client, db, alice, lab, bin_node, arduino,
                                                device_headers):
    _inside(db, alice, lab)
    cid = _take(client, db, alice, arduino)
    r = _done(client, device_headers, cid, 105.9, 105.5)
    assert r["recorded"] is False and r["lcd2"] == "NOTHING TAKEN"
    db.expire_all()
    assert db.get(Asset, arduino.id).status == AssetStatus.AVAILABLE
    assert db.get(DeviceCommand, cid).status == "FAILED"
    assert db.query(AssetTransaction).count() == 0
    assert any(n.title == "Not taken: Arduino Uno" for n in db.query(Notification).filter_by(user_id=alice.id))


def test_return_notifies_the_holder_and_staff(client, db, alice, staff, lab, bin_node, arduino,
                                              device_headers):
    _inside(db, alice, lab)
    cid = _take(client, db, alice, arduino)
    _done(client, device_headers, cid, 105.9, 70.6)
    assert _scan(client, device_headers, arduino.nfc_uid)["action"] == "OPEN_FOR_RETURN"
    r = _return(client, device_headers, arduino.nfc_uid, 70.6, 105.8)
    assert r["recorded"] is True
    assert any(n.title == "Returned: Arduino Uno" for n in db.query(Notification).filter_by(user_id=alice.id))
    assert any(n.title == "Arduino Uno returned" for n in db.query(Notification).filter_by(user_id=staff.id))


def test_unexplained_weight_change_alerts_staff_with_an_item_guess(client, db, staff, lab, bin_node,
                                                                   arduino, device_headers):
    arduino.bin_item, arduino.unit_mass_g = True, 35.3
    db.commit()
    r = client.post("/api/reusable/weight-change", headers=device_headers,
                    json={"device_uid": "REUSE_BIN_1", "delta_g": -70.4, "mass_g": 35.5}).json()
    assert r["alerted"] is True and "about 2 items" in r["guess"]
    assert db.query(Alert).count() == 1
    small = client.post("/api/reusable/weight-change", headers=device_headers,
                        json={"device_uid": "REUSE_BIN_1", "delta_g": 0.8}).json()
    assert small["alerted"] is False


def test_returning_the_other_identical_item_closes_the_open_checkout(client, db, alice, staff, lab,
                                                                      bin_node, arduino, breadboard,
                                                                      device_headers):
    # The bin holds interchangeable items: Alice picked the Arduino in the portal
    # but physically took the breadboard; she returns the breadboard's tag.
    arduino.bin_item = breadboard.bin_item = True
    db.commit()
    _inside(db, alice, lab)
    cid = _take(client, db, alice, arduino)
    _done(client, device_headers, cid, 105.9, 70.6)
    assert _scan(client, device_headers, breadboard.nfc_uid)["action"] == "OPEN_FOR_RETURN"
    r = _return(client, device_headers, breadboard.nfc_uid, 70.6, 105.8)
    assert r["recorded"] is True
    db.expire_all()
    assert db.get(Asset, arduino.id).status == AssetStatus.AVAILABLE
    assert db.get(Asset, breadboard.id).status == AssetStatus.AVAILABLE
    assert any("returned for" in n.title for n in db.query(Notification).filter_by(user_id=staff.id))
    # Nothing out any more: the same tag again is refused.
    assert _scan(client, device_headers, breadboard.nfc_uid)["action"] == "NOT_ALLOWED"


def test_staff_take_for_someone_outside_their_booking(client, db, staff, alice, lab, bin_node,
                                                       arduino, device_headers):
    """Owner 2026-10-13: booking over, the person cannot use the bin - staff can, for them."""
    sh = auth_headers(client, staff.email)
    assert client.post("/api/reusable/staff-checkout", headers=auth_headers(client, alice.email),
                       json={"asset_id": arduino.id, "user_id": alice.id}).status_code == 403
    r = client.post("/api/reusable/staff-checkout", headers=sh,
                    json={"asset_id": arduino.id, "user_id": alice.id})
    assert r.status_code == 200, r.text
    nxt = client.get("/api/access/commands/next?device_uid=REUSE_BIN_1", headers=device_headers).json()
    assert nxt["command"] == "OPEN_LID"
    # The tag confirms it, and it is recorded against the PERSON, not the staff member.
    assert _scan(client, device_headers, arduino.nfc_uid)["action"] == "CHECKOUT_OK"
    db.refresh(arduino)
    assert arduino.status == AssetStatus.CHECKED_OUT and arduino.holder_id == alice.id


def test_staff_record_a_return(client, db, staff, alice, lab, arduino):
    sh = auth_headers(client, staff.email)
    assert client.post("/api/reusable/staff-return", headers=sh,
                       json={"asset_id": arduino.id}).status_code == 409      # not out
    arduino.status, arduino.holder_id = AssetStatus.CHECKED_OUT, alice.id
    db.commit()
    assert client.post("/api/reusable/staff-return", headers=auth_headers(client, alice.email),
                       json={"asset_id": arduino.id}).status_code == 403
    r = client.post("/api/reusable/staff-return", headers=sh,
                    json={"asset_id": arduino.id, "note": "lid sensor fault"})
    assert r.status_code == 200, r.text
    db.refresh(arduino)
    assert arduino.status == AssetStatus.AVAILABLE and arduino.holder_id is None
    tx = db.query(AssetTransaction).filter_by(asset_id=arduino.id, action="RETURN").one()
    assert tx.source == "STAFF" and tx.user_id == alice.id and tx.note == "lid sensor fault"
