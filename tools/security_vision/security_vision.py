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
  * compares people seen with people inside per the door;
  * every 60 s looks for monitors / laptops in the background and checks
    them against the named boxes (equipwatch.py): nudges a box a little off
    its item, reports an item with no box, or a named item not seen for long.

The portal (device key, like every node) gives it the boxes and who is
inside, receives its state every 2 s, and gets an event with a snapshot when
something needs a look: more people seen than entered, a person with nobody
entered, equipment moved, movement at equipment with nobody there. Staff see
the live annotated view through the portal. Video is recorded only when an
administrator presses Record in the portal (recorder.py: FFmpeg, until Stop,
split into 1-hour MP4 files in recordings/ on this laptop, never deleted
automatically); otherwise only event
snapshots are kept. It never actuates anything.

HTTP (port 5100, X-Device-Key required except /health; this laptop only
by default - the portal in Docker reaches it through host.docker.internal):
    /frame.jpg   latest annotated frame       /raw.jpg   latest plain frame
    /state       JSON: people, names, zones   /health
    /record/status, /record/start|stop (POST), /recordings, /recordings/<file>
"""
from __future__ import annotations

import argparse
from collections import deque
import hmac
import collections
import copy
import json
import os
import random
import re
import threading
import traceback
import time
from typing import Optional

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request, send_file

from dataset import Collector
from equipwatch import NOT_SEEN_SCANS, EquipmentWatch, Found
from latency import PipelineMetrics, gpu_load, process_load
from robotvision import RobotVisualMotion
from recorder import Recorder
import realign
from vision import EQUIPMENT_CLASSES, find_equipment
from vision import PERSON, Appearance, Detector, DoorWatcher, Labeler, Tracker, ZoneWatcher, draw, drop_slivers, head_crop, iou, zoom_people
from vision import make_detector, predicted, red_share

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
def masked(src) -> str:
    """The camera address without its user/password, for logs."""
    return re.sub(r"(rtsp|https?)://[^@/\s]+@", r"\1://***@", str(src))


class Camera:
    """Keeps only the newest frame (an RTSP buffer would otherwise lag): there is never a backlog -
    a frame that arrives while analysis is busy replaces the older one (latency.py counts the skips).

    Reconnects on its own (2026-10-18): after a failed open or a lost stream it waits with exponential
    backoff - 1 s doubling to 30 s, +-20 % jitter - instead of a fixed 3 s forever (camera 1 offline
    all evening = 694 open attempts, each holding FFmpeg). FFmpeg's own open/read timeouts are set,
    so a camera that stops sending ends the connection after READ_TIMEOUT_MS instead of hanging
    inside read(). One connection at a time per camera (the loop is sequential).

    state: CONNECTING -> STREAMING; RECONNECTING after a loss or a failed open; OFFLINE after
    OFFLINE_AFTER failed opens in a row. A frame older than STALE_S is STALE (no frame is ever shown
    or analysed as live after that)."""
    BACKOFF_MIN_S, BACKOFF_MAX_S = 1.0, 30.0
    OPEN_TIMEOUT_MS, READ_TIMEOUT_MS = 8000, 5000
    LOST_S = 5.0                     # no frame for this long on an open stream = lost
    OFFLINE_AFTER = 3
    STALE_S = 2.0
    VIDEO_EXT = (".mp4", ".avi", ".mkv")

    def __init__(self, source: str, max_width: int, metrics: Optional[PipelineMetrics] = None,
                 start: bool = True):
        self.source, self.max_width = source, max_width
        self.frame: Optional[np.ndarray] = None
        self.at = 0.0
        self.seq = 0                                  # frames received so far (skips = latest-frame policy)
        self.ok = False
        self.metrics = metrics
        self.state, self.state_since = "CONNECTING", time.time()
        self.fails_in_row = 0
        self.retry_at = 0.0
        self.last_error = ""
        self._lock = threading.Lock()
        if start:
            threading.Thread(target=self._run, daemon=True, name="camera").start()

    def _open(self):
        s = self.source
        if s.isdigit():
            return cv2.VideoCapture(int(s), cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if os.path.isfile(s) and s.lower().endswith((".jpg", ".jpeg", ".png")):
            return None                                   # a still image, for tests/demos
        if s.startswith("rtsp://"):
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
            params = []
            for prop, ms in (("CAP_PROP_OPEN_TIMEOUT_MSEC", self.OPEN_TIMEOUT_MS),
                             ("CAP_PROP_READ_TIMEOUT_MSEC", self.READ_TIMEOUT_MS)):
                if hasattr(cv2, prop):                    # OpenCV >= 4.6 (installed: 4.10)
                    params += [getattr(cv2, prop), ms]
            if params:
                return cv2.VideoCapture(s, cv2.CAP_FFMPEG, params)
        return cv2.VideoCapture(s, cv2.CAP_FFMPEG)

    def _set(self, state: str, error: str = ""):
        if state != self.state:
            self.state, self.state_since = state, time.time()
        if error:
            self.last_error = error

    def backoff_s(self) -> float:
        """Wait before the next attempt: 1, 2, 4 ... 30 s (+-20 %), by failures in a row."""
        base = min(self.BACKOFF_MAX_S, self.BACKOFF_MIN_S * 2 ** min(max(self.fails_in_row - 1, 0), 10))
        return base * random.uniform(0.8, 1.2)

    def _wait(self):
        d = self.backoff_s()
        self.retry_at = time.time() + d
        time.sleep(d)

    def _store(self, frame, read_ms: float = 0.0):
        now = time.time()
        h, w = frame.shape[:2]
        if w > self.max_width:
            frame = cv2.resize(frame, (self.max_width, int(h * self.max_width / w)))
        with self._lock:
            self.frame, self.at, self.ok = frame, now, True
            self.seq += 1
        if self.state != "STREAMING":
            self.fails_in_row = 0
            self._set("STREAMING")
        if self.metrics:
            self.metrics.frame_in(now, read_ms)

    def _failed_open(self, why: str):
        self.ok = False
        self.fails_in_row += 1
        self._set("OFFLINE" if self.fails_in_row >= self.OFFLINE_AFTER else "RECONNECTING", why)
        if self.metrics:
            self.metrics.open_failures += 1

    def _run(self):
        still = None
        while True:
            cap = self._open()
            if cap is None:
                still = still if still is not None else cv2.imread(self.source)
                if still is None:
                    print(f"[camera] cannot read {masked(self.source)}")
                    self._failed_open("cannot read the image file")
                    self._wait()
                    continue
                self._store(still.copy())
                time.sleep(0.1)
                continue
            if not cap.isOpened():
                self._failed_open("could not open the stream")
                d = self.backoff_s()
                print(f"[camera] cannot open {self._safe()} - retry {self.fails_in_row} in {d:.0f} s")
                self.retry_at = time.time() + d
                time.sleep(d)
                continue
            print(f"[camera] streaming from {self._safe()}")
            self._stream(cap)
            cap.release()
            self.ok = False
            if self.metrics:
                self.metrics.reconnects += 1
            self.fails_in_row = max(self.fails_in_row, 1)
            self._set("RECONNECTING", f"no frame for {self.LOST_S:.0f} s")
            print(f"[camera] stream lost - reconnecting in about {self.backoff_s():.0f} s")
            self._wait()

    def _stream(self, cap):
        """Read until no frame came for LOST_S (a stalled stream is not waited on for ever)."""
        video = self.source.lower().endswith(self.VIDEO_EXT)
        last_ok = time.monotonic()
        while time.monotonic() - last_ok < self.LOST_S:
            r0 = time.perf_counter()
            ok, frame = cap.read()
            read_ms = (time.perf_counter() - r0) * 1000
            if not ok or frame is None:
                time.sleep(0.05)
                if video:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop a test video
                continue
            last_ok = time.monotonic()
            self._store(frame, read_ms)
            if video:
                time.sleep(1 / 15)

    def status(self) -> dict:
        """For /health and the portal: what the stream is doing, never the address."""
        now = time.time()
        age = now - self.at if self.at else None
        state = self.state
        if state == "STREAMING" and (age is None or age > self.STALE_S):
            state = "STALE"
        return {"state": state, "since_s": round(now - self.state_since, 1),
                "frame_age_s": None if age is None else round(age, 2),
                "fails_in_row": self.fails_in_row,
                "retry_in_s": round(max(0.0, self.retry_at - now), 1) if state in ("RECONNECTING", "OFFLINE") else None,
                "last_error": self.last_error}

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

    def latest_seq(self):
        """(frame, received at, sequence number) - the newest only; older frames are gone."""
        with self._lock:
            return (None if self.frame is None else self.frame.copy()), self.at, self.seq


# Desk owners (owner's rule 2026-10-14): tools/security_vision/home_desks.json, e.g.
# {"USER5": ["PC-09", "PC-10"]}. Used only for people the door or the face already placed in the lab.
def _home_desks() -> dict:
    p = os.path.join(HERE, "home_desks.json")
    try:
        return {k: list(v) for k, v in json.load(open(p, encoding="utf-8")).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


HOME_DESKS = _home_desks()


# --------------------------------------------------------------- service ---
class Service:
    STATE_PERIOD_S = 2.0
    ROBOT_STATE_PERIOD_S = 0.5         # with robot boxes: report faster (telemetry vs camera fusion)
    CONFIG_PERIOD_S = 3.0
    EXTRA_PERSON_HOLD_S = 8.0          # more people than entered for this long -> event
    EVENT_COOLDOWN_S = 120.0
    RENDER_FPS = 15                    # pictures drawn per second for the live views
    FACE_EVERY_S = 1.5                 # a face check per unnamed person at most this often
    FACE_MARGIN = 0.08                 # the best face must beat the next person by this (cosine; was 0.05)
    FACE_MAX_AGE_S = 1.0               # a detection older than this is not used for a face crop
    FACE_MIN = 0.50                    # and reach this: from the ceiling, wrong people matched 0.41-0.53,
                                       # the right one 0.59-0.66 (2026-10-12); the door camera stays at 0.363
    RAW_WANTED_S = 5.0                 # keep encoding the plain picture this long after a request
    FACE_RECHECK_S = 15.0              # a verified person's face is re-checked this often (swaps)

    def __init__(self, args):
        self.args = args
        self.key = device_key()
        self.portal = args.portal.rstrip("/")
        self.http = requests.Session()
        self.http.headers["X-Device-Key"] = self.key
        cv2.setNumThreads(args.threads)            # leave CPU for the face server
        self.detector = make_detector(args.model, conf=args.conf, size=args.size, threads=args.threads)
        # Who looks like whom: colours always, the body model when downloaded.
        reid = args.reid if args.reid and os.path.isfile(args.reid) else None
        self.appearance = Appearance(reid)
        print(f"[vision] identity lock: colours{' + body re-id model' if reid else ' only (no re-id model)'}")
        self.metrics = PipelineMetrics()
        process_load()                                 # primes psutil's CPU counter (its first reading is 0)
        self.camera = Camera(args.source, args.max_width, self.metrics)
        # Recording (admin, from the portal): the full-resolution stream when
        # the analysis reads the small one (MC210: stream1 vs stream2).
        rec_src = args.record_source or (args.source.replace("/stream2", "/stream1")
                                         if args.source.lower().startswith("rtsp://") else args.source)
        self.recorder = Recorder(args.device, rec_src, args.recordings, segment_minutes=args.record_part_min,
                                 min_free_gb=args.record_min_free_gb)
        # Training pictures for the robot detector (admin, Start / Stop in the portal).
        self.dataset = Collector(args.device, os.path.join(HERE, "dataset"))
        print(f"[record] {'FFmpeg found' if self.recorder.ffmpeg else 'FFmpeg NOT found - recording unavailable'};"
              f" files in {os.path.abspath(args.recordings)}")
        self.tracker, self.labeler, self.zones = Tracker(), Labeler(), ZoneWatcher()
        # Two cameras, one name per person (crosscam.py): only with a floor map for this camera
        # (anchors/<DEVICE>_floor.json) and the other camera's port (PEER_PORT / --peer).
        from crosscam import CrossCam, FloorMap
        try:
            floor = FloorMap.load(os.path.join(HERE, "anchors"), args.device)
        except ValueError as e:
            floor = None
            print(f"[crosscam] floor map ignored: {e}")
        peer = f"http://127.0.0.1:{args.peer}" if args.peer else None
        self.crosscam = CrossCam(peer, self.key, floor, obs_path=os.path.join(
            os.path.abspath(args.recordings), f"crosscam_obs_{args.device}.jsonl"))
        self.frame_wh = (0, 0)
        print(f"[crosscam] other camera {peer or 'none'}; floor map {'loaded' if floor else 'not calibrated - nothing shared'}")
        self.door_watch = DoorWatcher()      # open / closed from the red door leaf in the door box
        self.robot_vis = RobotVisualMotion() # optical flow in robot boxes (alert_on_motion off)
        self.robot_visual: dict[int, dict] = {}
        self.person_rects: list[tuple] = []        # latest people (0-1), from the detector pass
        self.det_frame = None                      # (frame, time, {track: box}, {crowded tracks})
        self.zone_states: list = []                # latest box states, from watch_zones
        self.door_open: Optional[bool] = None
        self.cfg = {"zones": [], "door": None, "occupants": []}
        self.versions: dict[int, int] = {}
        self.tracks = []
        # View re-alignment (realign.py): reference of the room for the current boxes.
        self.view_anchor = None           # realign.Reference of the view the boxes were drawn on
        self.view_anchor_boxes = {}
        self.view_applied = {}            # boxes as we last placed them (vs. staff edits)
        self.view_before = {}             # the boxes just before our last move (portal not re-read yet)
        self.view_pending = None          # a confident move seen once; acted on when seen twice
        self.view_unstable = False        # moved, not (yet) re-aligned: box alerts held back
        self.view_lost_checks = 0
        self.view_wake = threading.Event()  # set when many boxes change at once: check the view now
        self.fps = 0.0
        self.analysed_at = 0.0               # last finished analysis pass (staleness)
        self.part_ms: dict = {}               # re-ID / tracker / naming split of track_ms (/metrics)
        self.analysis_errors = 0
        self.jpeg = self.raw_jpeg = None
        self.jpeg_at = 0.0                  # when the frame in self.jpeg was received from the camera
        self.lock = threading.Lock()
        self.label_lock = threading.Lock()   # labeler: analysis + face checks
        self.equipment_detector = None        # 640 model for "Find equipment", loaded on first use
        self.equip_watch = EquipmentWatch()
        self.equip_cache = None               # (time, items) of the last background scan
        self.equip_key = None                 # the boxes the watch's counts belong to
        self.det_lock = threading.Lock()     # the detector network: analysis + equipment search
        self.face_asked: dict[int, float] = {}
        self.identity_log = deque(maxlen=300)      # identity decisions, newest last (/identity)
        self.mismatch_reported: set = set()
        self.face_http = requests.Session()
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
                    door = cfg.get("door")
                    if door and self.versions.get(("door", door["id"])) != door.get("ref_version"):
                        # The door box moved (camera re-aimed / re-aligned) or was redrawn:
                        # the learnt "how red is the open door" belongs to the old view.
                        if ("door", door["id"]) in self.versions:
                            self.door_watch = DoorWatcher()
                            print("[door] door box changed - learning the open door's look again")
                        self.versions[("door", door["id"])] = door.get("ref_version")
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
            time.sleep(self.STATE_PERIOD_S if not self.robot_visual else self.ROBOT_STATE_PERIOD_S)
            with self.lock:
                tracks = list(self.tracks)
                zones = [{"id": s.id, "name": s.name, "status": s.status, "score": s.score,
                          "visual": self.robot_visual.get(s.id)}
                         for s in self.zones.states.values()]
            named = [{"label": t.label, "name": t.name, "role": t.role, "source": t.source,
                      "entered": t.entered, "verified": t.verified, "face": t.mismatch,
                      "track_id": t.id, "identity_state": t.identity_state,
                      "confidence": t.identity_confidence, "named_by": t.named_by}
                     for t in tracks if t.label]
            try:
                self.http.post(self.portal + "/security/state", timeout=5, json={
                    "device_uid": self.args.device, "fps": self.live_fps(), "people": len(tracks),
                    "named": named, "unknown": len(tracks) - len(named), "zones": zones,
                    "source_ok": self.camera.ok and self.camera.status()["state"] == "STREAMING",
                    "door_open": self.door_open,
                    "metrics": self._metrics_brief()})
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
            frame, at, seq = self.camera.latest_seq()
            if frame is None or t0 - at > 5:
                time.sleep(0.2)
                continue
            try:
                age_ms = (t0 - at) * 1000
                h, w = frame.shape[:2]
                with self.det_lock:
                    d0 = time.perf_counter()
                    people = [d.box for d in self.detector.detect(frame) if d.cls == PERSON]
                    z0 = time.perf_counter()
                    self.part_ms.setdefault("detect_main", collections.deque(maxlen=100)).append((z0 - d0) * 1000)
                    # A named person just lost (Labeler.lost): look again, zoomed, where they were.
                    # Only where someone else's box now covers the lost spot (occlusion: Ali behind
                    # Nour). An empty spot means they walked away - a zoom there finds nothing and
                    # cost ~35 ms a pass (detect p50 140 ms with 4 people).
                    lost = [rec[0] for rec in getattr(self.labeler, "lost", {}).values()
                            if any(iou(rec[0], p) > 0.1 for p in people)]
                    # ...and inside unusually WIDE person boxes: two people seated together come
                    # out as one box (lab frames: one seated person w/h 0.56-0.60, Ali+Nour 0.78).
                    # Only boxes shaped like two people side by side (0.7-1.6): a 2.2-wide box at
                    # home (live 2026-10-15) zoomed EVERY pass - zoom 52 ms = half the pass time.
                    wide = [b for b in people if b[3] > 0 and 0.7 < b[2] / b[3] <= 1.6]
                    # ...and one more person box each pass, in turn: a ratio alone misses pairs
                    # (lab: 0.67 with Ali behind Nour). ~20 ms on the GPU; each box ~once a second.
                    self._zoom_i = getattr(self, "_zoom_i", -1) + 1
                    # every 3rd pass only (speed: 8 people at 5 fps had no headroom, pass p95 207 ms)
                    turn = [people[(self._zoom_i // 3) % len(people)]] if people and self._zoom_i % 3 == 0 else []
                    # ONE zoom a pass (measured: zooms 50 ms vs main detection 41 ms per pass), by
                    # priority: an occluded lost spot, then wide boxes in turn, then the round-robin.
                    wide_turn = [wide[(self._zoom_i // 2) % len(wide)]] if wide and self._zoom_i % 2 == 0 else []
                    regions = lost[:1] or wide_turn or turn
                    if regions:
                        people += zoom_people(self.detector, frame, regions, people, max_n=1)
                    self.part_ms.setdefault("zoom", collections.deque(maxlen=100)).append((time.perf_counter() - z0) * 1000)
                    detect_ms = (time.perf_counter() - d0) * 1000
                k0 = time.perf_counter()
                people = drop_slivers(people)
                r0 = time.perf_counter()
                looks = self.appearance.looks(frame, people, t0)
                r1 = time.perf_counter()
                tracks = self.tracker.update(people, t0, looks)
                r2 = time.perf_counter()
                occupants = self.cfg.get("occupants", [])
                door = self.cfg.get("door")
                door_px = (door["x"] * w, door["y"] * h, door["w"] * w, door["h"] * h) if door else None
                with self.label_lock:
                    seen_ids = {t.id for t in tracks}          # alive in the tracker but missed a moment ago
                    coasting = [t for t in self.tracker.tracks if t.id not in seen_ids]
                    self.labeler.assign(tracks, occupants, door_px, t0, known=self.cfg.get("known"),
                                        coasting=coasting)
                    if HOME_DESKS:
                        zpx = {z["name"]: (z["x"] * w, z["y"] * h, z["w"] * w, z["h"] * h)
                               for z in self.cfg.get("zones", [])}
                        self.labeler.home_desk(tracks, HOME_DESKS, zpx, occupants,
                                               {k["auth_subject"]: k for k in (self.cfg.get("known") or [])}, t0)
                    notes_cc = self.crosscam.share(tracks, w, h, t0, self.labeler)
                    self.frame_wh = (w, h)
                    id_events = list(self.labeler.events)
                    notes, self.labeler.notes = getattr(self.labeler, "notes", []) + notes_cc, []
                for nt in notes:                       # hand-back / door decisions, readable via /identity
                    self.identity_log.append({"t": round(time.time(), 2), **nt})
                    self._persist_identity(self.identity_log[-1])
                self._identity_events(id_events, tracks, occupants)
                track_ms = (time.perf_counter() - k0) * 1000
                for part, ms in (("reid", (r1 - r0) * 1000), ("tracker", (r2 - r1) * 1000),
                                 ("naming", (time.perf_counter() - r2) * 1000)):
                    self.part_ms.setdefault(part, collections.deque(maxlen=100)).append(ms)
                z0 = time.perf_counter()
                pnorm = [(b[0] / w, b[1] / h, b[2] / w, b[3] / h) for b in (t.box for t in tracks)]
                with self.lock:
                    self.person_rects = pnorm          # for the fast box loop (watch_zones)
                    states = list(self.zone_states)
                if door:
                    was = self.door_open
                    drect = (door["x"], door["y"], door["w"], door["h"])
                    self.door_open = self.door_watch.update(red_share(frame, drect),
                                                            any(iou(drect, p) > 0.02 for p in pnorm))
                    if was is not None and self.door_open is not None and was != self.door_open:
                        print(f"[door] {'opened' if self.door_open else 'closed'} (camera)")
                else:
                    self.door_open = None
                with self.lock:
                    self.tracks = tracks
                    # The frame these boxes come from: faces are cut from THIS frame,
                    # so a face can never be cropped from a later frame where the
                    # box already holds someone else (2026-10-12 root cause #1).
                    self.det_frame = (frame, t0, {t.id: tuple(t.box) for t in tracks},
                                      {t.id for t in tracks if t.crowded})
                self.check(tracks, occupants, states)
                zones_ms = (time.perf_counter() - z0) * 1000
                self.metrics.analysed(seq, age_ms, detect_ms, track_ms, zones_ms, (time.time() - t0) * 1000)
            except Exception as e:                 # one bad pass must not stop analysis for good
                self.analysis_errors += 1
                if self.analysis_errors <= 3 or self.analysis_errors % 100 == 0:
                    print(f"[analysis] pass failed ({self.analysis_errors} so far): {e.__class__.__name__}: {e}")
                    traceback.print_exc()
                time.sleep(0.5)
                continue
            self.analysed_at = time.time()
            times.append(time.time() - t0)
            times = times[-20:]
            self.fps = round(1.0 / max(sum(times) / len(times), period), 1)
            time.sleep(max(0.0, period - (time.time() - t0)))

    def live_fps(self) -> float:
        """Analysis rate, or 0 when no pass has finished for 3 s (never a frozen old value)."""
        return self.fps if time.time() - self.analysed_at < 3.0 else 0.0

    def _metrics_brief(self) -> dict:
        m = self.metrics.summary()
        g = lambda d, k: (d or {}).get(k)
        return {"input_fps": m["capture"]["fps"], "analysis_fps": m["analysis"]["fps"],
                "render_fps": m["render"]["fps"],
                "frame_age_ms_p50": g(m["analysis"]["frame_age_ms"], "p50"),
                "frame_age_ms_p95": g(m["analysis"]["frame_age_ms"], "p95"),
                "pass_ms_p50": g(m["analysis"]["pass_ms"], "p50"),
                "detect_ms_p50": g(m["analysis"]["detect_ms"], "p50"),
                "serve_age_ms_p50": g(m["serve"]["frame_age_ms"], "p50"),
                "skipped": m["analysis"]["skipped_latest_frame_policy"], "reconnects": m["capture"]["reconnects"], "open_failures": m["capture"].get("open_failures", 0),
                # numbers only (the portal keeps numeric metrics): 1 = on the graphics card (DirectML)
                "detector_gpu": int(self.detector_engine().startswith("directml")),
                "reid_gpu": int(self.appearance.engine.startswith("directml")),
                # 2026-10-18: real process / card load (was always 0) and the stream's own age
                "frame_age_s": self.camera.status()["frame_age_s"],
                "cpu_percent": (process_load() or {}).get("cpu_percent"),
                "private_mb": (process_load() or {}).get("private_mb"),
                "gpu_util_percent": (gpu_load() or {}).get("util_percent"),
                "gpu_mem_mb": (gpu_load() or {}).get("mem_used_mb")}

    def detector_engine(self) -> str:
        return str(getattr(self.detector, "engine", "unknown"))

    def _persist_identity(self, rec: dict) -> None:
        """Identity decisions survive a restart (the in-memory log was lost on every restart).
        One file per camera (git-ignored folder: it holds names)."""
        path = os.path.join(HERE, "recordings", f"identity_log_{self.args.device}.jsonl")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        except OSError:
            pass

    def _identity_events(self, events, tracks, occupants):
        """Identity decisions: all kept in a short local log (/identity, the
        evidence panel); a conflict is also an event for staff."""
        for e in events:
            self.identity_log.append({"t": round(time.time(), 2), "kind": e.kind, "track_id": e.track_id,
                                      "label": e.label, "detail": e.detail})
            self._persist_identity(self.identity_log[-1])
            print(f"[identity] {e.kind} track {e.track_id}: {e.detail}")
            if e.kind == "PERSON_IDENTITY_CONFLICT":
                self.event("PERSON_IDENTITY_CONFLICT", f"Track {e.track_id}: {e.detail}. The name was NOT "
                           "changed - check who this is.", people_seen=len(tracks), people_inside=len(occupants))
            elif e.kind == "PERSON_IDENTITY_REVIEW":       # ambiguous entry, names re-dealt, a name on two people
                self.event("PERSON_IDENTITY_REVIEW", f"Track {e.track_id}: {e.detail}.",
                           people_seen=len(tracks), people_inside=len(occupants))

    def check(self, tracks, occupants, states):
        seen, inside = len(tracks), len(occupants)
        now = time.time()
        if seen > inside:
            self.extra_since = self.extra_since or now
            self.clear_since = None
            if now - self.extra_since >= self.EXTRA_PERSON_HOLD_S and not self.extra_reported:
                self.extra_reported = True
                hold = [f"{t.name} ({t.label})" for t in tracks if t.label and not t.entered]
                face = f" Recognised by face: {', '.join(hold)} - not entered at the door." if hold else ""
                if inside == 0:
                    self.event("PERSON_NO_ENTRY", f"{seen} person(s) seen, nobody entered at the door.{face}",
                               people_seen=seen, people_inside=inside)
                else:
                    self.event("UNIDENTIFIED_PERSON",
                               f"{seen} people seen, {inside} entered at the door (possible tailgating).{face}",
                               people_seen=seen, people_inside=inside)
        else:
            self.extra_since = None
            self.clear_since = self.clear_since or now
            if now - self.clear_since >= 10:          # back to normal: the next one is new
                self.extra_reported = False
        # The badge said one person, the face clearly says another: card sharing?
        known = {k["auth_subject"]: k["name"] for k in self.cfg.get("known", [])}
        for t in tracks:
            if t.mismatch and (t.id, t.mismatch) not in self.mismatch_reported:
                self.mismatch_reported.add((t.id, t.mismatch))
                self.event("FACE_MISMATCH", f"The door entry was {t.name} ({t.label}), but the face matches "
                           f"{known.get(t.mismatch, t.mismatch)} ({t.mismatch}). Someone may be using another "
                           f"person's card.", zone_id=None, people_seen=seen, people_inside=inside)
        motion_ok = {z["id"]: z.get("alert_on_motion", True) for z in self.cfg.get("zones", [])}
        # Most boxes changing in the same moment = the camera moved, not the items:
        # no equipment alerts, and the view is checked at once (not in 15 s).
        busy = [st for st in states if st.status in ("CHANGED", "MOTION")]
        if len(states) >= 3 and len(busy) >= max(3, (len(states) + 1) // 2) and not self.view_unstable:
            self.view_unstable = True
            for st in busy:
                st.reported = True
            print(f"[view] {len(busy)} of {len(states)} boxes changed at once - the camera moved? checking now")
            self.view_wake.set()
        for st in states:
            if st.reported or st.status not in ("CHANGED", "MOTION"):
                continue
            if self.view_unstable:          # the whole view moved: not an item moving
                continue
            st.reported = True
            if st.status == "CHANGED":
                self.event("EQUIPMENT_CHANGED", f"{st.name} no longer looks as usual (moved, removed "
                           f"or covered; difference {st.score:.2f}) and nobody is at it.",
                           zone_id=st.id, people_seen=seen, people_inside=inside)
            elif motion_ok.get(st.id, True):
                self.event("EQUIPMENT_MOTION", f"Movement at {st.name} with nobody at it.",
                           zone_id=st.id, people_seen=seen, people_inside=inside)
            else:                       # a robot running on its own: logged, not an alert
                self.event("ROBOT_ACTIVITY", f"{st.name} is moving.", zone_id=st.id,
                           people_seen=seen, people_inside=inside)
        for st in states:
            if st.new_pose:
                st.new_pose = False
                if not self.view_unstable:
                    self.event("ROBOT_ACTIVITY", f"{st.name} moved to a new position and stopped there.",
                               zone_id=st.id, people_seen=seen, people_inside=inside)

    VIEW_CHECK_S = 15.0
    VIEW_CHECK_UNSETTLED_S = 3.0     # while the view is moving / just moved
    # PTZ cameras (2026-10-21): at power-on they sweep and stop at a default tilt, and staff
    # tilt them back by hand. A view check in that time re-aligned camera 2's boxes to the
    # wrong view. So for this long after the stream (re)connects nothing is anchored or moved.
    VIEW_STARTUP_QUIET_S = 180.0

    def view_settling(self, now: float) -> bool:
        """True while the camera is not streaming or has only just (re)connected."""
        cam = self.camera
        return cam.state != "STREAMING" or now - cam.state_since < self.VIEW_STARTUP_QUIET_S

    def watch_view(self):
        """Every 15 s: has the camera's view moved? Confident (twice in a row)
        -> every box re-aligned through the portal; not confident -> say so
        once, change nothing (see realign.py)."""
        if self.demo:
            return
        while True:
            self.view_wake.wait(self.VIEW_CHECK_UNSETTLED_S if self.view_unstable else self.VIEW_CHECK_S)
            self.view_wake.clear()
            try:
                self._check_view()
            except Exception as e:                       # never let this stop the camera
                print(f"[view] check failed: {e!r}")

    ZONE_HZ = 5.0                    # boxes (PCs, robots) checked this often - not tied to the
                                     # slow people detector, so a robot move shows within ~0.4 s

    def watch_zones(self):
        """PC / robot boxes on the newest frame, ZONE_HZ times a second (~12 ms a pass).
        People in a box (IN_USE) come from the detector's latest pass."""
        period = 1.0 / self.ZONE_HZ
        self.load_home()
        while True:
            t0 = time.time()
            frame, at = self.camera.latest()
            zones = self.cfg.get("zones", [])
            if frame is None or t0 - at > 5 or not zones:
                time.sleep(0.2)
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            with self.lock:
                pnorm = list(self.person_rects)
            states = self.zones.update(zones, gray, pnorm, t0)
            robot_boxes = [z for z in zones if z.get("alert_on_motion", True) is False]
            visual = self.robot_vis.update(robot_boxes, gray, pnorm, t0) if robot_boxes else {}
            with self.lock:
                self.zone_states = states
                self.robot_visual = visual
            time.sleep(max(0.0, period - (time.time() - t0)))

    IDENTITY_SAVE_S = 10.0           # locked looks / face names saved this often

    def _identity_path(self) -> str:
        return os.path.join(HERE, "anchors", f"{self.args.device}_identities.npz")

    def keep_identities(self):
        """Locked looks and face names survive a restart (kept up to FACE_KEEP_S)."""
        p = self._identity_path()
        if os.path.isfile(p):
            try:
                with self.label_lock:
                    n = self.labeler.load(p, time.time())
                print(f"[identity] {n} locked look(s) and {len(self.labeler.face_named)} face name(s) back from disk")
            except Exception as e:                       # damaged file: start fresh, never crash
                print(f"[identity] could not load {p}: {e!r}")
        while True:
            time.sleep(self.IDENTITY_SAVE_S)
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with self.label_lock:
                    self.labeler.save(p)
            except Exception as e:
                print(f"[identity] could not save: {e!r}")

    def _home_path(self) -> str:
        return os.path.join(HERE, "anchors", f"{self.args.device}_home.npz")

    def load_home(self):
        p = self._home_path()
        if not os.path.isfile(p):
            return
        try:
            d = np.load(p, allow_pickle=False)
            for key in d.files:
                if key.startswith("patch_"):
                    zid = int(key[6:])
                    self.zones.home[zid] = (d[key], tuple(float(v) for v in d[f"rect_{zid}"]))
            print(f"[home] HOME looks loaded for {len(self.zones.home)} robot box(es)")
        except Exception as e:                          # damaged file: no HOME, never a crash
            print(f"[home] could not load {p}: {e!r}")

    def save_home(self, only: Optional[str] = None) -> list[str]:
        frame, at = self.camera.latest()
        if frame is None or time.time() - at > 5:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        saved = self.zones.save_home(self.cfg.get("zones", []), gray, only)
        arrays = {}
        for zid, (patch, rect) in self.zones.home.items():
            arrays[f"patch_{zid}"] = patch
            arrays[f"rect_{zid}"] = np.array(rect, np.float64)
        os.makedirs(os.path.dirname(self._home_path()), exist_ok=True)
        np.savez(self._home_path(), **arrays)
        print(f"[home] HOME saved for {', '.join(saved) or 'no robot box'}")
        return saved

    def _anchor_path(self) -> str:
        return os.path.join(HERE, "anchors", f"{self.args.device}.npz")

    def _check_view(self):
        """Anchor = the view + boxes as staff last drew them (kept on disk).
        Each check maps the anchor straight to the current view; boxes move
        only when the camera has settled (two looks agree on every corner
        within 1 %) and the match is strong. No chaining, so no drift."""
        frame, at = self.camera.latest()
        zones, door = self.cfg.get("zones", []), self.cfg.get("door")
        if frame is None or time.time() - at > 5 or not (zones or door) or self.view_settling(time.time()):
            return
        with self.lock:
            people = [t.box for t in self.tracks]
        current = realign.boxes_of(zones, door)
        if self.view_anchor is None and os.path.isfile(self._anchor_path()):
            got = realign.load_anchor(self._anchor_path())
            if got:
                self.view_anchor, self.view_anchor_boxes, self.view_applied = got
                print(f"[view] anchor loaded from disk ({len(self.view_anchor_boxes)} boxes)")
        # Our last move sent, but the boxes not re-read from the portal yet:
        # wait (otherwise the same move is sent again, or taken for an edit).
        if self.view_before and realign.same_boxes(current, self.view_before):
            return
        self.view_before = {}
        # Boxes that are neither the anchor's nor the ones we placed = staff drew / edited them.
        ours = self.view_applied or self.view_anchor_boxes
        if self.view_anchor is None or not realign.same_boxes(current, ours):
            if self.view_unstable:
                return                       # never take a new anchor while the view is moving
            self.view_anchor = realign.make_reference(frame, people, "")
            self.view_anchor_boxes, self.view_applied = dict(current), {}
            self.view_pending, self.view_lost_checks = None, 0
            realign.save_anchor(self._anchor_path(), self.view_anchor, self.view_anchor_boxes, {})
            print(f"[view] anchor kept: {len(current)} box(es), {len(self.view_anchor.keypoints)} room features")
            return
        m = realign.compare(self.view_anchor, frame, people)
        strong = m.confident and m.inliers >= realign.APPLY_MIN_INLIERS and m.ratio >= realign.APPLY_MIN_RATIO
        if not strong:
            self.view_pending = None
            if m.moved or not m.confident:
                self.view_unstable = True
                self.view_lost_checks += 1
                print(f"[view] no strong match to the anchor ({m.summary()})")
                if self.view_lost_checks == 3:
                    self.event("CAMERA_VIEW_LOST", "The camera's view changed and the room could not be matched "
                               f"reliably ({m.inliers} matching points): the boxes were left as they were - "
                               "check them on the Boxes tab and redraw if needed.")
            return
        self.view_lost_checks = 0
        predicted, lost = realign.predict(m.homography, self.view_anchor_boxes)
        if len(lost) * 2 > len(self.view_anchor_boxes):
            self.view_unstable = True
            print(f"[view] {len(lost)} of {len(self.view_anchor_boxes)} boxes would leave the picture - not moving them")
            return
        if realign.max_corner_gap(predicted, current) <= realign.SETTLED and not lost:
            if self.view_unstable:
                print(f"[view] boxes are in place ({m.summary()})")
            self.view_pending, self.view_unstable = None, False
            return
        self.view_unstable = True
        if self.view_pending is None or realign.max_corner_gap(predicted, self.view_pending) > realign.SETTLED:
            self.view_pending = predicted        # still moving? wait for a second look that agrees
            print(f"[view] view moved ({m.summary()}) - waiting until it has settled")
            return
        boxes = [{"id": k, "x": v[0], "y": v[1], "w": v[2], "h": v[3]} for k, v in predicted.items()]
        try:
            r = self.http.post(self.portal + "/security/zones/realign", timeout=10, json={
                "device_uid": self.args.device, "boxes": boxes, "lost": lost,
                "inliers": m.inliers, "shift": round(m.shift_fraction, 4)})
        except requests.RequestException as e:
            print(f"[view] portal unreachable: {e.__class__.__name__}")
            return
        if r.status_code != 200:
            print(f"[view] portal refused the re-alignment: HTTP {r.status_code}")
            return
        self.view_before = dict(current)
        self.view_applied = {k: v for k, v in predicted.items()}
        for k in lost:                            # left the picture: unchanged in the portal
            if k in current:
                self.view_applied[k] = current[k]
        realign.save_anchor(self._anchor_path(), self.view_anchor, self.view_anchor_boxes, self.view_applied)
        self.view_pending = None
        print(f"[view] {len(boxes)} box(es) re-aligned from the anchor, {len(lost)} left the picture ({m.summary()})")
        self.event("CAMERA_VIEW_MOVED", f"The camera's view moved; {len(boxes)} box(es) re-aligned to the room"
                   + (f", {len(lost)} left the picture - redraw those" if lost else "") + ".")

    EQUIP_SCAN_S = 60.0              # background equipment scan (~5 s of CPU, between people passes)
    EQUIP_CACHE_S = 75.0             # "Find equipment" answers from a scan this recent: instant

    def scan_equipment(self) -> Optional[list[dict]]:
        """Monitors / laptops in the plain picture now, as boxes (0-1)."""
        frame, at = self.camera.latest()
        if frame is None or time.time() - at > 5:
            return None
        if self.equipment_detector is None:
            if getattr(self.detector, "size", None) == 640:
                # Same model and input size as the live detector: share its GPU session with a lower
                # threshold. A second DirectML model next to the running one crashed the NVIDIA driver
                # (nvwgf2umx.dll access violation, 4x at the lab 2026-10-14).
                self.equipment_detector = copy.copy(self.detector)
                self.equipment_detector.conf = 0.15
            else:
                self.equipment_detector = make_detector(self.args.model, conf=0.15, size=640, threads=self.args.threads)
        h, w = frame.shape[:2]
        found = find_equipment(self.equipment_detector, frame, lock=self.det_lock)
        items = [{"kind": EQUIPMENT_CLASSES[d.cls], "score": round(d.score, 2), "x": round(d.box[0] / w, 4),
                  "y": round(d.box[1] / h, 4), "w": round(d.box[2] / w, 4), "h": round(d.box[3] / h, 4)}
                 for d in found]
        self.equip_cache = (time.time(), items, (w, h))
        return items

    def watch_equipment(self):
        """Every 60 s: what the detector finds vs. the named boxes (equipwatch.py)."""
        if self.demo:
            return
        time.sleep(10)
        while True:
            try:
                self._watch_equipment_once()
            except Exception as e:                       # never let this stop the camera
                print(f"[equipment] check failed: {e!r}")
            time.sleep(self.EQUIP_SCAN_S)

    def _watch_equipment_once(self):
        zones = list(self.cfg.get("zones", []))
        if self.view_unstable:                           # the whole view is moving: not now
            self.equip_watch.forget()
            return
        items = self.scan_equipment()
        if items is None or self.view_unstable or zones != self.cfg.get("zones", []):
            return                                       # changed during the scan: next time
        key = realign.zones_key(zones, None)
        if key != self.equip_key:
            self.equip_watch.forget()
            self.equip_key = key
        _, _, (w, h) = self.equip_cache
        with self.lock:
            people = [(b[0] / w, b[1] / h, b[2] / w, b[3] / h) for b in (t.box for t in self.tracks)]
        boxes = {z["id"]: (z["x"], z["y"], z["w"], z["h"]) for z in zones}
        names = {z["id"]: z["name"] for z in zones}
        res = self.equip_watch.update(
            boxes, [Found(i["kind"], i["score"], (i["x"], i["y"], i["w"], i["h"])) for i in items], people)
        if res.nudge:
            body = [{"id": k, "x": round(v[0], 4), "y": round(v[1], 4), "w": round(v[2], 4), "h": round(v[3], 4)}
                    for k, v in res.nudge.items()]
            try:
                r = self.http.post(self.portal + "/security/zones/realign", timeout=10, json={
                    "device_uid": self.args.device, "boxes": body, "reason": "detector"})
                ok = r.status_code == 200
            except requests.RequestException:
                ok = False
            print(f"[equipment] {'nudged' if ok else 'could not nudge'} onto the item the detector found: "
                  + ", ".join(names.get(k, str(k)) for k in res.nudge))
        if res.unnamed:
            where = "; ".join(f"{f.kind.lower()} about {f.box[0] + f.box[2] / 2:.0%} across, "
                              f"{f.box[1] + f.box[3] / 2:.0%} down ({f.score:.0%} sure)" for f in res.unnamed)
            self.event("EQUIPMENT_UNNAMED", f"Found with no box: {where}. Add it on the Boxes tab "
                       "(Find equipment) if it belongs to the lab.")
        mins = round(NOT_SEEN_SCANS * self.EQUIP_SCAN_S / 60)
        for k in res.not_seen:
            self.event("EQUIPMENT_NOT_SEEN", f"{names.get(k, k)} has not been seen by the camera for about "
                       f"{mins} min and nobody is at it - moved, switched off and covered, or taken away?",
                       zone_id=k)
        for k in res.seen_again:
            print(f"[equipment] {names.get(k, k)} is seen again")

    def identify_faces(self):
        """Names by face: a head crop of each person not named yet goes to the
        face server (the door's templates; nothing logged there). Only a clear
        match counts, and the labeler waits for two that agree."""
        if not self.args.face_server:
            return
        url = self.args.face_server.rstrip("/") + "/identify"
        while True:
            time.sleep(0.3)
            with self.lock:
                tracks = list(self.tracks)
                det = self.det_frame
            if det is None:
                continue
            frame, det_at, det_boxes, crowded = det
            if time.time() - det_at > self.FACE_MAX_AGE_S:
                continue                             # detection too old: no face from it
            now = time.time()
            for tid in [k for k in self.face_asked if all(t.id != k for t in tracks)]:
                del self.face_asked[tid]
            for t in tracks:
                every = self.FACE_RECHECK_S if t.verified else self.FACE_EVERY_S
                if now - self.face_asked.get(t.id, 0.0) < every:
                    continue
                self.face_asked[t.id] = now
                box = det_boxes.get(t.id)
                if box is None or t.id in crowded:
                    continue                         # not in that frame, or touching someone: the crop may hold them
                crop = head_crop(frame, box)
                if crop is None:
                    continue
                jpg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
                try:
                    r = self.face_http.post(url, data=jpg, timeout=3,
                                            headers={"X-Device-Key": self.key, "Content-Type": "image/jpeg"})
                    res = r.json() if r.status_code == 200 else {}
                except (requests.RequestException, ValueError):
                    res = {}
                name, score, second = res.get("name"), res.get("score"), res.get("second")
                with self.lock:
                    alive = any(x.id == t.id for x in self.tracks)
                if not alive:
                    continue                         # the track ended while asking: result dropped
                if name and score is not None and score >= self.FACE_MIN and \
                        (second is None or score - second >= self.FACE_MARGIN):
                    with self.label_lock:
                        self.labeler.face_vote(t.id, name, time.time(), score)

    def render(self):
        """Annotated stream: newest frame + latest boxes, RENDER_FPS a second."""
        while True:
            t0 = time.time()
            frame, at = self.camera.latest()
            if frame is not None and t0 - at < 5:
                self.metrics.age_at_render_ms.add((t0 - at) * 1000)
                e0 = time.perf_counter()
                # The plain picture is only for drawing boxes / boxes-off views: encoded only while
                # someone asked for it in the last RAW_WANTED_S (measured 2026-10-15: two encodes a
                # frame = encode p50 40 ms, p95 76 ms per render).
                raw = (cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
                       if t0 - getattr(self, "raw_wanted_at", 0.0) < self.RAW_WANTED_S else None)
                saved = self.dataset.offer(frame)          # plain frame, before boxes are drawn
                if saved:
                    print(f"[dataset] saved {saved}")
                with self.lock:
                    tracks = predicted(list(self.tracks), time.time())   # boxes keep up between detections
                door = self.cfg.get("door")
                draw(frame, tracks, self.cfg.get("zones", []), dict(self.zones.states),
                     (door["x"], door["y"], door["w"], door["h"]) if door else None, self.door_open)
                jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
                self.metrics.encode_ms.add((time.perf_counter() - e0) * 1000)
                self.metrics.render.tick()
                with self.lock:
                    self.raw_jpeg, self.jpeg, self.jpeg_at = raw, jpeg, at
            else:
                with self.lock:
                    self.raw_jpeg = self.jpeg = None
            time.sleep(max(0.0, 1.0 / self.RENDER_FPS - (time.time() - t0)))


