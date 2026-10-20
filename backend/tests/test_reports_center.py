"""Reports Centre, cross-system timeline and inventory discrepancies (2026-10-17)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.models import Alert, AlertSeverity, AuditLog, InventoryBin, InventoryTransaction
from tests.conftest import auth_headers


def test_catalogue_and_students_are_refused(client, staff, alice):
    hs, ha = auth_headers(client, staff.email), auth_headers(client, alice.email)
    kinds = {r["kind"] for r in client.get("/api/reports-center", headers=hs).json()}
    assert {"access", "environment", "robots", "cameras", "pcs", "inventory", "alerts"} <= kinds
    assert client.get("/api/reports-center", headers=ha).status_code == 403
    assert client.get("/api/reports-center/alerts", headers=ha).status_code == 403
    assert client.get("/api/reports-center/timeline", headers=ha).status_code == 403


def test_empty_period_is_flagged_as_missing_not_zero(client, staff):
    r = client.get("/api/reports-center/robots?days=3", headers=auth_headers(client, staff.email)).json()
    assert r["count"] == 0 and any("missing data, not a zero" in w for w in r["warnings"])
    assert r["source"] == "robot_events"


def test_alert_report_json_and_csv_with_source_and_audit(client, db, staff, lab):
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="Door held open"))
    db.commit()
    h = auth_headers(client, staff.email)
    j = client.get("/api/reports-center/alerts?days=2", headers=h).json()
    assert j["count"] == 1 and j["rows"][0]["title"] == "Door held open" and j["rows"][0]["lab"] == lab.code
    c = client.get("/api/reports-center/alerts?days=2&format=csv", headers=h)
    assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv")
    assert c.text.startswith("# Alerts | source: alerts") and "Door held open" in c.text
    assert db.query(AuditLog).filter_by(action="REPORT_EXPORTED", entity_id="alerts").count() == 1
    assert client.get("/api/reports-center/nope", headers=h).status_code == 404
    assert client.get("/api/reports-center/alerts?start=2026-10-10&end=2026-10-01", headers=h).status_code == 422


def test_timeline_groups_by_timing_only_and_names_people_only_from_the_record(client, db, staff, alice, lab):
    now = datetime.now(timezone.utc)
    db.execute(text("""insert into access_events (event_type, lab_id, user_id, method, result, message, created_at, provenance)
                       values ('ENTRY', :lab, :u, 'RFID', 'GRANTED', 'Access granted', :t, 'SOFTWARE_TEST')"""),
               {"lab": lab.id, "u": alice.id, "t": now - timedelta(seconds=60)})
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="Smoke reading", created_at=now - timedelta(seconds=30)))
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.INFO, title="Much later", created_at=now - timedelta(hours=5)))
    db.commit()
    t = client.get("/api/reports-center/timeline?days=1", headers=auth_headers(client, staff.email)).json()
    items = t["items"]
    door = next(i for i in items if i["source"] == "door")
    smoke = next(i for i in items if i["summary"] == "Smoke reading")
    later = next(i for i in items if i["summary"] == "Much later")
    assert door["person"] == alice.full_name and smoke["person"] is None       # never inferred from timing
    assert door["group"] is not None and door["group"] == smoke["group"]       # co-occurring (2 subsystems)
    assert later["group"] is None
    assert "timing only" in t["note"] and door["ref"].startswith("access_events#")


def test_inventory_discrepancy_from_last_count_and_scale(client, db, staff, lab):
    b = InventoryBin(code="BIN_T", lab_id=lab.id, item_name="Resistors", tare_g=100.0, unit_mass_g=10.0,
                     noise_g=2.0, last_mass_g=100.0 + 7 * 10.0, is_active=True)
    db.add(b)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(InventoryTransaction(bin_id=b.id, kind="COUNT", actual_count=10, qty_est_after=10, attribution="STAFF_COUNT",
                                recorded_at=now - timedelta(hours=2)))
    db.add(InventoryTransaction(bin_id=b.id, kind="WITHDRAWAL", delta_qty_est=-1, attribution="NOBODY_INSIDE",
                                recorded_at=now - timedelta(hours=1)))
    db.commit()
    r = client.get("/api/reports-center/inventory-discrepancies", headers=auth_headers(client, staff.email)).json()
    row = next(x for x in r["bins"] if x["bin"] == "BIN_T")
    # counted 10, the scale saw 1 taken -> expected 9; the scale now measures 7 -> 2 unexplained.
    assert row["expected_qty"] == 9 and row["measured_qty"] == 7 and row["difference"] == -2
    assert row["status"] == "DISCREPANCY" and row["unattributed_withdrawals"] == 1


def test_asset_lifecycle_flags_overdue_checkout_maintenance_and_faults(client, db, staff, alice, lab):
    from app.models import Asset
    now = datetime.now(timezone.utc)
    db.add_all([Asset(asset_tag="MM-01", name="Multimeter", lab_id=lab.id, holder_id=alice.id,
                      checked_out_at=now - timedelta(hours=30)),
                Asset(asset_tag="OSC-01", name="Oscilloscope", lab_id=lab.id, next_maintenance_at=now - timedelta(days=1)),
                Asset(asset_tag="OK-01", name="Fine", lab_id=lab.id)])
    db.commit()
    r = client.get("/api/reports-center/asset-lifecycle", headers=auth_headers(client, staff.email)).json()
    by = {a["asset_tag"]: a for a in r["assets"]}
    assert by["MM-01"]["holder"] == alice.full_name and by["MM-01"]["flags"][0].startswith("OVERDUE")
    assert by["OSC-01"]["flags"] == ["MAINTENANCE_DUE"] and by["OK-01"]["flags"] == []
    assert r["flagged"] == 2
