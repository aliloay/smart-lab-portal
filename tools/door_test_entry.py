"""
TEST door entry - for testing the camera's "named at the door" flow while the door
controller (Master ESP32) and lock are not installed.

It records exactly what the Master records after a successful RFID + face/fingerprint check
(POST /api/access/grant), clearly marked as a test: device DOOR_TEST, message "TEST entry".
It opens NO door and sends nothing to any device. The portal opens an access session, and the
security camera gives that person's name to the next NEW person who first appears in the
camera's door box within 25 s (vision.Labeler.ENTRY_MATCH_S) - no face needed.

    py tools\\door_test_entry.py USER1            (Ali Loay; USER6 Nour, USER5 Eng. Hemaly ...)
    py tools\\door_test_entry.py USER1 --wait 8   (record it 8 s from now: time to walk to the door)

Test: stand outside the camera's view, run it (or use --wait), walk in through the door.
Leave the lab first if you are already being tracked inside - the name goes to a NEW track.

    py tools/door_test_entry.py --watch-face
Automatic while the lock is not installed: reads the face server's last recognised door face
(GET /door/last-face, read only) and records a TEST entry each time the door's ESP32-CAM
recognises a registered person; each new recognition refreshes the entry (at most every 10 s). Ctrl+C stops it.
"""
import argparse
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
FRESH_S = 15.0          # --watch-face: only a recognition this recent means someone is at the door now
# 2026-10-21 lab: with only Ali at the door, the face server answered USER5, USER1 and USER3 within 25 s and
# each single answer became an entry - camera 1 then named Ali "USER3 by door". The real door needs two
# factors; this test stand-in now needs the face to AGREE: the same name at least AGREE_N times within
# AGREE_S, and no other name within CLEAN_S.
AGREE_N, AGREE_S, CLEAN_S = 2, 5.0, 10.0


def stable_name(recent: list, now: float):
    """recent: [(name, at)] of door recognitions. The name the door camera agrees on now, or None."""
    if not recent:
        return None
    who = recent[-1][0]
    same = [at for n, at in recent if n == who and now - at <= AGREE_S]
    other = [n for n, at in recent if n != who and now - at <= CLEAN_S]
    return who if len(same) >= AGREE_N and not other else None


def device_key() -> str:
    for line in open(os.path.join(HERE, "..", ".env"), encoding="utf-8"):
        if line.strip().startswith("DEVICE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("DEVICE_API_KEY not found in .env")


def grant(a, subject: str) -> bool:
    r = requests.post(a.portal.rstrip("/") + "/access/grant", timeout=10,
                      headers={"X-Device-Key": device_key()},
                      json={"lab_id": a.lab, "device_uid": "DOOR_TEST", "event_type": "ACCESS_GRANTED",
                            "auth_subject": subject, "method": a.method, "result": "GRANTED",
                            "message": "TEST entry - door controller not installed, no door opened"})
    if r.status_code != 200:
        print(f"portal answered {r.status_code}: {r.text[:200]}")
    return r.status_code == 200


def exit_(a, subject: str) -> bool:
    """TEST exit: closes the person's open session the normal way (EXIT_RECORDED; kept, not deleted).
    For a wrong test entry, e.g. the door camera mistook someone for this person."""
    r = requests.post(a.portal.rstrip("/") + "/access/events", timeout=10,
                      headers={"X-Device-Key": device_key()},
                      json={"lab_id": a.lab, "device_uid": "DOOR_TEST", "event_type": "EXIT_RECORDED",
                            "auth_subject": subject, "result": "GRANTED",
                            "message": "TEST exit - correcting a test entry (door controller not installed)"})
    if r.status_code != 200:
        print(f"portal answered {r.status_code}: {r.text[:200]}")
    return r.status_code == 200


def watch_face(a, every_s: float = 10.0):
    """Poll the face server's last recognised door face (read only); a new one = that person is at the door."""
    url, key = a.face.rstrip("/") + "/door/last-face", device_key()
    last: dict[str, float] = {}
    seen_at = 0.0
    recent: list = []                            # (name, at) of the door camera's recent recognitions
    print(f"watching the door camera's recognitions ({url}) - a recognised face = TEST entry. Ctrl+C stops.")
    while True:
        try:
            f = requests.get(url, headers={"X-Device-Key": key}, timeout=3).json()
        except (requests.RequestException, ValueError) as e:
            print(f"face server not reachable ({e.__class__.__name__}) - retrying")
            time.sleep(3)
            continue
        who, at = f.get("name"), float(f.get("at") or 0)
        if who and at > seen_at:
            seen_at = at
            if time.time() - at > FRESH_S:      # an old recognition (e.g. from before this tool started):
                continue                         # nobody is at the door now - no entry (2026-10-21)
            now = time.time()
            recent = [r for r in recent if now - r[1] <= CLEAN_S] + [(who, at)]
            agreed = stable_name(recent, now)
            if agreed is None:
                names = sorted({n for n, _ in recent})
                print(f"{time.strftime('%H:%M:%S')} door camera says {who}"
                      + (f" - but also {', '.join(n for n in names if n != who)} just now: no entry" if len(names) > 1
                         else " - waiting for it to agree"))
            elif now - last.get(agreed, 0) >= every_s and grant(a, agreed):
                last[agreed] = now
                print(f"{time.strftime('%H:%M:%S')} {agreed} recognised at the door (agreed) -> TEST entry recorded; "
                      f"the camera names them as they walk in (25 s)")
        time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser(description="Record a TEST door entry (no door is opened)")
    ap.add_argument("auth_subject", nargs="?", help="the person's id, e.g. USER1")
    ap.add_argument("--exit", action="store_true", help="record a TEST exit instead (closes the open session)")
    ap.add_argument("--watch-face", action="store_true", help="automatic: every face recognised at the door")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--method", default="FACE", choices=["FACE", "FINGERPRINT", "RFID"])
    ap.add_argument("--wait", type=float, default=0.0, help="seconds to wait before recording")
    ap.add_argument("--portal", default="http://127.0.0.1:8000/api")
    ap.add_argument("--face", default="http://127.0.0.1:5000", help="face server (door camera)")
    a = ap.parse_args()
    if a.watch_face:
        try:
            watch_face(a)
        except KeyboardInterrupt:
            print("stopped")
        return
    if not a.auth_subject:
        sys.exit("give a person id (e.g. USER1) or --watch-face")
    if a.exit:
        if exit_(a, a.auth_subject):
            print(f"TEST exit recorded for {a.auth_subject} - no longer counted inside {a.lab}.")
        return
    for left in range(int(a.wait), 0, -1):
        print(f"recording the test entry in {left} s - go to the door", flush=True)
        time.sleep(1)
    if grant(a, a.auth_subject):
        print(f"TEST entry recorded for {a.auth_subject} in {a.lab} at {time.strftime('%H:%M:%S')}. "
              f"Walk in through the door within 25 s - the camera names the new person in the door box.")


if __name__ == "__main__":
    main()
