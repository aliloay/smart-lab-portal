"""2026-11-18 (owner): a lab PC card is renamed to its sticker / camera-box name. Admin only, audited, id kept."""
from app.models import AuditLog, Device, DeviceType
from tests.conftest import auth_headers


def test_admin_renames_a_pc_card_and_it_is_audited(client, db, lab, admin, alice):
    d = Device(device_uid="PC_GIULAB20-PC11", name="PC_GIULAB20-PC11", device_type=DeviceType.PC, lab_id=lab.id)
    db.add(d); db.commit()
    assert client.patch(f"/api/devices/{d.id}/name", headers=auth_headers(client, alice.email),
                        json={"name": "PC-08"}).status_code == 403
    r = client.patch(f"/api/devices/{d.id}/name", headers=auth_headers(client, admin.email), json={"name": "  PC-08 "})
    assert r.status_code == 200, r.text
    db.refresh(d)
    assert d.name == "PC-08" and d.device_uid == "PC_GIULAB20-PC11"
    a = db.query(AuditLog).filter_by(action="DEVICE_RENAMED", entity_id=str(d.id)).one()
    assert a.detail["from"] == "PC_GIULAB20-PC11" and a.detail["to"] == "PC-08"
    assert client.patch(f"/api/devices/{d.id}/name", headers=auth_headers(client, admin.email),
                        json={"name": ""}).status_code == 422
