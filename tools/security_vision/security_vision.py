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
import json
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify, request, send_file

from dataset import Collector
from equipwatch import NOT_SEEN_SCANS, EquipmentWatch, Found
from latency import PipelineMetrics, process_load
from recorder import Recorder
import realign
from vision import EQUIPMENT_CLASSES, find_equipment
from vision import PERSON, Appearance, Detector, DoorWatcher, Labeler, Tracker, ZoneWatcher, draw, head_crop, iou
from vision import predicted, red_share

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

    def __init__(self, source: str, max_width: int, metrics: Optional[PipelineMetrics] = None):
        self.source, self.max_width = source, max_width
        self.frame: Optional[np.ndarray] = None
        self.at = 0.0
        self.seq = 0                                  # frames received so far (skips = latest-frame policy)
        self.ok = False
        self.metrics = metrics
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

    def _store(self, frame, read_ms: float = 0.0):
        now = time.time()
        h, w = frame.shape[:2]
        if w > self.max_width:
            frame = cv2.resize(frame, (self.max_width, int(h * self.max_width / w)))
        with self._lock:
            self.frame, self.at, self.ok = frame, now, True
            self.seq += 1
        if self.metrics:
            self.metrics.frame_in(now, read_ms)

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
                r0 = time.perf_counter()
                ok, frame = cap.read()
                read_ms = (time.perf_counter() - r0) * 1000
                if not ok or frame is None:
                    fails += 1
                    time.sleep(0.05)
                    if self.source.lower().endswith((".mp4", ".avi", ".mkv")):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop a test video
                    continue
                fails = 0
                self._store(frame, read_ms)
                if self.source.lower().endswith((".mp4", ".avi", ".mkv")):
                    time.sleep(1 / 15)
            cap.release()
            self.ok = False
            if self.metrics:
                self.metrics.reconnects += 1
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

    def latest_seq(self):
        """(frame, received at, sequence number) - the newest only; older frames are gone."""
        with self._lock:
            return (None if self.frame is None else self.frame.copy()), self.at, self.seq


