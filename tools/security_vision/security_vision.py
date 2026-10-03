"""
Smart Lab security camera service - runs on the laptop next to the face server.

    py security_vision.py --source rtsp://camuser:campass@192.168.1.155:554/stream2
    py security_vision.py --source 0            (laptop webcam, for testing)

It reads a fixed camera in a lab corner (Mercusys MC210 or any RTSP/ONVIF
camera, or a webcam), and three times a second:

  * detects people (YOLOX-S, CPU) and follows each one (tracker);
  * names a person only when the door makes it certain: someone first seen in
    the door area just after a door entry, or the last unnamed person when
    only one name is left - otherwise "Unknown" (see vision.Labeler);
  * watches a box around each fixed item (PC, robot): moved / missing, or
    moving with nobody at it (vision.ZoneWatcher);
  * compares people seen with people inside per the door.

The portal (device key, like every node) gives it the boxes and who is
inside, receives its state every 2 s, and gets an event with a snapshot when
something needs a look: more people seen than entered, a person with nobody
entered, equipment moved, movement at equipment with nobody there. Staff see
the live annotated view through the portal. Nothing is recorded except
event snapshots. It never actuates anything.

HTTP (port 5100, X-Device-Key required except /health):
    /frame.jpg   latest annotated frame       /raw.jpg   latest plain frame
    /state       JSON: people, names, zones   /health
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request

from vision import PERSON, Appearance, Detector, Labeler, Tracker, ZoneWatcher, draw

HERE = os.path.dirname(os.path.abspath(__file__))


def device_key() -> str:
    """DEVICE_API_KEY as the portal uses it: environment, then the repo's .env."""
    key = os.environ.get("DEVICE_API_KEY") or os.environ.get("DEVICE_KEY")
    env = os.path.join(HERE, "..", "..", ".env")
    if not key and os.path.isfile(env):
        with open(env, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("DEVICE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or "dev-device-key-change-me"


# --------------------------------------------------------------- capture ---
class Camera:
    """Keeps only the newest frame (an RTSP buffer would otherwise lag)."""

    def __init__(self, source: str, max_width: int):
        self.source, self.max_width = source, max_width
        self.frame: Optional[np.ndarray] = None
        self.at = 0.0
        self.ok = False
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        s = self.source
        if s.isdigit():
            return cv2.VideoCapture(int(s), cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if os.path.isfile(s) and s.lower().endswith((".jpg", ".jpeg", ".png")):
            return None                                   # a still image, for tests/demos
        if s.startswith("rtsp://"):
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        return cv2.VideoCapture(s, cv2.CAP_FFMPEG)

    def _store(self, frame):
        h, w = frame.shape[:2]
        if w > self.max_width:
            frame = cv2.resize(frame, (self.max_width, int(h * self.max_width / w)))
        with self._lock:
            self.frame, self.at, self.ok = frame, time.time(), True

    def _run(self):
        still = None
        while True:
            cap = self._open()
            if cap is None:
                still = still if still is not None else cv2.imread(self.source)
                if still is None:
                    print(f"[camera] cannot read {self.source}")
                    time.sleep(5)
                    continue
                self._store(still.copy())
                time.sleep(0.1)
                continue
            if not cap.isOpened():
                self.ok = False
                print(f"[camera] cannot open {self._safe()} - retrying in 3 s")
                time.sleep(3)
                continue
            print(f"[camera] streaming from {self._safe()}")
            fails = 0
            while fails < 30:
                ok, frame = cap.read()
                if not ok or frame is None:
                    fails += 1
                    time.sleep(0.05)
                    if self.source.lower().endswith((".mp4", ".avi", ".mkv")):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop a test video
                    continue
                fails = 0
                self._store(frame)
                if self.source.lower().endswith((".mp4", ".avi", ".mkv")):
                    time.sleep(1 / 15)
            cap.release()
            self.ok = False
            print("[camera] stream lost - reconnecting")
            time.sleep(1)

    def _safe(self):
        # Never print the camera password.
        s = self.source
        if "@" in s and "://" in s:
            scheme, rest = s.split("://", 1)
            return f"{scheme}://***@{rest.split('@', 1)[1]}"
        return s

    def latest(self):
        with self._lock:
            return (None if self.frame is None else self.frame.copy()), self.at


# --------------------------------------------------------------- service ---
class Service:
    STATE_PERIOD_S = 2.0
    CONFIG_PERIOD_S = 3.0
    EXTRA_PERSON_HOLD_S = 8.0          # more people than entered for this long -> event
    EVENT_COOLDOWN_S = 120.0

    def __init__(self, args):
        self.args = args
        self.key = device_key()
        self.portal = args.portal.rstrip("/")
        self.http = requests.Session()
        self.http.headers["X-Device-Key"] = self.key
        cv2.setNumThreads(args.threads)            # leave CPU for the face server
        self.detector = Detector(args.model, conf=args.conf, size=args.size)
        # Who looks like whom: colours always, the body model when downloaded.
        reid = args.reid if args.reid and os.path.isfile(args.reid) else None
        self.appearance = Appearance(reid)
        print(f"[vision] identity lock: colours{' + body re-id model' if reid else ' only (no re-id model)'}")
        self.camera = Camera(args.source, args.max_width)
        self.tracker, self.labeler, self.zones = Tracker(), Labeler(), ZoneWatcher()
        self.cfg = {"zones": [], "door": None, "occupants": []}
        self.versions: dict[int, int] = {}
        self.tracks = []
        self.fps = 0.0
        self.jpeg = self.raw_jpeg = None
        self.lock = threading.Lock()
        self.extra_since: Optional[float] = None
        self.clear_since: Optional[float] = None
        self.extra_reported = False        # one event per incident, not one per cooldown
        self.last_event: dict[str, float] = {}
        # Demo (--demo "USER1=Ali,USER2=Sara"): no portal; "X enters" buttons
        # on /demo stand in for the door, and the whole picture is the door
        # area, so whoever walks in next gets that name.
        self.demo = {}
        if args.demo:
            for part in args.demo.split(","):
                label, _, name = part.partition("=")
                if label.strip():
                    self.demo[label.strip()] = name.strip() or label.strip()
            self.cfg = {"zones": [], "door": {"x": 0, "y": 0, "w": 1, "h": 1}, "occupants": []}

    # -- portal ------------------------------------------------------------
    def demo_enter(self, label: str):
        occ = [o for o in self.cfg["occupants"] if o["auth_subject"] != label]
        occ.append({"auth_subject": label, "name": self.demo[label], "role": "STUDENT",
                    "entered_at": time.time()})
        self.cfg = {**self.cfg, "occupants": occ}

    def demo_leave(self, label: str):
        self.cfg = {**self.cfg, "occupants": [o for o in self.cfg["occupants"] if o["auth_subject"] != label]}

    def poll_config(self):
        if self.demo:
            return                     # demo: nothing from the portal
        while True:
            try:
                r = self.http.get(self.portal + "/security/config", timeout=5, params={
                    "device_uid": self.args.device, "lab_id": self.args.lab,
                    "port": self.args.port, "name": self.args.name})
                if r.status_code == 200:
                    cfg = r.json()
                    for z in cfg["zones"]:
                        if self.versions.get(z["id"]) != z["ref_version"]:
                            self.zones.reset(z["id"])        # new box / accepted: relearn
                            self.versions[z["id"]] = z["ref_version"]
                    self.cfg = cfg
                else:
                    print(f"[portal] config HTTP {r.status_code}: {r.text[:120]}")
            except requests.RequestException as e:
                print(f"[portal] unreachable: {e.__class__.__name__}")
            time.sleep(self.CONFIG_PERIOD_S)

    def post_state(self):
        if self.demo:
            return
        while True:
            time.sleep(self.STATE_PERIOD_S)
            with self.lock:
                tracks = list(self.tracks)
                zones = [{"id": s.id, "name": s.name, "status": s.status, "score": s.score}
                         for s in self.zones.states.values()]
            named = [{"label": t.label, "name": t.name, "role": t.role} for t in tracks if t.label]
            try:
                self.http.post(self.portal + "/security/state", timeout=5, json={
                    "device_uid": self.args.device, "fps": self.fps, "people": len(tracks),
                    "named": named, "unknown": len(tracks) - len(named), "zones": zones,
                    "source_ok": self.camera.ok})
            except requests.RequestException:
                pass

    def event(self, kind: str, detail: str, zone_id=None, people_seen=0, people_inside=0):
        if self.demo:
            print(f"[demo event] {kind} {detail}")
            return
        key = f"{kind}:{zone_id}"
        now = time.time()
        if now - self.last_event.get(key, 0) < self.EVENT_COOLDOWN_S:
            return
        self.last_event[key] = now
        with self.lock:
            snap = self.jpeg
        meta = {"device_uid": self.args.device, "kind": kind, "detail": detail, "zone_id": zone_id,
                "people_seen": people_seen, "people_inside": people_inside}
        print(f"[event] {kind} {detail}")

        def send():
            try:
                self.http.post(self.portal + "/security/events", timeout=10,
                               data={"meta": json.dumps(meta)},
                               files={"snapshot": ("snapshot.jpg", snap, "image/jpeg")} if snap else None)
            except requests.RequestException as e:
                print(f"[event] not delivered: {e.__class__.__name__}")
        threading.Thread(target=send, daemon=True).start()

    # -- analysis ----------------------------------------------------------
    def analyse(self):
        period = 1.0 / self.args.det_fps
        times = []
        while True:
            t0 = time.time()
            frame, at = self.camera.latest()
            if frame is None or t0 - at > 5:
                time.sleep(0.2)
                continue
            h, w = frame.shape[:2]
            people = [d.box for d in self.detector.detect(frame) if d.cls == PERSON]
            tracks = self.tracker.update(people, t0, self.appearance.looks(frame, people, t0))
            occupants = self.cfg.get("occupants", [])
            door = self.cfg.get("door")
            door_px = (door["x"] * w, door["y"] * h, door["w"] * w, door["h"] * h) if door else None
            self.labeler.assign(tracks, occupants, door_px, t0)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            pnorm = [(b[0] / w, b[1] / h, b[2] / w, b[3] / h) for b in (t.box for t in tracks)]
            states = self.zones.update(self.cfg.get("zones", []), gray, pnorm, t0)
            with self.lock:
                self.tracks = tracks
            self.check(tracks, occupants, states)
            times.append(time.time() - t0)
            times = times[-20:]
            self.fps = round(1.0 / max(sum(times) / len(times), period), 1)
            time.sleep(max(0.0, period - (time.time() - t0)))

    def check(self, tracks, occupants, states):
        seen, inside = len(tracks), len(occupants)
        now = time.time()
        if seen > inside:
            self.extra_since = self.extra_since or now
            self.clear_since = None
            if now - self.extra_since >= self.EXTRA_PERSON_HOLD_S and not self.extra_reported:
                self.extra_reported = True
                if inside == 0:
                    self.event("PERSON_NO_ENTRY", f"{seen} person(s) seen, nobody entered at the door.",
                               people_seen=seen, people_inside=inside)
                else:
                    self.event("UNIDENTIFIED_PERSON",
                               f"{seen} people seen, {inside} entered at the door (possible tailgating).",
                               people_seen=seen, people_inside=inside)
        else:
            self.extra_since = None
            self.clear_since = self.clear_since or now
            if now - self.clear_since >= 10:          # back to normal: the next one is new
                self.extra_reported = False
        motion_ok = {z["id"]: z.get("alert_on_motion", True) for z in self.cfg.get("zones", [])}
        for st in states:
            if st.reported or st.status not in ("CHANGED", "MOTION"):
                continue
            st.reported = True
            if st.status == "CHANGED":
                self.event("EQUIPMENT_CHANGED", f"{st.name} no longer looks as usual (moved, removed "
                           f"or covered; difference {st.score:.2f}) and nobody is at it.",
                           zone_id=st.id, people_seen=seen, people_inside=inside)
            elif motion_ok.get(st.id, True):
                self.event("EQUIPMENT_MOTION", f"Movement at {st.name} with nobody at it.",
                           zone_id=st.id, people_seen=seen, people_inside=inside)

    def render(self):
        """Annotated stream: newest frame + latest boxes, ~10 fps."""
        while True:
            t0 = time.time()
            frame, at = self.camera.latest()
            if frame is not None and t0 - at < 5:
                raw = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
                with self.lock:
                    tracks = list(self.tracks)
                door = self.cfg.get("door")
                draw(frame, tracks, self.cfg.get("zones", []), dict(self.zones.states),
                     (door["x"], door["y"], door["w"], door["h"]) if door else None)
                jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
                with self.lock:
                    self.raw_jpeg, self.jpeg = raw, jpeg
            else:
                with self.lock:
                    self.raw_jpeg = self.jpeg = None
            time.sleep(max(0.0, 0.1 - (time.time() - t0)))


def make_app(svc: Service) -> Flask:
    app = Flask(__name__)

    def authorised() -> bool:
        return hmac.compare_digest(request.headers.get("X-Device-Key", ""), svc.key)

    def image(data):
        if not authorised():
            return Response("device key required", status=401)
        if data is None:
            return Response(status=204)
        return Response(data, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "camera": svc.camera.ok, "fps": svc.fps,
                        "people": len(svc.tracks), "zones": len(svc.cfg.get("zones", []))})

    @app.get("/frame.jpg")
    def frame():
        return image(svc.jpeg)

    @app.get("/raw.jpg")
    def raw():
        return image(svc.raw_jpeg)

    @app.get("/state")
    def state():
        if not authorised():
            return Response("device key required", status=401)
        return jsonify({"fps": svc.fps, "camera": svc.camera.ok,
                        "tracks": [{"id": t.id, "label": t.label, "name": t.name, "role": t.role,
                                    "box": t.box} for t in svc.tracks],
                        "zones": [{"id": s.id, "name": s.name, "status": s.status, "score": s.score}
                                  for s in svc.zones.states.values()]})

    if svc.demo:                       # local only (bound to 127.0.0.1), no key needed
        @app.get("/demo")
        def demo_page():
            buttons = "".join(
                f'<div class="p"><b>{n}</b> ({l})<br><button onclick="go(\'enter\',\'{l}\')">{n} enters</button>'
                f'<button onclick="go(\'leave\',\'{l}\')">{n} leaves</button></div>' for l, n in svc.demo.items())
            return Response(DEMO_PAGE.replace("{BUTTONS}", buttons), mimetype="text/html")

        @app.get("/demo/frame.jpg")
        def demo_frame():
            return Response(svc.jpeg or b"", mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

        @app.post("/demo/<action>/<label>")
        def demo_action(action, label):
            if label not in svc.demo or action not in ("enter", "leave"):
                return jsonify({"error": "unknown"}), 404
            (svc.demo_enter if action == "enter" else svc.demo_leave)(label)
            return jsonify({"inside": [o["auth_subject"] for o in svc.cfg["occupants"]]})

        @app.get("/demo/state")
        def demo_state():
            with svc.lock:
                tracks = list(svc.tracks)
            return jsonify({"fps": svc.fps, "people": [
                {"id": t.id, "label": t.label, "name": t.name, "crowded": t.crowded} for t in tracks],
                "locked": {k: v.samples for k, v in svc.labeler.identities.items()},
                "inside": [o["auth_subject"] for o in svc.cfg["occupants"]]})
    return app


DEMO_PAGE = """<!doctype html><meta charset=utf-8><title>Name lock demo</title>
<style>body{font:15px system-ui;background:#0b1220;color:#e2e8f0;margin:0;display:flex;gap:16px;padding:16px}
img{max-width:72vw;border-radius:10px;border:1px solid #334155}.side{min-width:260px}
.p{background:#111a2e;border:1px solid #334155;border-radius:10px;padding:10px;margin-bottom:10px}
button{margin:6px 6px 0 0;padding:6px 10px;border-radius:8px;border:0;background:#2563eb;color:#fff;cursor:pointer}
pre{background:#111a2e;padding:10px;border-radius:10px;white-space:pre-wrap}</style>
<img id=f><div class=side><h3>Name lock demo</h3>
<p>1. Everyone out of view. 2. Click "X enters", then X walks in alone and stands clear for 2 s
(the look locks). 3. Next person. 4. Walk past each other, bump, swap places: the names should stay.</p>
{BUTTONS}<pre id=s></pre></div>
<script>
const f=document.getElementById('f');setInterval(()=>{f.src='/demo/frame.jpg?'+Date.now()},150);
async function go(a,l){await fetch('/demo/'+a+'/'+l,{method:'POST'})}
setInterval(async()=>{const r=await (await fetch('/demo/state')).json();
document.getElementById('s').textContent=JSON.stringify(r,null,1)},700);
</script>"""


def main():
    ap = argparse.ArgumentParser(description="Smart Lab security camera service")
    ap.add_argument("--source", default=os.environ.get("SECURITY_CAMERA_SOURCE", "0"),
                    help="rtsp://user:pass@ip:554/stream2, a webcam number, a video or image file")
    ap.add_argument("--device", default="SECCAM_LAB01", help="device id in the portal")
    ap.add_argument("--name", default="Security camera")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://127.0.0.1:8000/api")
    ap.add_argument("--port", type=int, default=5100)
    ap.add_argument("--model", default=os.path.join(HERE, "models", "object_detection_yolox_2022nov.onnx"))
    ap.add_argument("--reid", default=os.path.join(HERE, "models", "person_reid_youtu_2021nov.onnx"),
                    help="body re-identification model (optional; colours only without it)")
    ap.add_argument("--size", type=int, default=416, help="detector input (416: ~160 ms; 640: sharper, slower)")
    ap.add_argument("--conf", type=float, default=0.45)
    ap.add_argument("--threads", type=int, default=4, help="CPU threads (the face server needs the rest)")
    ap.add_argument("--det-fps", type=float, default=3.0)
    ap.add_argument("--max-width", type=int, default=960)
    ap.add_argument("--demo", default="", help='name-lock test without the portal, e.g. "USER1=Ali,USER2=Sara"; '
                                               'open http://127.0.0.1:<port>/demo')
    args = ap.parse_args()
    if not os.path.isfile(args.model):
        raise SystemExit(f"Model not found: {args.model}\nSee tools/security_vision/README.md (download once).")
    svc = Service(args)
    for target in (svc.poll_config, svc.post_state, svc.analyse, svc.render):
        threading.Thread(target=target, daemon=True).start()
    host = "127.0.0.1" if svc.demo else "0.0.0.0"
    print(f"Smart Lab security camera {args.device} ({args.lab}) on port {args.port}. Ctrl+C stops.")
    if svc.demo:
        print(f"DEMO: open http://127.0.0.1:{args.port}/demo")
    try:
        from waitress import serve
        serve(make_app(svc), host=host, port=args.port, threads=6)
    except ImportError:
        make_app(svc).run(host=host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
