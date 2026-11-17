"""
Consumable inventory (Robotics Lab, System 3), backend side.

Tested: an uncalibrated bin reports mass only (no invented count); after
calibration the estimate and its error band follow the model; stable steps
above the threshold become withdrawals/refills, noise does not; attribution
only with exactly one person inside; low-stock alert and its clearing;
physical counts record the estimation error; device binding and scope.
"""
from datetime import datetime, timezone

import pytest

from app.models import (AccessSession, Alert, AuthMethod, Device, DeviceType,
                        InventoryBin, InventoryTransaction)
from tests.conftest import auth_headers


@pytest.fixture
def node(db, lab) -> Device:
    d = Device(device_uid="BIN_NODE_1", name="Consumable node", lab_id=lab.id,
               device_type=DeviceType.SENSOR_NODE, last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


@pytest.fixture
def resistors(db, lab) -> InventoryBin:
    b = InventoryBin(code="BIN-R10K", lab_id=lab.id, item_name="10k resistors")
    db.add(b)
    db.commit()
    return b


def _report(client, headers, mass, uid="BIN_NODE_1", code="BIN-R10K"):
    return client.post("/api/inventory/measurements", headers=headers,
                       json={"device_uid": uid, "readings": [{"bin_code": code, "mass_g": mass}]})


def test_uncalibrated_bin_reports_mass_only(client, db, staff, lab, node, resistors,
                                            device_headers):
    r = _report(client, device_headers, 412.3).json()["bins"][0]
    assert r["known"] and r["qty_est"] is None and r["calibrated"] is False
    b = client.get("/api/inventory/bins", headers=auth_headers(client, staff.email)).json()[0]
    assert b["mass_g"] == 412.3 and b["qty_est"] is None and b["quality"] == "VALID"
    db.refresh(resistors)
    assert resistors.device_id == node.id                 # bound to the node that weighs it


def test_calibrated_estimate_and_transactions(client, db, staff, lab, node, resistors,
                                              device_headers):
    h = auth_headers(client, staff.email)
    client.patch(f"/api/inventory/bins/{resistors.id}", headers=h,
                 json={"tare_g": 100.0, "unit_mass_g": 0.2, "noise_g": 0.3, "reorder_qty": 300})
    first = _report(client, device_headers, 300.0).json()["bins"][0]
    assert first["qty_est"] == 1000 and first["qty_err"] == 2   # ceil(0.3 / 0.2)
    assert first["transaction"] is None                         # first reading = baseline

    assert _report(client, device_headers, 299.5).json()["bins"][0]["transaction"] is None  # < 3 x noise
    # One reading is not enough (a hand may still be on it); the next agreeing one books it.
    assert _report(client, device_headers, 280.0).json()["bins"][0]["transaction"] is None
    took = _report(client, device_headers, 280.0).json()["bins"][0]
    assert took["transaction"] == "WITHDRAWAL" and took["qty_est"] == 900
    t = db.query(InventoryTransaction).filter_by(kind="WITHDRAWAL").one()
    assert t.delta_mass_g == -20.0 and t.delta_qty_est == -100   # 299.5 = 997.5 pcs: between counts, not booked
    assert t.attribution == "NOBODY_INSIDE" and t.user_id is None


def test_single_occupant_is_linked_multiple_are_not(client, db, lab, node, resistors,
                                                    alice, bob, device_headers):
    resistors.unit_mass_g, resistors.tare_g = 0.2, 100.0
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()
    _report(client, device_headers, 300.0)
    _report(client, device_headers, 290.0)
    _report(client, device_headers, 290.0)
    t = db.query(InventoryTransaction).one()
    assert t.user_id == alice.id and t.attribution == "SINGLE_OCCUPANT"

    db.add(AccessSession(lab_id=lab.id, user_id=bob.id, entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()
    _report(client, device_headers, 280.0)
    _report(client, device_headers, 280.0)
    t2 = db.query(InventoryTransaction).order_by(InventoryTransaction.id.desc()).first()
    assert t2.user_id is None and t2.attribution == "MULTIPLE_OCCUPANTS"


def test_low_stock_alert_and_refill_clears_it(client, db, lab, node, resistors, device_headers):
    resistors.unit_mass_g, resistors.tare_g, resistors.reorder_qty = 1.0, 0.0, 50
    db.commit()
    _report(client, device_headers, 40.0)
    alert = db.query(Alert).filter_by(dedupe_key=f"inv:{resistors.id}:low").one()
    assert not alert.is_resolved and "10k resistors" in alert.title
    _report(client, device_headers, 500.0)
    assert _report(client, device_headers, 500.0).json()["bins"][0]["transaction"] == "REFILL"
    db.refresh(alert)
    assert alert.is_resolved


def test_physical_count_records_the_error(client, db, staff, lab, node, resistors, device_headers):
    resistors.unit_mass_g, resistors.tare_g = 0.2, 100.0
    db.commit()
    _report(client, device_headers, 300.0)               # estimate 1000
    r = client.post(f"/api/inventory/bins/{resistors.id}/count",
                    headers=auth_headers(client, staff.email), json={"actual_count": 990})
    assert r.json() == {"bin_code": "BIN-R10K", "estimate": 1000, "actual_count": 990,
                        "error": 10, "mass_g": 300.0, "recalibrated": False, "tare_g": 100.0}


def test_device_binding_and_permissions(client, db, lab, node, resistors, alice, device_headers):
    _report(client, device_headers, 300.0)                # binds to BIN_NODE_1
    other = Device(device_uid="BIN_NODE_2", name="Other", lab_id=lab.id,
                   device_type=DeviceType.SENSOR_NODE)
    db.add(other)
    db.commit()
    assert _report(client, device_headers, 290.0, uid="BIN_NODE_2").status_code == 403
    assert _report(client, device_headers, 290.0, code="NOPE").json()["bins"][0]["known"] is False
    assert client.get("/api/inventory/bins",
                      headers=auth_headers(client, alice.email)).status_code == 403
    assert client.post("/api/inventory/measurements",
                       json={"device_uid": "BIN_NODE_1",
                             "readings": [{"bin_code": "BIN-R10K", "mass_g": 1}]}).status_code == 401


def test_lifting_the_container_books_only_the_net_change(client, db, lab, node, resistors,
                                                         device_headers):
    """Measured on the real bin 2026-10-13: envelope 1.048 g, 0.2066 g per resistor.
    Lifting the envelope (scale ~0) and putting it back with 5 fewer is ONE
    withdrawal of 5 - not "30 taken" then "25 added"."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 1.048, 0.04
    db.commit()
    for m in (7.246, 7.25):                 # 30 pieces, confirmed
        _report(client, device_headers, m)
    for m in (0.02, -0.01, 0.03):           # envelope in someone's hand
        assert _report(client, device_headers, m).json()["bins"][0]["transaction"] is None
    _report(client, device_headers, 4.43)   # caught mid-placement: ignored
    for m in (6.21, 6.20):                  # back with 25
        last = _report(client, device_headers, m).json()["bins"][0]
    assert last["transaction"] == "WITHDRAWAL" and last["qty_est"] == 25
    t = db.query(InventoryTransaction).one()
    assert t.delta_qty_est == -5 and t.qty_est_after == 25


def test_drift_between_counts_is_not_booked_and_title_says_what_is_left(
        client, db, lab, node, resistors, device_headers, staff):
    """Owner's run 2026-10-13: 30 in, took 4 then 2. The second take settled
    6.15 -> 6.02 g; it must be booked as 2 (24 left), never as 1."""
    from app.models import Notification
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 1.048, 0.04
    db.commit()
    for m in (7.246, 7.25, 0.0, 6.45, 6.45, 0.0, 6.15, 6.15, 6.06, 6.02, 6.02):
        _report(client, device_headers, m)
    took = [t.delta_qty_est for t in db.query(InventoryTransaction).order_by(InventoryTransaction.id)]
    assert took == [-4, -2]
    titles = [n.title for n in db.query(Notification).filter(Notification.title.like("%taken%"))]
    assert any("2 pcs taken · 24 left (was 26)" in t for t in titles)


def test_zero_seen_at_the_lift_removes_drift(client, db, lab, node, resistors, device_headers):
    """Owner's run 2026-10-13: 27 resistors read 6.71 g (27.4 pcs with a drifted
    zero); the lift just before read 0.04 g. Counted from that zero: 27."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 1.048, 0.04
    db.commit()
    for m in (6.16, 6.16):                 # 25 confirmed
        _report(client, device_headers, m)
    for m in (0.16, 0.12, 0.04, 6.71, 6.71):
        last = _report(client, device_headers, m).json()["bins"][0]
    assert last["transaction"] == "REFILL" and last["qty_est"] == 27


def test_never_more_than_the_lab_owns(client, db, lab, node, resistors, device_headers):
    """Owner 2026-10-13: the lab owns 30 resistors - a rise to '31' or '32' is the load
    cell (air, creep), never a refill."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 128.63, 0.04
    resistors.stock_max = 30
    db.commit()
    for m in (134.83, 134.83):                       # 30
        _report(client, device_headers, m)
    for m in (135.25, 135.25, 135.45, 135.45):       # "32": fluctuation
        last = _report(client, device_headers, m).json()["bins"][0]
    assert last["qty_est"] == 30 and last["transaction"] is None
    assert db.query(InventoryTransaction).count() == 0
    for m in (134.83, 134.83):                       # the bump goes away: nothing booked
        _report(client, device_headers, m)
    assert db.query(InventoryTransaction).count() == 0
    for m in (133.80, 133.80):                       # a real take of 5 still counts
        last = _report(client, device_headers, m).json()["bins"][0]
    assert last["transaction"] == "WITHDRAWAL" and last["qty_est"] == 25


def test_portal_zero_absorbs_a_transport_offset(client, db, staff, lab, node, resistors, device_headers):
    """Lab day 2026-11-17: after transport the EMPTY platform read ~15 g. 'Zero scale' with the container
    off makes the glass box + 30 resistors count 30 (not 30 + 15 g / 0.2066 = 103), books nothing, and
    pressing it again replaces the offset instead of stacking it."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 128.752, 0.04
    resistors.last_mass_g = 134.95
    db.commit()
    h = auth_headers(client, staff.email)
    for m in (15.3, 15.31, 15.3):                         # container off, platform empty, settled
        _report(client, device_headers, m)
    r = client.post(f"/api/inventory/bins/{resistors.id}/zero", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["zero_offset_g"] == 15.3
    db.refresh(resistors)
    assert resistors.tare_g == round(128.752 + 15.3, 4) and resistors.last_mass_g is None
    box30 = 128.752 + 15.3 + 30 * 0.2066
    for m in (box30, box30):
        last = _report(client, device_headers, round(m, 2)).json()["bins"][0]
    assert last["qty_est"] == 30 and last["transaction"] is None
    # Container off again, the drift is now 12 g: the offset is replaced, not added.
    for m in (12.0, 12.0, 12.01):
        _report(client, device_headers, m)
    assert client.post(f"/api/inventory/bins/{resistors.id}/zero", headers=h).status_code == 200
    db.refresh(resistors)
    assert abs(resistors.tare_g - (128.752 + 12.0)) < 0.03          # replaced (a stacked offset would be ~156 g)
    assert db.query(InventoryTransaction).filter(InventoryTransaction.kind != "COUNT").count() == 0


def test_portal_zero_refuses_unsafe_cases(client, db, staff, alice, lab, node, resistors, device_headers):
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 128.752, 0.04
    db.commit()
    h = auth_headers(client, staff.email)
    url = f"/api/inventory/bins/{resistors.id}/zero"
    assert client.post(url, headers=h).status_code == 409                       # no reading at all
    for m in (150.0, 150.0, 150.0):                                              # container still on
        _report(client, device_headers, m)
    r = client.post(url, headers=h)
    assert r.status_code == 409 and "off the platform" in r.json()["detail"]
    for m in (15.0, 18.0):                                                       # not settled
        _report(client, device_headers, m)
    assert client.post(url, headers=h).status_code == 409
    assert client.post(url, headers=auth_headers(client, alice.email)).status_code == 403   # staff only
    db.refresh(resistors)
    assert resistors.tare_g == 128.752


def test_portal_zero_asks_a_bin_04_node_to_tare_itself(client, db, staff, lab, node, resistors, device_headers):
    """bin-0.4 nodes zero themselves (the LCD shows 0 too): the button only asks, once, in the next reply."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 128.752, 0.04
    node.firmware_version = "bin-0.4"
    db.commit()
    for m in (15.3, 15.3, 15.3):
        assert "tare" not in _report(client, device_headers, m).json()["bins"][0]
    r = client.post(f"/api/inventory/bins/{resistors.id}/zero", headers=auth_headers(client, staff.email))
    assert r.status_code == 200 and r.json()["zeroed_by"] == "node"
    db.refresh(resistors)
    assert resistors.tare_g == 128.752                     # unchanged: the node removes the offset itself
    assert _report(client, device_headers, 15.3).json()["bins"][0]["tare"] is True
    assert "tare" not in _report(client, device_headers, 0.0).json()["bins"][0]   # asked once only


def test_set_as_current_stock_reanchors_the_container(client, db, staff, lab, node, resistors, device_headers):
    """Lab day 2026-11-17: after Zero the box + 30 read 131.96 g net -> ~16 with the 1 Nov m0 (128.752).
    'Set as current stock = 30' moves m0 so the same reading shows 30, and later takes still count."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.2066, 146.292, 0.04
    db.commit()
    for m in (149.5, 149.5):
        last = _report(client, device_headers, m).json()["bins"][0]
    assert last["qty_est"] == 16
    h = auth_headers(client, staff.email)
    r = client.post(f"/api/inventory/bins/{resistors.id}/count", headers=h,
                    json={"actual_count": 30, "recalibrate": True})
    assert r.status_code == 201 and r.json()["recalibrated"] is True
    db.refresh(resistors)
    assert abs(resistors.tare_g - (149.5 - 30 * 0.2066)) < 1e-6
    for m in (149.5 - 5 * 0.2066,) * 2:                    # 5 taken
        last = _report(client, device_headers, round(m, 2)).json()["bins"][0]
    assert last["qty_est"] == 25 and last["transaction"] == "WITHDRAWAL"
    # refused with the container off
    for m in (17.5, 17.5):
        _report(client, device_headers, m)
    assert client.post(f"/api/inventory/bins/{resistors.id}/count", headers=h,
                       json={"actual_count": 30, "recalibrate": True}).status_code in (201, 409)


def test_slow_steps_of_a_real_take_are_not_absorbed_as_drift(client, db, lab, node, resistors, device_headers):
    """Lab 2026-11-17: 30 in the glass read 27-28 after takes/returns - small settling steps (< 0.3 pc each) were
    followed as drift and swallowed ~4 resistors. Drift is now followed at most DRIFT_STEP_G per reading."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.204, 125.5, 0.04
    db.commit()
    full = 125.5 + 30 * 0.204
    for m in (full, full):
        _report(client, device_headers, round(full, 2))
    m = full
    for _ in range(12):                                   # 3 pieces leave in 12 small steps of 0.05 g
        m -= 0.051
        last = _report(client, device_headers, round(m, 2)).json()["bins"][0]
    for _ in range(3):
        last = _report(client, device_headers, round(m, 2)).json()["bins"][0]
    assert last["qty_est"] == 27                          # booked as taken, not hidden in the empty mass
    db.refresh(resistors)
    assert abs(resistors.tare_g - 125.5) < 0.15


def test_real_slow_creep_is_still_followed(client, db, lab, node, resistors, device_headers):
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.204, 125.5, 0.04
    db.commit()
    m = 125.5 + 30 * 0.204
    for _ in range(60):                                   # 0.0015 g per reading = 0.09 g/min (9x today's creep)
        m += 0.0015
        last = _report(client, device_headers, round(m, 3)).json()["bins"][0]
    assert last["qty_est"] == 30 and last["transaction"] is None


def test_live_count_follows_every_reading_and_settles(client, db, staff, lab, node, resistors, device_headers):
    """Owner 17 Nov: the number should change with the weight at once and settle when the weight settles."""
    resistors.unit_mass_g, resistors.tare_g, resistors.noise_g = 0.204, 125.0, 0.04
    db.commit()
    full = round(125.0 + 30 * 0.204, 2)
    for m in (full, full):
        _report(client, device_headers, m)
    moving = _report(client, device_headers, round(full - 4 * 0.204, 2)).json()["bins"][0]
    assert moving["qty_est"] == 26 and moving["qty_booked"] == 30          # LCD shows 26 at once, not yet booked
    b = client.get("/api/inventory/bins", headers=auth_headers(client, staff.email)).json()[0]
    assert b["qty_live"] == 26 and b["settled"] is False
    settled = _report(client, device_headers, round(full - 4 * 0.204, 2)).json()["bins"][0]
    assert settled["qty_booked"] == 26 and settled["qty_est"] == 26
    b = client.get("/api/inventory/bins", headers=auth_headers(client, staff.email)).json()[0]
    assert b["qty_live"] == 26 and b["settled"] is True
