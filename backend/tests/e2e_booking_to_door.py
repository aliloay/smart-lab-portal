"""
END-TO-END: booking -> QR -> camera -> master -> backend -> biometric -> door.

This is not a unit test. It drives the RUNNING API over HTTP exactly as the
real components do:

  * the student's browser  -> login, book, fetch the QR
  * the ESP32-CAM          -> decode the rendered PNG with cv2 (real OpenCV)
  * the Master ESP32       -> POST /access/validate-qr with X-Device-Key
  * the Master ESP32       -> report the biometric outcome and door events

Run:  python tests/e2e_booking_to_door.py
"""
import base64
import io
import sys
from datetime import datetime, timedelta, timezone

import cv2
import httpx
import numpy as np

API = "http://127.0.0.1:8000/api"
DEVICE_HEADERS = {"X-Device-Key": "dev-device-key-change-me"}
LAB = "LAB_01"
DEVICE = "MASTER_LAB01"

ok_count = 0
fail_count = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global ok_count, fail_count
    if condition:
        ok_count += 1
        print(f"  PASS  {label}")
    else:
        fail_count += 1
        print(f"  FAIL  {label}   {detail}")


def decode_qr_like_the_camera(png_b64: str) -> str:
    """
    The real path: base64 PNG -> image -> grayscale -> cv2.QRCodeDetector,
    the same detector face_server.py uses.
    """
    raw = base64.b64decode(png_b64)
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(gray)
    return (data or "").strip()