def make_app(svc: Service) -> Flask:
    app = Flask(__name__)

    def authorised() -> bool:
        return hmac.compare_digest(request.headers.get("X-Device-Key", ""), svc.key)

    def image(data):
        if not authorised():
            return Response("device key required", status=401)
        if data is None:
            return Response(status=204)
        # The frame's receive time and age travel with it, so the portal and the
        # browser can measure the rest of the way (latency.py, docs/LATENCY.md).
        at = svc.jpeg_at
        age = (time.time() - at) * 1000 if at else 0.0
        svc.metrics.age_at_serve_ms.add(age)
        return Response(data, mimetype="image/jpeg", headers={
            "Cache-Control": "no-store", "X-Frame-Received-At-Ms": str(int(at * 1000)),
            "X-Frame-Age-Ms": str(int(age))})

    @app.get("/equipment")
    def equipment():
        """Monitors and laptops the detector sees in the plain picture now, as
        boxes (0-1) to suggest; the portal numbers them and staff choose."""
        if not authorised():
            return Response("device key required", status=401)
        # The full 640 model over overlapping tiles (vision.find_equipment) takes
        # ~5 s; the background watch runs it every 60 s, so a recent scan of a
        # still view answers at once. ?fresh=1 forces a new look.
        c = svc.equip_cache
        if (c and not svc.view_unstable and request.args.get("fresh") != "1"
                and time.time() - c[0] <= svc.EQUIP_CACHE_S):
            return jsonify({"items": c[1], "age_s": round(time.time() - c[0], 1)})
        items = svc.scan_equipment()
        return jsonify({"items": items or [], "age_s": 0.0})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "camera": svc.camera.ok, "fps": svc.live_fps(),
                        "stream": svc.camera.status(), "device": svc.args.device, "time": round(time.time(), 3),
                        "analysis_age_s": round(time.time() - svc.analysed_at, 1) if svc.analysed_at else None,
                        "analysis_errors": svc.analysis_errors,
                        "people": len(svc.tracks), "zones": len(svc.cfg.get("zones", []))})

    @app.get("/frame.jpg")
    def frame():
        return image(svc.jpeg)

    @app.get("/raw.jpg")
    def raw():
        svc.raw_wanted_at = time.time()
        data = svc.raw_jpeg
        if data is None and authorised():          # first request after a quiet spell: encode now
            frame, at = svc.camera.latest()
            if frame is not None and time.time() - at < 5:
                data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        return image(data)

    @app.get("/peer")
    def peer():
        """For the other camera (crosscam.py): tracks with their floor position, if calibrated."""
        if not authorised():
            return Response("device key required", status=401)
        from crosscam import peer_view
        w, h = svc.frame_wh
        with svc.lock:
            tracks = list(svc.tracks)
        return jsonify(peer_view(tracks, svc.crosscam.floor if w else None, w or 1, h or 1, time.time()))

    @app.get("/state")
    def state():
        if not authorised():
            return Response("device key required", status=401)
        return jsonify({"fps": svc.live_fps(), "camera": svc.camera.ok, "door_open": svc.door_open,
                        "tracks": [{"id": t.id, "label": t.label, "name": t.name, "role": t.role,
                                    "box": t.box, "identity_state": t.identity_state,
                                    "confidence": t.identity_confidence, "named_by": t.named_by}
                                   for t in svc.tracks],
                        "zones": [{"id": s.id, "name": s.name, "status": s.status, "score": s.score,
                                   "home": s.home, "home_score": s.home_score}
                                  for s in svc.zones.states.values()]})

    @app.post("/home/save")
    def home_save():
        """Robots at HOME now: their boxes' look becomes the HOME look (kept on disk)."""
        if not authorised():
            return Response("device key required", status=401)
        saved = svc.save_home(request.args.get("only"))     # ?only=Fanuc: that robot only
        return jsonify({"saved": saved})

    @app.get("/metrics")
    def metrics():
        """Measured stage timings (latency.py) + this process's load."""
        if not authorised():
            return Response("device key required", status=401)
        return jsonify({**svc.metrics.summary(), "process": process_load(), "gpu": gpu_load(),
                        "stream": svc.camera.status(),
                        "engines": {"detector": svc.detector_engine(), "reid": svc.appearance.engine},
                        "track_parts_ms_p50": {k: round(sorted(v)[len(v) // 2], 1) for k, v in svc.part_ms.items() if v},
                        "settings": {"det_fps": svc.args.det_fps, "size": svc.args.size,
                                     "max_width": svc.args.max_width, "render_fps": svc.RENDER_FPS}})

    @app.get("/identity")
    def identity():
        """Evidence panel: why each person in view has (or has not) a name, and
        the recent identity decisions. Names, states, scores and times only -
        no face data."""
        if not authorised():
            return Response("device key required", status=401)
        with svc.label_lock:
            people = [{"track_id": t.id, "label": t.label, "name": t.name,
                       "explain": svc.labeler.ledger.explain(t.id)} for t in svc.tracks]
        return jsonify({"people": people, "decisions": list(svc.identity_log)[-100:]})

    # ---- recording (the portal calls these for an administrator) ----------
    @app.get("/record/status")
    def record_status():
        if not authorised():
            return Response("device key required", status=401)
        return jsonify(svc.recorder.status())

    @app.post("/record/<action>")
    def record(action):
        if not authorised():
            return Response("device key required", status=401)
        by = str((request.get_json(silent=True) or {}).get("by", ""))[:80]
        if action == "start":
            r = svc.recorder.start(by)
        elif action == "stop":
            r = svc.recorder.stop(by)
        else:
            return Response("unknown action", status=404)
        print(f"[record] {action} by {by or '?'}: {r}")
        return jsonify(r), (200 if r.get("ok") else 409)

    # ---- training pictures (robot detector) ------------------------------
    @app.get("/dataset/status")
    def dataset_status():
        if not authorised():
            return Response("device key required", status=401)
        return jsonify(svc.dataset.status())

    @app.post("/dataset/<action>")
    def dataset_switch(action):
        if not authorised():
            return Response("device key required", status=401)
        by = str((request.get_json(silent=True) or {}).get("by", ""))[:80]
        if action == "start":
            r = svc.dataset.start(by)
        elif action == "stop":
            r = svc.dataset.stop()
        else:
            return Response("unknown action", status=404)
        print(f"[dataset] {action} by {by or '?'}: {r}")
        return jsonify(r), (200 if r.get("ok") else 409)

    @app.get("/recordings")
    def recordings():
        if not authorised():
            return Response("device key required", status=401)
        return jsonify({"items": svc.recorder.list(), "free_gb": round(svc.recorder.free_gb(), 1)})

    @app.post("/recordings/<name>/delete")
    def recording_delete(name):
        if not authorised():
            return Response("device key required", status=401)
        by = (request.get_json(silent=True) or {}).get("by", "")
        r = svc.recorder.remove(name, by)
        print(f"[record] delete {name} by {by or '?'}: {r}")
        return jsonify(r), (200 if r.get("ok") else 409)

    @app.get("/recordings/<name>")
    def recording_file(name):
        if not authorised():
            return Response("device key required", status=401)
        path = svc.recorder.path_of(name)
        if path is None:
            return Response("no such recording", status=404)
        # conditional=True: Range requests, so the browser can seek.
        return send_file(path, mimetype="video/mp4", conditional=True, download_name=name)

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
            return jsonify({"fps": svc.live_fps(), "people": [
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


def no_quick_edit() -> bool:
    """Windows console: a click starts text selection (QuickEdit) and every print() then blocks -
    the analysis thread prints, so one click froze detection with no error (lab 2026-10-14).
    Switch QuickEdit off for this window only. Returns True when it was switched off."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)                      # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return False                               # not a console (redirected): nothing to do
        new = (mode.value | 0x0080) & ~0x0040          # ENABLE_EXTENDED_FLAGS on, ENABLE_QUICK_EDIT_MODE off
        return bool(k32.SetConsoleMode(h, new))
    except Exception:
        return False


def camera_priority() -> Optional[str]:
    """Cameras have priority (project rule). Ollama starts its model runners at ABOVE NORMAL priority
    with every core: one portal AI answer took camera 2 from 7 to 1.7 analyses/s (measured
    2026-10-18). Run this service in the same class so the scheduler shares the CPU fairly.
    SMARTLAB_CAMERA_PRIORITY=normal keeps the old behaviour. Returns what was set."""
    want = os.environ.get("SMARTLAB_CAMERA_PRIORITY", "above_normal").lower()
    if os.name != "nt" or want == "normal":
        return None
    try:
        import psutil
        cls = {"above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS, "high": psutil.HIGH_PRIORITY_CLASS}.get(want)
        if cls is None:
            return None
        psutil.Process().nice(cls)
        return want
    except Exception as e:                           # never fatal: the camera still runs at normal
        print(f"[console] priority unchanged ({e.__class__.__name__})")
        return None


def main():
    if no_quick_edit():
        print("[console] QuickEdit off: clicking in this window no longer pauses the camera")
    pr = camera_priority()
    if pr:
        print(f"[console] process priority: {pr.replace('_', ' ')} (cameras first; same class as the AI runner)")
    ap = argparse.ArgumentParser(description="Smart Lab security camera service")
    ap.add_argument("--source", default=os.environ.get("SECURITY_CAMERA_SOURCE", "0"),
                    help="rtsp://user:pass@ip:554/stream2, a webcam number, a video or image file")
    ap.add_argument("--device", default="SECCAM_LAB01", help="device id in the portal")
    ap.add_argument("--name", default="Security camera")
    ap.add_argument("--lab", default="LAB_01")
    ap.add_argument("--portal", default="http://127.0.0.1:8000/api")
    ap.add_argument("--port", type=int, default=5100)
    ap.add_argument("--record-source", default="", help="stream to record (default: the full-resolution stream)")
    ap.add_argument("--recordings", default=os.path.join(HERE, "recordings"), help="folder for recordings")
    ap.add_argument("--record-part-min", type=int, default=60,
                    help="a recording runs until Stop, split into files of this many minutes")
    ap.add_argument("--record-min-free-gb", type=float, default=2.0, help="refuse to record below this free space")
    ap.add_argument("--face-server", default=os.environ.get("FACE_SERVER_URL", "http://127.0.0.1:5000"),
                    help="face server for naming people by face ('' = door names only)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="127.0.0.1 = this laptop only (the portal in Docker still reaches it); "
                         "0.0.0.0 only when the portal runs on another computer")
    # YOLO26s (Ultralytics, AGPL-3.0) when present: same accuracy as YOLOX-S at 640, 3.5x faster
    # (measured on lab frames 2026-10-12); otherwise the YOLOX-S model.
    ap.add_argument("--model", default=os.path.join(HERE, "models", "yolo26s.onnx")
                    if os.path.isfile(os.path.join(HERE, "models", "yolo26s.onnx"))
                    else os.path.join(HERE, "models", "object_detection_yolox_2022nov.onnx"))
    ap.add_argument("--reid", default=os.path.join(HERE, "models", "person_reid_youtu_2021nov.onnx"),
                    help="body re-identification model (optional; colours only without it)")
    ap.add_argument("--size", type=int, default=640, help="detector input (640: finds seated / half-hidden people - measured 2.97 of 3 vs 2.10 at 416 on lab frames, 2026-10-12)")
    ap.add_argument("--conf", type=float, default=0.35)   # 0.45 missed a seated person (0.39); 0.25 doubles boxes - lab frame 2026-10-12
    ap.add_argument("--threads", type=int, default=8, help="CPU threads of 12 (was 4; the face server needs the rest)")
    ap.add_argument("--det-fps", type=float, default=7.0)   # was 5; a pass takes ~95 ms (p95 ~146) since 2026-10-14
    ap.add_argument("--max-width", type=int, default=960)
    ap.add_argument("--peer", type=int, default=int(os.environ.get("PEER_PORT") or 0),
                    help="port of the OTHER camera service in the same lab (0 = none); see crosscam.py")
    ap.add_argument("--demo", default="", help='name-lock test without the portal, e.g. "USER1=Ali,USER2=Sara"; '
                                               'open http://127.0.0.1:<port>/demo')
    args = ap.parse_args()
    if not os.path.isfile(args.model):
        raise SystemExit(f"Model not found: {args.model}\nSee tools/security_vision/README.md (download once).")
    svc = Service(args)
    svc.crosscam.start()
    for target in (svc.poll_config, svc.post_state, svc.analyse, svc.render, svc.identify_faces,
                   svc.watch_view, svc.watch_equipment, svc.watch_zones, svc.keep_identities):
        threading.Thread(target=target, daemon=True).start()
    host = "127.0.0.1" if svc.demo else args.host
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
