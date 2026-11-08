"""
Bench stand-in for the door controller, same two steps as the door:
  1. a booking QR shown to the ESP32-CAM is checked by the portal
     (POST /api/access/validate-qr: right lab, right time, whose booking);
  2. within STEP2_S the ESP32-CAM must see THAT person's face.
Then it counts as that person entering the lab, as if the door had opened.

Use it only while the Master ESP32 (lock, sensors) is NOT running - the real
door reports its own grants. Nothing in the portal or camera logic changes:
this posts the same POST /api/access/grant the door sends, so the portal opens
an occupancy session and the security camera names whoever appears in the door
area, exactly as after a real entry.

Every entry is labelled "BENCH ENTRY (ESP32-CAM QR + face, no lock)" in the access
log, so it is never confused with a real door entry.

    py tools/bench_face_entry.py            (Ctrl+C stops)
"""
import json
import os
import sys
import time
import urllib.request

CAM = "http://192.168.1.150/status"          # ESP32-CAM (firmware/ESP32CAM_Vision_FAST)
PORTAL = "http://127.0.0.1:8000/api/access/grant"
LAB = "LAB_01"
DEVICE = "CAM_LAB01"                          # the entry camera, registered in the portal
MAX_DISTANCE = 40.0                           # 100*(1-cosine): 40 = cosine 0.60 (door uses 0.363)
FRESH_MS = 1500                               # a face result older than this is ignored
CONFIRM = 2                                   # same person this many polls in a row
REPEAT_S = 60.0                               # one entry per person per minute
POLL_S = 0.3

KEY = os.environ.get("DEVICE_API_KEY", "")
if not KEY:
    sys.exit("Set DEVICE_API_KEY (the portal's device key) first.")


STEP2_S = 20.0                                # face must follow the QR within this


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Device-Key": KEY})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read() or b"{}")


def grant(label: str, distance: float, booking_id) -> int:
    body = json.dumps({"lab_id": LAB, "device_uid": DEVICE, "event_type": "ACCESS_GRANTED",
                       "auth_subject": label, "booking_id": booking_id, "method": "QR", "result": "GRANTED",
                       "message": f"BENCH ENTRY (ESP32-CAM QR + face, no lock): {label}, distance {distance:.1f}"}).encode()
    req = urllib.request.Request(PORTAL, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Device-Key": KEY})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


last_entry: dict[str, float] = {}
run_label, run = None, 0
step1 = None                                   # (auth_subject, name, booking_id, at) after a valid QR
last_qr = None
print("Bench face entry: watching the ESP32-CAM. Ctrl+C stops.", flush=True)
while True:
    try:
        st = json.loads(urllib.request.urlopen(CAM, timeout=2).read())
        now = time.time()
        qr, qr_age = st.get("qr"), st.get("qr_age_ms", -1)
        if qr and 0 <= qr_age <= FRESH_MS and qr != last_qr:
            last_qr = qr
            v = post(PORTAL.replace("/grant", "/validate-qr"), {"qr_token": qr, "lab_id": LAB, "device_uid": DEVICE})
            if v.get("valid"):
                step1 = (v["auth_subject"], v.get("display_name"), v.get("booking_id"), now)
                print(f"{time.strftime('%H:%M:%S')} QR ok: {v.get('display_name')} ({v['auth_subject']}) - now the face", flush=True)
            else:
                print(f"{time.strftime('%H:%M:%S')} QR refused: {v.get('reason')}", flush=True)
        if step1 and now - step1[3] > STEP2_S:
            print(f"{time.strftime('%H:%M:%S')} no matching face within {STEP2_S:.0f} s - start again with the QR", flush=True)
            step1 = None
        label, age, dist = st.get("face"), st.get("face_age_ms", -1), st.get("distance")
        ok = label and 0 <= age <= FRESH_MS and dist is not None and dist <= MAX_DISTANCE
        if ok and label == run_label:
            run += 1
        else:
            run_label, run = (label, 1) if ok else (None, 0)
        if run >= CONFIRM and step1 and label != step1[0]:
            print(f"{time.strftime('%H:%M:%S')} face is {label}, QR is {step1[0]}: IDENTITY MISMATCH - refused", flush=True)
            step1, run_label, run = None, None, 0
        if run >= CONFIRM and step1 and label == step1[0] and now - last_entry.get(label, 0) >= REPEAT_S:
            code = grant(label, dist, step1[2])
            step1 = None
            last_entry[label] = now
            print(f"{time.strftime('%H:%M:%S')} entry {label} (distance {dist:.1f}) -> HTTP {code}", flush=True)
            run_label, run = None, 0
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} {e.__class__.__name__}: {e}", flush=True)
        time.sleep(2)
    time.sleep(POLL_S)
