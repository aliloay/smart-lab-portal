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


def test_staff_takes_several_and_the_weight_says_how_many(client, db, staff, alice, lab, bin_node,
                                                          device_headers):
    """Owner 2026-10-13: pick several breadboards at once; the weight decides how many left."""
    bbs = []
    for n in (1, 2, 3):
        a = Asset(asset_tag=f"RB-T-00{n}", name=f"Breadboard {n}", lab_id=lab.id,
                  nfc_uid=f"1D00000000000{n}", bin_item=True, unit_mass_g=32.8)
        db.add(a)
        bbs.append(a)
    db.commit()
    r = client.post("/api/reusable/staff-checkout", headers=auth_headers(client, staff.email),
                    json={"asset_ids": [b.id for b in bbs], "user_id": alice.id})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    client.get("/api/access/commands/next?device_uid=REUSE_BIN_1", headers=device_headers)
    done = client.post("/api/reusable/checkout-complete", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "command_id": cid, "lid_opened": True, "lid_closed": True,
        "mass_before_g": 104.5, "mass_after_g": 38.8}).json()        # -65.7 g = 2 boards
    assert done["recorded"] is True
    for b in bbs:
        db.refresh(b)
    out = [b for b in bbs if b.status == AssetStatus.CHECKED_OUT]
    assert len(out) == 2 and all(b.holder_id == alice.id for b in out)


# ------------------------------------------- live hint to open pages (2026-11-16) ---
@pytest.fixture
def published(monkeypatch):
    """Everything the portal would push over the live socket during the test."""
    from app.ws.manager import manager
    sent: list[dict] = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    return sent


def _hints(published):
    return [m for m in published if m.get("type") == "reusable_update"]


def test_accepted_scan_pushes_a_hint_without_uid_or_names(client, arduino, bin_node, device_headers, lab, published):
    assert _scan(client, device_headers, arduino.nfc_uid)["lcd2"] == "TAKE VIA PORTAL"
    h = _hints(published)
    assert len(h) == 1 and {k: h[0][k] for k in ("type", "lab_id", "kind")} == {"type": "reusable_update", "lab_id": lab.id, "kind": "scan"}
    assert set(h[0]) == {"type", "lab_id", "kind", "eid", "acc_ms"}
    assert arduino.nfc_uid not in str(h) and arduino.name not in str(h)


def test_unknown_tag_also_pushes_so_the_assign_screen_updates(client, bin_node, device_headers, published):
    assert _scan(client, device_headers, "04 11 22 33 44 55 66")["action"] == "UNKNOWN"
    assert len(_hints(published)) == 1


def test_rejected_report_pushes_nothing(client, arduino, bin_node, published):
    r = client.post("/api/reusable/scan", headers={"X-Device-Key": "wrong"},
                    json={"device_uid": "REUSE_BIN_1", "nfc_uid": arduino.nfc_uid})
    assert r.status_code in (401, 403)
    assert _hints(published) == []


def test_unexplained_weight_change_pushes_a_hint(client, bin_node, device_headers, lab, published):
    r = client.post("/api/reusable/weight-change", headers=device_headers,
                    json={"device_uid": "REUSE_BIN_1", "delta_g": -120.0, "mass_g": 500.0})
    assert r.status_code == 200
    h = _hints(published)
    assert len(h) == 1 and {k: h[0][k] for k in ("type", "lab_id", "kind")} == {"type": "reusable_update", "lab_id": lab.id, "kind": "weight"}


def test_hint_reaches_only_its_lab_and_any_signed_in_user():
    from app.ws.manager import Client, manager
    msg = {"type": "reusable_update", "lab_id": 7, "kind": "scan"}
    assert manager._wants(Client(user_id=1, is_staff=False, lab_filter=None), msg)
    assert manager._wants(Client(user_id=1, is_staff=False, lab_filter=7), msg)
    assert not manager._wants(Client(user_id=1, is_staff=False, lab_filter=8), msg)


