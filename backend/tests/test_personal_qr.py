"""Personal door QR (a card in the phone's Wallet): RFID-card rules, hash only."""
from app.models import PersonalQrCredential
from tests.conftest import auth_headers


def _validate(client, device_headers, lab, payload):
    return client.post("/api/access/validate-qr", headers=device_headers, json={
        "qr_token": payload, "lab_id": lab.code, "device_uid": "MASTER_TEST"}).json()


def test_personal_qr_is_step_one_like_a_card(client, db, alice, lab, device, device_headers):
    h = auth_headers(client, alice.email)
    r = client.post("/api/auth/me/door-qr", headers=h).json()
    payload = r["payload"]
    assert payload.startswith("SLB:~") and r["png_base64"]
    stored = db.query(PersonalQrCredential).one()
    assert payload not in stored.token_sha256                       # only the hash is kept
    v = _validate(client, device_headers, lab, payload)
    assert v["valid"] is True and v["auth_subject"] == alice.auth_subject
    assert client.get("/api/auth/me/door-qr", headers=h).json()["active"] is True


def test_replacing_or_revoking_kills_the_old_qr(client, db, alice, lab, device, device_headers):
    h = auth_headers(client, alice.email)
    old = client.post("/api/auth/me/door-qr", headers=h).json()["payload"]
    new = client.post("/api/auth/me/door-qr", headers=h).json()["payload"]
    assert _validate(client, device_headers, lab, old)["valid"] is False
    assert _validate(client, device_headers, lab, new)["valid"] is True
    client.delete("/api/auth/me/door-qr", headers=h)
    assert _validate(client, device_headers, lab, new)["valid"] is False
    assert db.query(PersonalQrCredential).count() == 2              # history kept


def test_lab_requiring_a_booking_applies_to_the_personal_qr(client, db, alice, lab, device, device_headers):
    lab.require_booking_for_rfid = True
    db.commit()
    payload = client.post("/api/auth/me/door-qr", headers=auth_headers(client, alice.email)).json()["payload"]
    v = _validate(client, device_headers, lab, payload)
    assert v["valid"] is False and v["reason"] == "NO_ACTIVE_BOOKING"


def test_made_up_personal_qr_is_refused(client, lab, device, device_headers):
    assert _validate(client, device_headers, lab, "SLB:~not-a-real-one")["valid"] is False
