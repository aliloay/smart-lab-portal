"""2026-10-18 live findings.

1. The bins are SENSOR_NODE devices too; "the most recently seen sensor node" of a lab picked a bin
   (reports every second) as the environment node.
2. A bin weighing every second was shown STALE for hours: its confirmed-count time only moves when a
   reading confirms the count, and readings resting between two counts confirm nothing."""
from datetime import datetime, timedelta, timezone

from app.models import Device, DeviceType, InventoryBin, InventoryMeasurement, SensorReading
from app.services import environment, inventory


def test_the_environment_node_is_not_a_bin(db, lab):
    now = datetime.now(timezone.utc)
    env = Device(device_uid="ENV_T", name="Environment node", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                 last_seen_at=now - timedelta(seconds=8), is_online=True, component_state={"dht22": True})
    binn = Device(device_uid="BIN_T", name="Bin", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                  last_seen_at=now, is_online=True, component_state={"hx711": True})
    db.add_all([env, binn, SensorReading(lab_id=lab.id, metric="temperature", value=26.5, unit="C", recorded_at=now)])
    db.commit()
    assert environment.node(db, lab).device_uid == "ENV_T"
    assert environment.latest(db, lab, now)["node"]["device_uid"] == "ENV_T"


def test_a_bin_is_fresh_while_its_readings_arrive(db, lab):
    now = datetime.now(timezone.utc)
    dev = Device(device_uid="BIN_F", name="Bin", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                 last_seen_at=now, is_online=True)
    db.add(dev)
    db.commit()
    b = InventoryBin(code="BIN-F", lab_id=lab.id, device_id=dev.id, item_name="resistors", tare_g=100.0,
                     unit_mass_g=0.2, last_mass_g=106.0, last_measured_at=now - timedelta(hours=4))
    db.add(b)
    db.commit()
    db.add(InventoryMeasurement(bin_id=b.id, mass_g=106.09, recorded_at=now - timedelta(seconds=1)))
    db.commit()
    o = inventory.bin_out(db, b, now)
    assert o["quality"] == "VALID" and o["qty_est"] == 30
    assert o["measured_at"] is not None and o["last_reading_at"] is not None
