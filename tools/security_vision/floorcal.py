"""
Floor map for one camera (crosscam.py): click points ON THE FLOOR in the camera's picture and type
where they are in the room, in metres, measured from ONE fixed corner of the room (same corner and
directions for both cameras!).

    py floorcal.py camera.env          (camera 1)       py floorcal.py camera2.env    (camera 2)

The camera service must be running (it serves the picture). Click a point, then type "x y" in this
window (e.g. "2.40 1.10"). At least 4 points, spread over the floor and not on one line - 6 is
better. Press s to save, u to undo the last point, q to quit without saving.
Writes anchors/<DEVICE>_floor.json; restart that camera's service to use it.
"""
import json
import os
import sys

import cv2
import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))


def read_env(path):
    env = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.lower().startswith("set ") and "=" in line:
            k, v = line[4:].split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main():
    env = read_env(os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "camera.env"))
    device, port = env.get("DEVICE", "SECCAM_LAB01"), env.get("PORT", "5100")
    key = os.environ.get("DEVICE_API_KEY") or env.get("DEVICE_API_KEY") or ""
    if not key:
        from security_vision import device_key
        key = device_key()
    r = requests.get(f"http://127.0.0.1:{port}/raw.jpg", headers={"X-Device-Key": key}, timeout=5)
    if r.status_code != 200:
        raise SystemExit(f"No picture from {device} on port {port} (HTTP {r.status_code}) - is its service running?")
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    points = []

    def redraw():
        view = img.copy()
        for i, p in enumerate(points):
            x, y = int(p["px"][0] * w), int(p["px"][1] * h)
            cv2.circle(view, (x, y), 6, (0, 255, 255), -1)
            cv2.putText(view, f"{i + 1}: {p['floor'][0]:.2f},{p['floor'][1]:.2f} m", (x + 8, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(f"Floor map {device} - click floor points, s=save u=undo q=quit", view)

    def click(ev, x, y, *_):
        if ev != cv2.EVENT_LBUTTONDOWN:
            return
        txt = input(f"Point {len(points) + 1} at pixel ({x}, {y}) - room position in metres 'x y': ").split()
        try:
            points.append({"px": [x / w, y / h], "floor": [float(txt[0]), float(txt[1])]})
        except (ValueError, IndexError):
            print("  not two numbers - point skipped")
        redraw()

    redraw()
    cv2.setMouseCallback(f"Floor map {device} - click floor points, s=save u=undo q=quit", click)
    while True:
        k = cv2.waitKey(50) & 0xFF
        if k == ord("u") and points:
            points.pop(); redraw()
        elif k == ord("q"):
            print("Not saved."); break
        elif k == ord("s"):
            if len(points) < 4:
                print("Need at least 4 points."); continue
            from crosscam import FloorMap
            try:
                fm = FloorMap(points)
            except ValueError as e:
                print(f"Not saved: {e}"); continue
            err = max(np.hypot(*np.subtract(fm.project(*p["px"]), p["floor"])) for p in points)
            out = os.path.join(HERE, "anchors", f"{device}_floor.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            json.dump({"device": device, "image": [w, h], "points": points}, open(out, "w"), indent=1)
            print(f"Saved {out} ({len(points)} points, worst fit {err:.2f} m). Restart {device}'s service to use it.")
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
