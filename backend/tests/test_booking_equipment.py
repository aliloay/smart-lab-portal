"""Equipment chosen while booking: smart-bin items, consumables, workstation."""
from datetime import timedelta

import pytest

from app.models import Asset, AssetStatus, BookingItem, InventoryBin
from tests.conftest import auth_headers


@pytest.fixture
def kit(db, lab):
    bb = Asset(asset_tag="BB-1", name="Breadboard 1", category="Tool", lab_id=lab.id,
               status=AssetStatus.AVAILABLE, notes="", nfc_uid="04AA", bin_item=True)
    ur = Asset(asset_tag="RB-1", name="UR5e", category="Manipulator", lab_id=lab.id,
               status=AssetStatus.AVAILABLE, notes="")
    fixed = Asset(asset_tag="FX-1", name="Oscilloscope", category="Instrument", lab_id=lab.id,
                  status=AssetStatus.AVAILABLE, notes="")
    leds = InventoryBin(code="LED", lab_id=lab.id, item_name="Red LEDs", category="component")
    db.add_all([bb, ur, fixed, leds])
    db.commit()
    return {"bb": bb.id, "ur": ur.id, "fixed": fixed.id, "leds": leds.id}


def _window(now, h0=2, h1=4):
    s = (now + timedelta(hours=h0)).replace(minute=0, second=0, microsecond=0)
    return s.isoformat(), (s + timedelta(hours=h1 - h0)).isoformat()


def _book(client, h, lab, now, equipment, h0=2, h1=4):
    s, e = _window(now, h0, h1)
    return client.post("/api/bookings", headers=h, json={
        "lab_id": lab.id, "start_time": s, "end_time": e, "reason": "test", "equipment": equipment})


def test_options_list_bin_items_consumables_and_workstations(client, alice, lab, kit, now):
    h = auth_headers(client, alice.email)
    s, e = _window(now)
    r = client.get("/api/bookings/equipment-options", headers=h,
                   params={"lab_id": lab.id, "start_time": s, "end_time": e})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [i["name"] for i in d["bin_items"]] == ["Breadboard 1"]          # not the oscilloscope
    assert [c["name"] for c in d["consumables"]] == ["Red LEDs"]
    assert [w["key"] for w in d["workstations"]] == [f"ASSET:{kit['ur']}", "PC"]


def test_booking_stores_the_choices(client, db, alice, lab, kit, now):
    h = auth_headers(client, alice.email)
    r = _book(client, h, lab, now, {"bin_asset_ids": [kit["bb"]],
                                    "consumables": [{"inventory_bin_id": kit["leds"], "quantity": 5}],
                                    "workstation": f"ASSET:{kit['ur']}"})
    assert r.status_code == 201, r.text
    eq = {(i["kind"], i["label"], i["quantity"]) for i in r.json()["equipment"]}
    assert eq == {("BIN_ITEM", "Breadboard 1", None), ("CONSUMABLE", "Red LEDs", 5),
                  ("WORKSTATION", "UR5e", None)}


def test_none_everywhere_is_fine(client, db, alice, lab, kit, now):
    h = auth_headers(client, alice.email)
    r = _book(client, h, lab, now, {"bin_asset_ids": [], "consumables": [], "workstation": "NONE"})
    assert r.status_code == 201, r.text
    assert r.json()["equipment"] == []
    r = _book(client, h, lab, now, None, h0=5, h1=6)                       # old clients: no field
    assert r.status_code == 201, r.text


def test_an_item_is_held_by_one_overlapping_booking(client, db, alice, bob, lab, kit, now):
    lab.exclusive_booking = False
    db.commit()
    assert _book(client, auth_headers(client, alice.email), lab, now,
                 {"bin_asset_ids": [kit["bb"]], "workstation": f"ASSET:{kit['ur']}"}).status_code == 201
    hb = auth_headers(client, bob.email)
    r = _book(client, hb, lab, now, {"bin_asset_ids": [kit["bb"]]}, h0=3, h1=5)   # overlaps
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EQUIPMENT_RESERVED"
    r = _book(client, hb, lab, now, {"workstation": f"ASSET:{kit['ur']}"}, h0=3, h1=5)
    assert r.status_code == 409
    r = _book(client, hb, lab, now, {"bin_asset_ids": [kit["bb"]]}, h0=4, h1=6)   # starts as it ends
    assert r.status_code == 201, r.text
    s, e = _window(now, 3, 5)
    opts = client.get("/api/bookings/equipment-options", headers=hb,
                      params={"lab_id": lab.id, "start_time": s, "end_time": e}).json()
    assert opts["bin_items"][0]["state"] == "RESERVED"


def test_fixed_equipment_and_other_labs_items_are_refused(client, db, alice, lab, other_lab, kit, now):
    h = auth_headers(client, alice.email)
    r = _book(client, h, lab, now, {"bin_asset_ids": [kit["fixed"]]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EQUIPMENT_UNKNOWN"
    r = _book(client, h, other_lab, now, {"bin_asset_ids": [kit["bb"]]})
    assert r.status_code == 409
    assert db.query(BookingItem).count() == 0


def test_robot_and_pc_together(client, db, alice, lab, kit, now):
    h = auth_headers(client, alice.email)
    r = _book(client, h, lab, now, {"workstations": [f"ASSET:{kit['ur']}", "PC"]})
    assert r.status_code == 201, r.text
    assert sorted(i["label"] for i in r.json()["equipment"]) == ["Lab PC", "UR5e"]
