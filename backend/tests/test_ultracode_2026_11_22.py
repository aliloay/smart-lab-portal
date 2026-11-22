"""ultracode 2026-11-22 regression tests (reports/claude-ultracode-full-system-upgrade-2026-11-22)."""
import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core import csvsafe
from app.models import Alert, Asset, AssetStatus, Booking, BookingStatus, Device, DeviceType
from tests.conftest import auth_headers


# ------------------------------------------------------------ B-02 device lab scope ---
@pytest.fixture
def node(db, lab) -> Device:
    d = Device(device_uid="ENV_SCOPED", name="Env", lab_id=lab.id, device_type=DeviceType.SENSOR_NODE,
               last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


def test_own_key_cannot_raise_smoke_in_another_lab(client, db, admin, lab, other_lab, node):
    key = client.post(f"/api/devices/{node.id}/key", headers=auth_headers(client, admin.email)).json()["device_key"]
    r = client.post("/api/access/telemetry", headers={"X-Device-Key": key}, json={
        "device_uid": "ENV_SCOPED", "lab_id": other_lab.code, "readings": [{"metric": "smoke", "value": 1}]})
    assert r.status_code == 403
    assert db.query(Alert).count() == 0
    ok = client.post("/api/access/telemetry", headers={"X-Device-Key": key}, json={
        "device_uid": "ENV_SCOPED", "lab_id": lab.code, "readings": [{"metric": "temperature", "value": 22}]})
    assert ok.status_code == 200


def test_shared_key_unchanged(client, lab, other_lab, node, device_headers):
    r = client.post("/api/access/telemetry", headers=device_headers, json={
        "device_uid": "ENV_SCOPED", "lab_id": other_lab.code, "readings": [{"metric": "temperature", "value": 22}]})
    assert r.status_code == 200


# ------------------------------------------------------------ B-03 bin items ---
def test_student_cannot_check_out_a_smart_bin_item_by_hand(client, db, alice, lab):
    a = Asset(asset_tag="BB-9", name="Breadboard", lab_id=lab.id, nfc_uid="04A29999", bin_item=True)
    db.add(a)
    db.commit()
    r = client.post(f"/api/assets/{a.id}/checkout", headers=auth_headers(client, alice.email))
    assert r.status_code == 409
    db.refresh(a)
    assert a.status == AssetStatus.AVAILABLE


def test_plain_asset_checkout_still_works(client, db, alice, lab):
    a = Asset(asset_tag="SCOPE-1", name="Oscilloscope", lab_id=lab.id)
    db.add(a)
    db.commit()
    assert client.post(f"/api/assets/{a.id}/checkout", headers=auth_headers(client, alice.email)).status_code == 200


# ------------------------------------------------------------ B-05 swap proof ---
def test_rescanning_an_item_already_in_the_bin_does_not_close_someone_elses_loan(client, db, bob, lab, device_headers):
    Device_ = Device(device_uid="REUSE_BIN_1", name="Reusable bin", lab_id=lab.id, device_type=DeviceType.SENSOR_NODE,
                     last_seen_at=datetime.now(timezone.utc), component_state={"reusable_bin": True})
    bb1 = Asset(asset_tag="BB-1", name="Breadboard 1", lab_id=lab.id, nfc_uid="04BB0001")
    bb2 = Asset(asset_tag="BB-2", name="Breadboard 2", lab_id=lab.id, nfc_uid="04BB0002",
                status=AssetStatus.CHECKED_OUT, holder_id=bob.id, checked_out_at=datetime.now(timezone.utc))
    db.add_all([Device_, bb1, bb2])
    db.commit()
    r = client.post("/api/reusable/complete", headers=device_headers, json={
        "device_uid": "REUSE_BIN_1", "nfc_uid": "04BB0001", "lid_opened": True, "lid_closed": True,
        "mass_before_g": 500.0, "mass_after_g": 500.0}).json()
    assert r["recorded"] is False
    db.refresh(bb2)
    assert bb2.status == AssetStatus.CHECKED_OUT and bb2.holder_id == bob.id


# ------------------------------------------------------------ B-08 CSV ---
def test_csv_cells_cannot_run_as_formulas():
    buf = io.StringIO()
    csvsafe.writer(buf).writerow(['=HYPERLINK("http://x")', "+1", "-2", "@SUM(A1)", "normal", -3.5])
    line = buf.getvalue().strip()
    assert line.startswith("\"'=HYPERLINK") and ",'+1,'-2,'@SUM(A1),normal,-3.5" in line


# ------------------------------------------------------------ B-09 camera event meta ---
@pytest.mark.parametrize("meta", ["[]", json.dumps({"device_uid": "CAM_X", "kind": "PERSON", "zone_id": "abc"})])
def test_malformed_camera_event_meta_is_422_not_500(client, meta, device_headers):
    r = client.post("/api/security/events", headers=device_headers, data={"meta": meta})
    assert r.status_code == 422


# ------------------------------------------------------------ B-10 booking states ---
def test_completed_booking_cannot_be_reconfirmed_or_cancelled(client, db, alice, staff, lab):
    past = datetime.now(timezone.utc) - timedelta(days=2)
    b = Booking(user_id=alice.id, lab_id=lab.id, start_time=past, end_time=past + timedelta(hours=1),
                status=BookingStatus.COMPLETED, reason="done")
    db.add(b)
    db.commit()
    assert client.post(f"/api/bookings/{b.id}/confirm", headers=auth_headers(client, staff.email)).status_code == 409
    assert client.post(f"/api/bookings/{b.id}/cancel", headers=auth_headers(client, alice.email)).status_code == 409


# ------------------------------------------------------------ K2 model question ---
def test_robot_model_question_is_not_answered_with_the_ai_model(client, staff):
    r = client.post("/api/ai/ask", headers=auth_headers(client, staff.email), json={"question": "What model is the UR5e?"})
    assert r.status_code == 200
    assert r.json().get("tools_used") != ["instant:ai_model"]


def test_ai_model_question_still_answered(client, staff):
    r = client.post("/api/ai/ask", headers=auth_headers(client, staff.email),
                    json={"question": "Which model does the assistant use?"})
    assert r.json().get("tools_used") == ["instant:ai_model"]


# ------------------------------------------------------------ B-07 websocket rights ---
def test_role_change_updates_open_socket_rights():
    from app.ws.manager import Client, ConnectionManager
    m = ConnectionManager()
    ws = object()
    m._clients[ws] = Client(user_id=7, is_staff=True, lab_filter=None)
    assert m.update_rights(7, is_staff=False) == 1
    assert m._clients[ws].is_staff is False
    m.update_rights(7, is_staff=False, active=False)
    assert ws not in m._clients