# --------------------------------------------------------------- service ---
class Service:
    STATE_PERIOD_S = 2.0
    CONFIG_PERIOD_S = 3.0
    EXTRA_PERSON_HOLD_S = 8.0          # more people than entered for this long -> event
    EVENT_COOLDOWN_S = 120.0
    RENDER_FPS = 15                    # pictures drawn per second for the live views
    FACE_EVERY_S = 1.5                 # a face check per unnamed person at most this often
    FACE_MARGIN = 0.05                 # the best face must beat the next person by this (cosine)
    FACE_RECHECK_S = 15.0              # a verified person's face is re-checked this often (swaps)

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
        self.metrics = PipelineMetrics()
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
        self.door_watch = DoorWatcher()      # open / closed from the red door leaf in the door box
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
            named = [{"label": t.label, "name": t.name, "role": t.role, "source": t.source,
                      "entered": t.entered, "verified": t.verified, "face": t.mismatch,
                      "track_id": t.id, "identity_state": t.identity_state,
                      "confidence": t.identity_confidence, "named_by": t.named_by}
                     for t in tracks if t.label]
            try:
                self.http.post(self.portal + "/security/state", timeout=5, json={
                    "device_uid": self.args.device, "fps": self.fps, "people": len(tracks),
                    "named": named, "unknown": len(tracks) - len(named), "zones": zones,
                    "source_ok": self.camera.ok, "door_open": self.door_open,
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
            age_ms = (t0 - at) * 1000
            h, w = frame.shape[:2]
            with self.det_lock:
                d0 = time.perf_counter()
                people = [d.box for d in self.detector.detect(frame) if d.cls == PERSON]
                detect_ms = (time.perf_counter() - d0) * 1000
            k0 = time.perf_counter()
            tracks = self.tracker.update(people, t0, self.appearance.looks(frame, people, t0))
            occupants = self.cfg.get("occupants", [])
            door = self.cfg.get("door")
            door_px = (door["x"] * w, door["y"] * h, door["w"] * w, door["h"] * h) if door else None
            with self.label_lock:
                self.labeler.assign(tracks, occupants, door_px, t0, known=self.cfg.get("known"))
                id_events = list(self.labeler.events)
            self._identity_events(id_events, tracks, occupants)
            track_ms = (time.perf_counter() - k0) * 1000
            z0 = time.perf_counter()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            pnorm = [(b[0] / w, b[1] / h, b[2] / w, b[3] / h) for b in (t.box for t in tracks)]
            states = self.zones.update(self.cfg.get("zones", []), gray, pnorm, t0)
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
            self.check(tracks, occupants, states)
            zones_ms = (time.perf_counter() - z0) * 1000
            self.metrics.analysed(seq, age_ms, detect_ms, track_ms, zones_ms, (time.time() - t0) * 1000)
            times.append(time.time() - t0)
            times = times[-20:]
            self.fps = round(1.0 / max(sum(times) / len(times), period), 1)
            time.sleep(max(0.0, period - (time.time() - t0)))

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
                "skipped": m["analysis"]["skipped_latest_frame_policy"], "reconnects": m["capture"]["reconnects"]}

    def _identity_events(self, events, tracks, occupants):
        """Identity decisions: all kept in a short local log (/identity, the
        evidence panel); a conflict is also an event for staff."""
        for e in events:
            self.identity_log.append({"t": round(time.time(), 2), "kind": e.kind, "track_id": e.track_id,
                                      "label": e.label, "detail": e.detail})
            print(f"[identity] {e.kind} track {e.track_id}: {e.detail}")
            if e.kind == "PERSON_IDENTITY_CONFLICT":
                self.event("PERSON_IDENTITY_CONFLICT", f"Track {e.track_id}: {e.detail}. The name was NOT "
                           "changed - check who this is.", people_seen=len(tracks), people_inside=len(occupants))

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

    def _anchor_path(self) -> str:
        return os.path.join(HERE, "anchors", f"{self.args.device}.npz")

    def _check_view(self):
        """Anchor = the view + boxes as staff last drew them (kept on disk).
        Each check maps the anchor straight to the current view; boxes move
        only when the camera has settled (two looks agree on every corner
        within 1 %) and the match is strong. No chaining, so no drift."""
        frame, at = self.camera.latest()
        zones, door = self.cfg.get("zones", []), self.cfg.get("door")
        if frame is None or time.time() - at > 5 or not (zones or door):
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
            self.equipment_detector = Detector(self.args.model, conf=0.15, size=640)
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
            frame, _ = self.camera.latest()
            if frame is None:
                continue
            now = time.time()
            for tid in [k for k in self.face_asked if all(t.id != k for t in tracks)]:
                del self.face_asked[tid]
            for t in tracks:
                every = self.FACE_RECHECK_S if t.verified else self.FACE_EVERY_S
                if now - self.face_asked.get(t.id, 0.0) < every:
                    continue
                self.face_asked[t.id] = now
                crop = head_crop(frame, t.box)
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
                if name and (second is None or score - second >= self.FACE_MARGIN):
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
                raw = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
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
                                    "box": t.box, "identity_state": t.identity_state,
                                    "confidence": t.identity_confidence, "named_by": t.named_by}
                                   for t in svc.tracks],
                        "zones": [{"id": s.id, "name": s.name, "status": s.status, "score": s.score}
                                  for s in svc.zones.states.values()]})

    @app.get("/metrics")
    def metrics():
        """Measured stage timings (latency.py) + this process's load."""
        if not authorised():
            return Response("device key required", status=401)
        return jsonify({**svc.metrics.summary(), "process": process_load(),
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
    for target in (svc.poll_config, svc.post_state, svc.analyse, svc.render, svc.identify_faces,
                   svc.watch_view, svc.watch_equipment):
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