# ------------------- which lab a bin node belongs to (2026-11-16: LAB_ID "BENCH" vs "LAB_01") ---
# The heartbeat's lab_id is a lab CODE looked up in Lab.code. The Modular firmware (reuse-mod-0.1, the one the portal
# last heard from) reports "LAB_01"; the older single-file firmware (reuse-0.3, kept for reference) still says "BENCH".
def _beat(client, headers, lab_code, uid="REUSE_BIN_1"):
    return client.post("/api/access/heartbeat", headers=headers, json={
        "device_uid": uid, "lab_id": lab_code, "device_type": "SENSOR_NODE", "firmware_version": "reuse-mod-0.1",
        "components": {"reusable_bin": True, "hx711": True}})


def test_heartbeat_with_the_labs_code_keeps_the_bin_in_that_lab(client, db, bin_node, lab, device_headers):
    r = _beat(client, device_headers, lab.code)
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["lab"] == lab.code
    db.expire_all()
    assert db.get(Device, bin_node.id).lab_id == lab.id


def test_heartbeat_naming_an_unknown_lab_changes_nothing(client, db, bin_node, lab, device_headers):
    before = (bin_node.lab_id, bin_node.last_seen_at, dict(bin_node.component_state or {}))
    r = _beat(client, device_headers, "BENCH")
    assert r.status_code == 200 and r.json() == {"status": "unknown_lab"}
    db.expire_all()
    d = db.get(Device, bin_node.id)
    assert (d.lab_id, d.last_seen_at, dict(d.component_state or {})) == before
    assert db.query(Device).filter(Device.device_uid == "REUSE_BIN_1").count() == 1   # no duplicate node


def test_repeated_heartbeats_do_not_duplicate_the_node(client, db, lab, device_headers):
    for _ in range(3):
        assert _beat(client, device_headers, lab.code, uid="REUSE_BIN_NEW").json()["status"] == "ok"
    assert db.query(Device).filter(Device.device_uid == "REUSE_BIN_NEW").count() == 1


def test_bin_hint_names_the_lab_the_node_belongs_to(client, bin_node, device_headers, lab, published):
    client.post("/api/reusable/scan", headers=device_headers, json={"device_uid": "REUSE_BIN_1", "nfc_uid": "04 AA BB CC DD"})
    assert [m["lab_id"] for m in published if m.get("type") == "reusable_update"] == [lab.id]


# ------------------------------- per-stage timing and correlation id (2026-11-16) ---
def test_each_accepted_report_gets_its_own_event_id_and_timing(client, arduino, bin_node, device_headers, published):
    from app.api.routes import reusable as rr
    rr._timings.clear()
    _scan(client, device_headers, arduino.nfc_uid)
    client.post("/api/reusable/weight-change", headers=device_headers,
                json={"device_uid": "REUSE_BIN_1", "delta_g": 0.0, "mass_g": 0.0})
    hints = _hints(published)
    assert [h["kind"] for h in hints] == ["scan", "weight"]
    assert len({h["eid"] for h in hints}) == 2 and all(len(h["eid"]) == 12 for h in hints)
    for h in hints:
        assert isinstance(h["acc_ms"], float) and 0 <= h["acc_ms"] < 5000          # request received -> accepted
    assert [t["eid"] for t in rr._timings] == [h["eid"] for h in hints]            # same ids in the diagnostics ring
    assert all(t["pub_ms"] >= 0 for t in rr._timings)                              # publish (enqueue) measured after, never before, acceptance


def test_the_hint_carries_no_identifier_or_device_clock(client, arduino, bin_node, device_headers, published):
    _scan(client, device_headers, arduino.nfc_uid)
    h = _hints(published)[0]
    assert set(h) == {"type", "lab_id", "kind", "eid", "acc_ms"}                  # no uid, name, weight, user or device timestamp


def test_rejected_and_unknown_device_reports_publish_no_timing(client, arduino, bin_node, published):
    from app.api.routes import reusable as rr
    rr._timings.clear()
    r = client.post("/api/reusable/scan", headers={"X-Device-Key": "wrong"},
                    json={"device_uid": "REUSE_BIN_1", "nfc_uid": arduino.nfc_uid})
    assert r.status_code in (401, 403) and _hints(published) == [] and not rr._timings


def test_timing_ring_is_bounded():
    from app.api.routes import reusable as rr
    assert rr._timings.maxlen == 200