def main() -> int:
    c = httpx.Client(timeout=15.0)
    now = datetime.now(timezone.utc)

    print("\n=== 1. Student signs in ===")
    r = c.post(f"{API}/auth/login",
               json={"email": "ali@giu-uni.de", "password": "Student#2026"})
    check("login succeeds", r.status_code == 200, r.text)
    tok = r.json()["access_token"]
    student = {"Authorization": f"Bearer {tok}"}
    check("auth_subject bridges to the firmware",
          c.get(f"{API}/auth/me", headers=student).json()["auth_subject"] == "USER1")

    print("\n=== 2. Student books the laboratory ===")
    labs = c.get(f"{API}/labs", headers=student).json()
    lab = next(l for l in labs if l["code"] == LAB)
    start = now - timedelta(minutes=5)          # already running
    end = now + timedelta(hours=1)

    # Make the run repeatable. LAB_01 is exclusive, so a booking left behind
    # by an earlier run would (correctly) collide with this one. Clearing our
    # own overlapping bookings first means the script can be run any number of
    # times without hand-resetting the database - and it exercises the cancel
    # path on the way through.
    cleared = 0
    for b in c.get(f"{API}/bookings", headers=student).json():
        if b["lab_id"] != lab["id"] or b["status"] != "CONFIRMED":
            continue
        if (datetime.fromisoformat(b["start_time"]) < end
                and datetime.fromisoformat(b["end_time"]) > start):
            c.post(f"{API}/bookings/{b['id']}/cancel", headers=student)
            cleared += 1
    if cleared:
        print(f"  (cleared {cleared} overlapping booking(s) from an earlier run)")
    r = c.post(f"{API}/bookings", headers=student, json={
        "lab_id": lab["id"], "start_time": start.isoformat(),
        "end_time": end.isoformat(), "reason": "Thesis experiment"})
    check("booking created", r.status_code == 201, r.text)
    if r.status_code != 201:
        print("\n  Cannot continue without a booking.")
        return 1
    booking = r.json()
    check("auto-confirmed", booking["status"] == "CONFIRMED", str(booking))

    print("\n=== 3. Portal renders the QR ===")
    r = c.get(f"{API}/bookings/{booking['id']}/qr", headers=student)
    check("QR issued", r.status_code == 200, r.text)
    qr = r.json()
    check("currently valid", qr["is_currently_valid"] is True)

    print("\n=== 4. ESP32-CAM decodes it (real OpenCV) ===")
    decoded = decode_qr_like_the_camera(qr["qr_png_base64"])
    check("decoded payload matches the issued token", decoded == qr["token"],
          f"{decoded!r} != {qr['token']!r}")
    check("payload is opaque", decoded.startswith("SLB:") and
          "ali" not in decoded.lower() and "user1" not in decoded.lower())

    print("\n=== 5. Master validates it with the portal ===")
    r = c.post(f"{API}/access/validate-qr", headers=DEVICE_HEADERS,
               json={"lab_id": LAB, "qr_token": decoded, "device_uid": DEVICE})
    check("validate-qr returns 200", r.status_code == 200, r.text)
    v = r.json()
    check("valid", v["valid"] is True, str(v))
    check("returns the identity the biometric must match",
          v["auth_subject"] == "USER1", str(v))
    check("returns display name for the LCD",
          v["display_name"] == "Ali Loay", str(v))

    print("\n=== 6. THE SECURITY TEST: wrong laboratory ===")
    r = c.post(f"{API}/access/validate-qr", headers=DEVICE_HEADERS,
               json={"lab_id": "LAB_02", "qr_token": decoded,
                     "device_uid": DEVICE})
    check("same token refused at another lab", r.json()["valid"] is False)
    check("reason is WRONG_LAB", r.json()["reason"] == "WRONG_LAB",
          str(r.json()))

    print("\n=== 7. THE SECURITY TEST: identity mismatch ===")
    # Master reports: QR said USER1, but the face matched USER2.
    r = c.post(f"{API}/access/deny", headers=DEVICE_HEADERS, json={
        "lab_id": LAB, "device_uid": DEVICE, "event_type": "ACCESS_DENIED",
        "auth_subject": "USER1", "booking_id": booking["id"],
        "method": "FACE", "result": "DENIED", "reason": "IDENTITY_MISMATCH",
        "message": "Step 1 was USER1 but face matched USER2"})
    check("mismatch recorded", r.status_code == 200, r.text)

    print("\n=== 8. Happy path: matching biometric, door opens ===")
    c.post(f"{API}/access/events", headers=DEVICE_HEADERS, json={
        "lab_id": LAB, "device_uid": DEVICE, "event_type": "FACE_ACCEPTED",
        "auth_subject": "USER1", "booking_id": booking["id"],
        "method": "FACE", "result": "GRANTED", "message": "Face matched USER1"})
    r = c.post(f"{API}/access/grant", headers=DEVICE_HEADERS, json={
        "lab_id": LAB, "device_uid": DEVICE, "event_type": "ACCESS_GRANTED",
        "auth_subject": "USER1", "booking_id": booking["id"],
        "method": "QR", "result": "GRANTED", "message": "Access granted"})
    check("grant recorded", r.status_code == 200, r.text)

    for ev in ("DOOR_OPENED", "DOOR_CLOSED"):
        c.post(f"{API}/access/events", headers=DEVICE_HEADERS, json={
            "lab_id": LAB, "device_uid": DEVICE, "event_type": ev,
            "auth_subject": "USER1", "booking_id": booking["id"],
            "message": ev.replace("_", " ").title()})

    print("\n=== 9. Heartbeat and device status ===")
    r = c.post(f"{API}/access/heartbeat", headers=DEVICE_HEADERS, json={
        "device_uid": DEVICE, "lab_id": LAB, "ip_address": "192.168.1.77",
        "firmware_version": "portal-1.0", "door_closed": True})
    check("heartbeat accepted", r.status_code == 200, r.text)

    print("\n=== 10. Cancellation kills the credential ===")
    r = c.post(f"{API}/bookings/{booking['id']}/cancel", headers=student)
    check("cancelled", r.status_code == 200, r.text)
    r = c.post(f"{API}/access/validate-qr", headers=DEVICE_HEADERS,
               json={"lab_id": LAB, "qr_token": decoded, "device_uid": DEVICE})
    check("the SAME token is now refused", r.json()["valid"] is False,
          str(r.json()))
    check("reason names the revocation",
          r.json()["reason"] in ("TOKEN_REVOKED", "BOOKING_CANCELLED"),
          str(r.json()))

    print("\n=== 11. The audit trail tells the whole story ===")
    admin = c.post(f"{API}/auth/login",
                   json={"email": "admin@giu-uni.de", "password": "Admin#2026"})
    ah = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    events = c.get(f"{API}/access-events?limit=40", headers=ah).json()
    kinds = [e["event_type"] for e in events]
    for needed in ("BOOKING_CREATED", "BOOKING_CONFIRMED", "QR_GENERATED",
                   "QR_VALIDATED", "QR_REJECTED", "ACCESS_GRANTED",
                   "ACCESS_DENIED", "DOOR_OPENED", "DOOR_CLOSED",
                   "BOOKING_CANCELLED"):
        check(f"timeline contains {needed}", needed in kinds)

    print("\n--- reconstructed timeline (newest first) ---")
    for e in events[:14]:
        ts = e["created_at"][11:19]
        print(f"  {ts}  {e['event_type']:<20} {e.get('message','')[:58]}")

    print("\n" + "=" * 62)
    print(f"  {ok_count} passed, {fail_count} failed")
    print("=" * 62)
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
