"""
===========================================================================
SMART LAB - STAGE 2: FACE RECOGNITION SERVER  (runs on your laptop)
===========================================================================

WHY THE LAPTOP AND NOT THE ESP32-CAM
Real face RECOGNITION - telling one person from another - needs more compute
than the ESP32 has. Espressif removed their ML face library for the classic
ESP32 precisely because a single frame took ~20 seconds on this chip. So the
camera captures and the laptop recognizes. Everything stays on your LAN; no
cloud services are involved.

WHAT THIS USES
Default: OpenCV's YuNet detector + SFace embeddings (CNN models from the
OpenCV model zoo, in models/ - see models/README.md). Each enrolled sample
updates its person's template at once, so there is no separate training
step. Fallback: OpenCV's LBPH recognizer (the original choice: one pip
command, no C++ compiler), used when the model files are missing or when
FACE_ENGINE=lbph is set. On this lab's own samples SFace identified 96.2 %
vs 86.8 % for LBPH, both with no wrong person accepted (2 people, 53
samples - small; see firmware/tools/eval_face_models.py).

INSTALL
    pip install flask waitress opencv-python opencv-contrib-python numpy

RUN
    python face_server.py

Then find your laptop's LAN IP with  ipconfig  (IPv4 Address under your
WiFi adapter, likely 192.168.1.x) and put it in the ESP32-CAM sketch.

---------------------------------------------------------------------------
ENDPOINTS

  POST /enroll?name=USER1   body = JPEG   save one training face for USER1
  GET  /train                             (re)build the model from all faces
  POST /recognize           body = JPEG   -> {"name":..,"distance":..,"access":bool}
  POST /identify            body = JPEG   -> {"name","score","second"} (security camera; device key; nothing logged)
  GET  /users                             list enrolled users + sample counts
  GET  /health                            quick status check

---------------------------------------------------------------------------
WORKFLOW

  1. Run this server.
  2. Flash the Stage 2 sketch to the ESP32-CAM.
  3. Enroll USER1: visit  http://<esp32cam-ip>/enroll?name=USER1  about 20
     times with that person's face in frame, moving the head slightly each
     time (angles and expressions make the model far more robust).
  4. Repeat for USER2.
  5. Visit  http://<laptop-ip>:5000/train  once.
  6. The camera then recognizes automatically and prints results to Serial.

Names here MUST match the access-control user names - USER1 / USER2 - so the
face result can later be checked against the RFID/QR identity from step 1.
===========================================================================
"""

import os
import shutil
import re
import csv
import time
import logging
import datetime
import functools
import threading
import json
import hmac
import sys
import cv2
import numpy as np
from flask import Flask, Response, request, jsonify

DATASET_DIR = "dataset"
MODEL_PATH  = "lbph_model.yml"
LABELS_PATH = "labels.txt"
LOG_PATH    = "recognition_log.csv"
# One colour photo per person for the ACCESS GRANTED screen (LCD + tablet).
# Kept automatically from enrollment: the frame with the largest face wins.
# A photo put here BY HAND (USER2.jpg with no USER2.json next to it) is
# never replaced by enrollment.
PORTRAIT_DIR = "portraits"

# LBPH predict() returns a DISTANCE: LOWER means a BETTER match.
# 70 is a reasonable starting point. Tune it with real data - watch the
# distance values printed for correct vs wrong people and set the threshold
# between the two clusters. Worth a table in your thesis.
CONFIDENCE_THRESHOLD = 70.0

FACE_SIZE = (200, 200)   # all training/query faces normalized to this

os.makedirs(DATASET_DIR, exist_ok=True)

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

# FAIL LOUDLY rather than limping. OpenCV 5.0 REMOVED the bundled Haar cascade
# XML files, so CascadeClassifier loads EMPTY and silently detects nothing -
# every enrollment would report "no face found" while appearing to work.
if face_cascade.empty():
    print()
    print("!" * 70)
    print(" FATAL: the face detector could not be loaded.")
    print(f" Expected cascade at: {CASCADE_PATH}")
    print(f" OpenCV version installed: {cv2.__version__}")
    print()
    print(" OpenCV 5.x no longer ships the Haar cascade files. Downgrade:")
    print('     pip install "opencv-python==4.10.0.84" "opencv-contrib-python==4.10.0.84"')
    print("!" * 70)
    print()
    raise SystemExit(1)
recognizer    = cv2.face.LBPHFaceRecognizer_create()
label_to_name = {}
model_trained = False

# ---------------------------------------------------------------------------
# SFace: the default recognizer when its model files are present
# ---------------------------------------------------------------------------
# YuNet finds the face and five landmarks, SFace turns the aligned face into
# a 128-number embedding, and a person is the mean embedding of their
# samples. A match is the cosine similarity to that template.
#
# Measured on this lab's own enrolled samples (firmware/tools/
# eval_face_models.py, leave-one-out, 2 people, 53 samples, 2026-10-02):
#   LBPH  86.8 % identified and accepted, 0 wrong person accepted
#   SFace 96.2 % identified and accepted, 0 wrong person accepted
# "Training" is instant: each enrolled sample updates its person's template
# at once. LBPH keeps being trained alongside, so FACE_ENGINE=lbph (an
# environment variable) switches back without re-enrolling anyone.
MODELS_DIR = "models"
YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
# Aligned colour faces (112x112) saved at enrollment, next to the grey LBPH
# crops in dataset/. Gitignored with it: pictures of people.
SFACE_DATASET_DIR = "dataset_sface"
SFACE_THRESHOLD = 0.363          # cosine; OpenCV model zoo's value for SFace
DETECT_WIDTH = 320               # YuNet runs on a half-size VGA frame

yunet = sface = None
if os.environ.get("FACE_ENGINE", "auto").lower() != "lbph" and \
        os.path.isfile(YUNET_PATH) and os.path.isfile(SFACE_PATH):
    try:
        yunet = cv2.FaceDetectorYN.create(YUNET_PATH, "", (DETECT_WIDTH, 240), 0.6, 0.3, 5000)
        sface = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
    except cv2.error as e:                    # pragma: no cover
        print(f"[startup] SFace unavailable ({e}) - using LBPH")
        yunet = sface = None
ENGINE = "sface" if sface is not None else "lbph"
templates = {}                   # name -> unit-length mean embedding
_feature_cache = {}              # sample path -> (mtime, embedding)


def yunet_face(img):
    """Largest face in a BGR frame as YuNet's 15-value row (full-res coords)."""
    scale = DETECT_WIDTH / img.shape[1]
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) \
        if scale < 1 else img
    if scale >= 1:
        scale = 1.0
    yunet.setInputSize((small.shape[1], small.shape[0]))
    _, faces = yunet.detect(small)
    if faces is None or not len(faces):
        return None
    face = max(faces, key=lambda f: f[2] * f[3]).copy()
    face[:14] /= scale                        # box + 5 landmarks back to full size
    return face


def _unit(v):
    v = v.flatten()
    return v / (np.linalg.norm(v) or 1.0)


def sample_feature(path):
    """Embedding of one stored sample, cached until the file changes."""
    mtime = os.path.getmtime(path)
    hit = _feature_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    if path.startswith(SFACE_DATASET_DIR):
        feat = _unit(sface.feature(img))       # already an aligned 112x112 face
    else:
        # A legacy grey crop (forehead to chin): a margin lets YuNet see the
        # whole face and return landmarks; without them, a plain resize.
        pad = cv2.copyMakeBorder(img, 50, 50, 50, 50, cv2.BORDER_REPLICATE)
        yunet.setInputSize((pad.shape[1], pad.shape[0]))
        _, faces = yunet.detect(pad)
        crop = sface.alignCrop(pad, max(faces, key=lambda f: f[2] * f[3])) \
            if faces is not None and len(faces) else cv2.resize(img, (112, 112))
        feat = _unit(sface.feature(crop))
    _feature_cache[path] = (mtime, feat)
    return feat


def rebuild_templates(only=None):
    """Mean embedding per person from every stored sample. Milliseconds per
    person once cached, so it runs after every enrollment sample."""
    names = set()
    for d in (DATASET_DIR, SFACE_DATASET_DIR):
        if os.path.isdir(d):
            names.update(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))
    for name in sorted(names):
        if only and name not in only:
            continue
        feats = []
        for d in (DATASET_DIR, SFACE_DATASET_DIR):
            folder = os.path.join(d, name)
            if os.path.isdir(folder):
                for fn in os.listdir(folder):
                    f = sample_feature(os.path.join(folder, fn))
                    if f is not None:
                        feats.append(f)
        if feats:
            templates[name] = _unit(np.mean(feats, axis=0))
        else:
            templates.pop(name, None)


def sface_identify(img):
    """(name or None, cosine or None, face found?, YuNet row or None)."""
    face = yunet_face(img)
    if face is None or not templates:
        return None, None, face is not None, face
    q = _unit(sface.feature(sface.alignCrop(img, face)))
    name, score = max(((n, float(np.dot(q, t))) for n, t in templates.items()),
                      key=lambda x: x[1])
    return (name if score >= SFACE_THRESHOLD else None), score, True, face


def sface_distance(score):
    """Reported in the 'distance' field like LBPH (lower = better): 100*(1-cos)."""
    return None if score is None else round(100 * (1 - score), 1)

# OpenCV's built-in QR decoder. This replaces the on-device ESP32QRCodeReader:
# decoding here means the camera never has to switch modes, and a laptop
# decodes QR far more reliably than quirc on an ESP32.
qr_detector = cv2.QRCodeDetector()

# Second decoder: WeChat's, which ships in opencv-contrib (already required
# for cv2.face). Measured on simulated ESP32-CAM frames (VGA, JPEG q12, blur,
# tilt, dim/bright), share of frames decoded, by QR size in the frame:
#
#     QR size      QRCodeDetector   WeChat
#     110 px            1%            33%
#     140 px           15%            90%
#     180 px           69%           100%
#     260 px           97%           100%
#
# i.e. the plain detector only works with the phone held close. WeChat is
# slower on a frame with no QR (~80 ms vs ~8 ms), so it only runs when the
# fast detector has found nothing.
try:
    wechat_qr = cv2.wechat_qrcode_WeChatQRCode()
except Exception as e:                      # pragma: no cover
    wechat_qr = None
    print(f"[startup] WeChat QR decoder unavailable ({e}) - close-range QR only")


def decode_qr_fast(gray):
    """QR payload via cv2.QRCodeDetector (~10 ms), or None."""
    try:
        data, _, _ = qr_detector.detectAndDecode(gray)
        if data:
            return data.strip()
    except Exception as e:
        print(f"[analyze] QR decode error: {e}")
    return None


def decode_qr_wechat(gray):
    """QR payload via the WeChat decoder (~80-150 ms), or None."""
    if wechat_qr is not None:
        try:
            results, _ = wechat_qr.detectAndDecode(gray)
            for r in results:
                if r:
                    return r.strip()
        except Exception as e:
            print(f"[analyze] WeChat QR error: {e}")
    return None


# Rolling numbers printed every STATS_EVERY_S seconds: how many frames the
# camera actually delivers and how long each takes here. If fps is low while
# ms/frame is small, the bottleneck is the camera's WiFi, not this laptop.
STATS_EVERY_S = 10
_stats = {"t0": time.time(), "frames": 0, "ms": 0.0, "qr": 0, "face": 0,
          "cam": 0, "rssi": 0, "cap": 0, "post": 0, "fails0": None, "fails": 0}


def _cam_header(name):
    try:
        return int(request.headers.get(name, ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_log():
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "name", "distance", "access"])


def log_recognition(name, distance, access):
    with open(LOG_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            name, round(float(distance), 1), access
        ])


def load_labels():
    global label_to_name
    label_to_name = {}
    if os.path.exists(LABELS_PATH):
        with open(LABELS_PATH) as f:
            for line in f:
                if "," in line:
                    label, name = line.strip().split(",", 1)
                    label_to_name[int(label)] = name


def save_labels():
    with open(LABELS_PATH, "w") as f:
        for label, name in label_to_name.items():
            f.write(f"{label},{name}\n")


def load_model_if_exists():
    global model_trained
    load_labels()
    if os.path.exists(MODEL_PATH) and label_to_name:
        recognizer.read(MODEL_PATH)
        model_trained = True
        print(f"[startup] Model loaded. Users: {list(label_to_name.values())}")
    else:
        model_trained = False
        print("[startup] No model yet. Enroll faces, then GET /train")


def decode_jpeg(data):
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# Haar detection cost scales with pixel count, so detecting on a half-size
# image is roughly 4x faster. The BOX is then scaled back up and the crop is
# taken from the FULL-RESOLUTION frame, so LBPH still sees every pixel it
# would have before. Speed comes from cheaper searching, not from throwing
# away the detail that recognition depends on.
DETECT_SCALE = 0.5


def largest_face_box(gray):
    """Haar cascade finds WHERE the face is: (x, y, w, h) or None."""
    small = cv2.resize(gray, None, fx=DETECT_SCALE, fy=DETECT_SCALE,
                       interpolation=cv2.INTER_AREA)

    # equalizeHist flattens the illumination differences that LBPH is most
    # sensitive to. It also makes detection more reliable in uneven light,
    # which is exactly the door situation.
    small = cv2.equalizeHist(small)

    found = face_cascade.detectMultiScale(
        small,
        scaleFactor=1.2,      # coarser pyramid: fewer scales to search
        minNeighbors=4,
        minSize=(40, 40),     # 40px here == 80px at full resolution
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    if len(found) == 0:
        return None

    x, y, w, h = sorted(found, key=lambda r: r[2] * r[3], reverse=True)[0]

    inv = 1.0 / DETECT_SCALE
    x, y, w, h = int(x * inv), int(y * inv), int(w * inv), int(h * inv)

    # Clamp to the frame: the scaled-up box can overhang by a pixel or two.
    H, W = gray.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def largest_face(gray):
    """Haar cascade finds WHERE the face is. LBPH then decides WHO it is."""
    box = largest_face_box(gray)
    if box is None:
        return None
    x, y, w, h = box

    # NO equalizeHist here, deliberately.
    #
    # The images already in dataset/ were saved WITHOUT it. LBPH compares
    # histograms, so equalizing the query while the stored samples are
    # unequalized shifts every distance upward - measured at roughly +12,
    # which pushed correct matches from the 40s to the high 60s, right up
    # against the threshold. Equalization stays on the DETECTION image
    # above, where it helps Haar find the face in uneven light and cannot
    # affect the comparison.
    #
    # If the dataset is ever rebuilt from scratch, equalizing BOTH here and
    # at enrollment is the better configuration - but it must be both.
    return cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE)


# The camera keeps two frames in flight, so requests can overlap. OpenCV's
# detectors and the LBPH model are single objects shared by every request
# and are not guaranteed thread-safe, so the image work itself runs one frame
# at a time; only the network transfer overlaps. Analysis takes ~20-120 ms,
# far less than a frame's round trip, so this costs no throughput.
cv_lock = threading.Lock()


def one_at_a_time(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        with cv_lock:
            return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
app = Flask(__name__)
ensure_log()

# Werkzeug prints a line for EVERY request. At several frames a second that is
# hundreds of lines a minute, it hides the results you actually care about,
# and console I/O on Windows is slow enough to measurably delay responses.
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/enroll", methods=["GET", "POST"])
@one_at_a_time
def enroll():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "missing ?name="}), 400
    # The name becomes a folder: allow only a portal label such as USER5.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        return jsonify({"error": "name must be letters/digits only, e.g. USER5"}), 400

    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    box = largest_face_box(gray)
    if box is None:
        print(f"[enroll] {name}: no face found in frame")
        return jsonify({"status": "no face found - try again"}), 200
    x, y, w, h = box
    face = cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE)
    keep_best_portrait(name, img, w * h)

    user_dir = os.path.join(DATASET_DIR, name)
    os.makedirs(user_dir, exist_ok=True)
    idx = len(os.listdir(user_dir))
    cv2.imwrite(os.path.join(user_dir, f"{idx}.jpg"), face)

    if ENGINE == "sface":
        # The aligned colour face for SFace, then this person's template is
        # rebuilt at once: no separate training step.
        row = yunet_face(img)
        if row is not None:
            sdir = os.path.join(SFACE_DATASET_DIR, name)
            os.makedirs(sdir, exist_ok=True)
            cv2.imwrite(os.path.join(sdir, f"{idx}.png"), sface.alignCrop(img, row))
        rebuild_templates({name})

    print(f"[enroll] {name}: sample {idx + 1} saved")
    return jsonify({"status": "saved", "name": name, "samples": idx + 1,
                    "engine": ENGINE})


# ---------------------------------------------------------------------------
# Portraits: the photo on the ACCESS GRANTED screen
# ---------------------------------------------------------------------------
# The master ESP32 fetches the granted person's photo from here, so a newly
# enrolled person appears on the LCD and tablet without reflashing it. Only
# a device with the device key may fetch one: these are photos of people.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
import make_lcd_photo as lcd  # noqa: E402  (same crop as the old header tool)


def _device_key():
    """DEVICE_API_KEY as the portal uses it: environment, then the repo's
    .env, then the same development default as docker-compose.yml."""
    key = os.environ.get("DEVICE_API_KEY")
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env")
    if not key and os.path.isfile(env):
        with open(env, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("DEVICE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or "dev-device-key-change-me"


DEVICE_KEY = _device_key()
_portrait_cache = {}            # name -> (mtime, rgb565 bytes)
_portrait_lock = threading.Lock()


def keep_best_portrait(name, img, face_area):
    """Keep the enrollment frame with the largest (closest, sharpest) face."""
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    jpg = os.path.join(PORTRAIT_DIR, f"{name}.jpg")
    meta = os.path.join(PORTRAIT_DIR, f"{name}.json")
    if os.path.exists(jpg) and not os.path.exists(meta):
        return                                  # chosen by hand: keep it
    best = 0
    if os.path.exists(meta):
        try:
            with open(meta, encoding="utf-8") as f:
                best = json.load(f).get("face_area", 0)
        except (OSError, ValueError):
            best = 0
    if face_area <= best:
        return
    cv2.imwrite(jpg, img)
    with open(meta, "w", encoding="utf-8") as f:
        json.dump({"face_area": int(face_area), "source": "enrollment"}, f)
    print(f"[portrait] {name}: new photo for the ACCESS GRANTED screen")


@app.route("/portrait/<name>.rgb565", methods=["GET"])
def portrait_rgb565(name):
    """160x128 RGB565, little-endian - the LCD's own pixel format."""
    if not hmac.compare_digest(request.headers.get("X-Device-Key", ""), DEVICE_KEY):
        return jsonify({"error": "device key required"}), 403
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        return jsonify({"error": "bad name"}), 400
    path = os.path.join(PORTRAIT_DIR, f"{name}.jpg")
    if not os.path.isfile(path):
        return jsonify({"error": f"no portrait for {name}"}), 404
    mtime = os.path.getmtime(path)
    with _portrait_lock:
        cached = _portrait_cache.get(name)
        if cached is None or cached[0] != mtime:
            # cv2 directly, not lcd.load(): that one exits the process on
            # an unreadable file, which here would take the server down.
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return jsonify({"error": f"unreadable portrait for {name}"}), 500
            pixels = lcd.to_rgb565(lcd.crop_around_face(img))
            cached = (mtime, pixels.astype("<u2").tobytes())
            _portrait_cache[name] = cached
    return Response(cached[1], mimetype="application/octet-stream",
                    headers={"Cache-Control": "no-store"})


@app.route("/train", methods=["GET", "POST"])
@one_at_a_time
def train():
    global model_trained
    names = sorted(os.listdir(DATASET_DIR)) if os.path.exists(DATASET_DIR) else []
    if not names:
        return jsonify({"error": "nothing enrolled yet"}), 400

    faces, labels = [], []
    label_to_name.clear()
    for label, name in enumerate(names):
        label_to_name[label] = name
        user_dir = os.path.join(DATASET_DIR, name)
        for fn in os.listdir(user_dir):
            img = cv2.imread(os.path.join(user_dir, fn), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                faces.append(img)
                labels.append(label)

    if not faces:
        return jsonify({"error": "no usable training images"}), 400

    recognizer.train(faces, np.array(labels))
    recognizer.save(MODEL_PATH)
    save_labels()
    model_trained = True

    if ENGINE == "sface":
        rebuild_templates()

    summary = {n: len(os.listdir(os.path.join(DATASET_DIR, n))) for n in names}
    print(f"[train] {len(faces)} images across {names}")
    return jsonify({"status": "trained", "users": summary, "total_images": len(faces)})


@app.route("/recognize", methods=["POST"])
@one_at_a_time
def recognize():
    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400

    if ENGINE == "sface":
        if not templates:
            return jsonify({"error": "nobody enrolled"}), 400
        name, score, found, _ = sface_identify(img)
        if not found:
            return jsonify({"name": None, "access": False, "reason": "no face in frame"})
        distance = sface_distance(score)
        print(f"[recognize] {name or 'unknown':10s} cosine={score:.3f}  "
              f"{'ACCESS' if name else 'reject'}  (threshold {SFACE_THRESHOLD})")
        log_recognition(name or "unknown", distance, bool(name))
        return jsonify({"name": name or "unknown", "distance": distance,
                        "score": round(score, 3), "access": bool(name)})

    if not model_trained:
        return jsonify({"error": "model not trained"}), 400

    face = largest_face(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    if face is None:
        return jsonify({"name": None, "access": False, "reason": "no face in frame"})

    label, distance = recognizer.predict(face)
    access = distance <= CONFIDENCE_THRESHOLD
    name   = label_to_name.get(label, "unknown") if access else "unknown"

    print(f"[recognize] {name:10s} distance={distance:6.1f}  "
          f"{'ACCESS' if access else 'reject'}  (threshold {CONFIDENCE_THRESHOLD})")
    log_recognition(name, distance, access)

    return jsonify({
        "name": name,
        "distance": round(float(distance), 1),
        "access": bool(access)
    })


@app.route("/identify", methods=["POST"])
@one_at_a_time
def identify():
    """
    Who is this? For the lab's security camera (tools/security_vision): the
    same templates and threshold as the door, but nothing else happens - no
    access result, no line in recognition_log.csv, no tablet preview. Device
    key required: these are pictures of people.

    Returns {"name": "USER1"|null, "score": cosine|null, "second": cosine of
    the next most alike person|null, "face": bool}.
    """
    if not hmac.compare_digest(request.headers.get("X-Device-Key", ""), DEVICE_KEY):
        return jsonify({"error": "device key required"}), 401
    if ENGINE != "sface":
        return jsonify({"error": "identify needs the SFace models"}), 501
    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400
    face = yunet_face(img)
    if face is None or not templates:
        return jsonify({"name": None, "score": None, "second": None, "face": face is not None})
    q = _unit(sface.feature(sface.alignCrop(img, face)))
    scores = sorted(((float(np.dot(q, t)), n) for n, t in templates.items()), reverse=True)
    best, name = scores[0]
    second = scores[1][0] if len(scores) > 1 else None
    return jsonify({"name": name if best >= SFACE_THRESHOLD else None, "score": round(best, 3),
                    "second": None if second is None else round(second, 3), "face": True})


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    THE ENDPOINT THE INTEGRATED SYSTEM USES.

    One JPEG in -> both a QR payload and a face identity out. Doing both from
    the same frame is what removes the need for the camera to switch modes,
    which was the fragile part of the original design.

    Returns:
      {"qr": "USER1"|null, "face": "USER2"|null, "distance": float|null}
    """
    raw = request.get_data()
    img = decode_jpeg(raw)
    if img is None:
        return jsonify({"error": "no image received"}), 400
    publish_frame(raw)        # tablet live view: shown before analysis, no added delay

    # JPEG decoding (above) runs in parallel; the analysis is serialised.
    with cv_lock:
        t0 = time.perf_counter()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # --- QR ---
        # Decoding from the GRAYSCALE image, not the colour one: the detector
        # converts internally anyway, so handing it one channel instead of three
        # saves that conversion on every frame.
        qr_payload = decode_qr_fast(gray)
        t_qr = time.perf_counter()

        # --- Face ---
        face_name, face_distance = None, None
        face = None
        face_row = None
        if ENGINE == "sface":
            name, score, found, face_row = sface_identify(img)
            face = True if found else None     # only "was there a face" is used below
            face_name, face_distance = name, sface_distance(score)
        elif model_trained:
            face = largest_face(gray)
            if face is not None:
                label, distance = recognizer.predict(face)
                face_distance = round(float(distance), 1)
                if distance <= CONFIDENCE_THRESHOLD:
                    face_name = label_to_name.get(label)

        t_face = time.perf_counter()
        # The tablet's live view: where the face is in this frame.
        # A few numbers - the camera does nothing extra.
        set_preview(img.shape, face_row, face is not None, face_name)

        # --- QR, second chance ---
        # The slow WeChat decoder only runs when the fast one found nothing AND
        # there is no face in the frame. A frame showing a face is someone at
        # step 2, not holding up a phone, and skipping WeChat there cut ~120 ms
        # from every face frame. A QR held close in front of a face is still
        # caught by the fast decoder above.
        if qr_payload is None and face is None:
            t_w = time.perf_counter()
            qr_payload = decode_qr_wechat(gray)
            dt = time.perf_counter() - t_w
            t_qr += dt                    # report it as QR time, not face time
            t_face += dt

        # Timing is printed only when something was actually found, so the console
        # stays readable. These numbers are worth putting in the thesis: they are
        # the measured per-stage latency of the recognition pipeline.
        total_ms = 1000 * (t_face - t0)
        _stats["frames"] += 1
        _stats["ms"] += total_ms
        _stats["qr"] += bool(qr_payload)
        _stats["face"] += bool(face_name)
        # The camera's own timing (previous frame), sent as headers by the
        # ESP32-CAM sketch. Absent with older camera firmware.
        rssi = _cam_header("X-Cam-Rssi")
        if rssi is not None:
            _stats["cam"] += 1
            _stats["rssi"] += rssi
            _stats["cap"] += _cam_header("X-Cam-Capture-Ms") or 0
            _stats["post"] += _cam_header("X-Cam-Post-Ms") or 0
            fails = _cam_header("X-Cam-Fails") or 0
            if _stats["fails0"] is None:
                _stats["fails0"] = fails
            if fails < _stats["fails0"]:      # camera rebooted: counter reset
                _stats["fails0"] = fails - _stats["fails"]
            _stats["fails"] = fails - _stats["fails0"]
        elapsed = time.time() - _stats["t0"]
        if elapsed >= STATS_EVERY_S:
            n = _stats["frames"]
            print(f"[stats] {n / elapsed:.1f} frames/s from camera, "
                  f"{_stats['ms'] / n:.0f} ms/frame here, "
                  f"QR in {_stats['qr']}, face in {_stats['face']} of {n} frames")
            c = _stats["cam"]
            if c:
                print(f"        camera: capture {_stats['cap'] // c} ms, "
                      f"upload+reply {_stats['post'] // c} ms, "
                      f"{_stats['fails']} failed uploads, "
                      f"WiFi {_stats['rssi'] // c} dBm")
            _stats.update(t0=time.time(), frames=0, ms=0.0, qr=0, face=0,
                          cam=0, rssi=0, cap=0, post=0, fails0=None, fails=0)
        if total_ms > 500:
            # The camera gives up after 2 s. A frame this slow means the laptop
            # is overloaded - or this console window is paused (see
            # start_face_server.bat).
            print(f"[analyze] SLOW frame: {total_ms:.0f}ms")
        if qr_payload or face_name:
            print(f"[analyze] qr={qr_payload}  face={face_name} (d={face_distance})"
                  f"   qr {1000*(t_qr-t0):.0f}ms  face {1000*(t_face-t_qr):.0f}ms")

        return jsonify({
            "qr": qr_payload,
            "face": face_name,
            "distance": face_distance
        })


# ---------------------------------------------------------------------------
# Tablet live view - the frame the camera ALREADY sent for analysis
# ---------------------------------------------------------------------------
# The tablet shows the latest analysed frame and a hint ("come a little
# closer", "face the camera"...). Nothing is asked of the camera: it keeps
# its own pace and detection is unchanged; this only keeps a reference to
# the last frame. Frames older than PREVIEW_MAX_AGE_S are not served, and
# PREVIEW=off (environment) switches the view off entirely.
#
# /preview.mjpg pushes each frame to the tablet the moment the camera's POST
# arrives (before analysis), so the view runs at the camera's own rate with
# no polling delay. A stream ends by itself when frames stop for
# PREVIEW_MAX_AGE_S, and at most PREVIEW_MAX_STREAMS run at once so viewers
# can never take the server threads the camera needs.
PREVIEW_ON = os.environ.get("PREVIEW", "on").lower() != "off"
PREVIEW_MAX_AGE_S = 2.0
PREVIEW_MAX_STREAMS = 2
_preview = {"jpeg": None, "at": 0.0, "state": {}, "seq": 0, "streams": 0}
_preview_cond = threading.Condition()


def guidance(shape, row, found, name):
    """A short hint from the face box and landmarks detection already found."""
    if not found:
        return {"hint": "Look at the camera", "tone": "idle", "box": None}
    if row is None:                         # LBPH mode: no box kept
        return {"hint": "Recognised - hold still" if name else "Hold still", "tone": "ok", "box": None}
    h, w = shape[:2]
    x, y, bw, bh = (float(v) for v in row[:4])
    box = {"x": x / w, "y": y / h, "w": bw / w, "h": bh / h}
    re_x, re_y, le_x, le_y, nose_x = (float(row[i]) for i in (4, 5, 6, 7, 8))
    eye_dx = le_x - re_x
    size = bw / w
    off = (x + bw / 2) / w - 0.5
    yaw = (nose_x - (re_x + le_x) / 2) / eye_dx if abs(eye_dx) > 1 else 0.0
    roll = abs(np.degrees(np.arctan2(le_y - re_y, eye_dx))) if abs(eye_dx) > 1 else 0.0
    if size < 0.16:
        hint, tone = "Come a little closer", "warn"
    elif size > 0.55:
        hint, tone = "Step back a little", "warn"
    elif abs(off) > 0.2:
        hint, tone = "Center your face in the frame", "warn"
    elif abs(yaw) > 0.28:
        hint, tone = "Face the camera straight", "warn"
    elif min(roll, 180 - roll) > 15:
        hint, tone = "Keep your head level", "warn"
    elif name:
        hint, tone = "Recognised - hold still", "ok"
    else:
        hint, tone = "Hold still", "ok"
    return {"hint": hint, "tone": tone, "box": box}


def publish_frame(raw):
    """Hand the frame to any open stream at once (a reference, no copy)."""
    if not PREVIEW_ON:
        return
    with _preview_cond:
        _preview["jpeg"], _preview["at"] = raw, time.time()
        _preview["seq"] += 1
        _preview_cond.notify_all()


def set_preview(shape, row, found, name):
    """The hint for the frame just analysed."""
    if PREVIEW_ON:
        _preview["state"] = guidance(shape, row, found, name)


def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"   # the tablet page is served by the master
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/preview.jpg", methods=["GET"])
def preview_jpg():
    if not PREVIEW_ON or _preview["jpeg"] is None or time.time() - _preview["at"] > PREVIEW_MAX_AGE_S:
        return _cors(Response(status=204))
    return _cors(Response(_preview["jpeg"], mimetype="image/jpeg"))


@app.route("/preview.mjpg", methods=["GET"])
def preview_mjpg():
    if not PREVIEW_ON:
        return _cors(Response(status=204))
    with _preview_cond:
        if _preview["streams"] >= PREVIEW_MAX_STREAMS:
            return _cors(Response("Too many viewers", status=503))
        _preview["streams"] += 1

    def frames():
        seen = -1
        try:
            while True:
                with _preview_cond:
                    if _preview["seq"] == seen:
                        _preview_cond.wait(timeout=PREVIEW_MAX_AGE_S)
                    if _preview["seq"] == seen or _preview["jpeg"] is None:
                        return                      # camera stopped: end; the tablet reconnects
                    seen, jpeg = _preview["seq"], _preview["jpeg"]
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                       str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
        finally:
            with _preview_cond:
                _preview["streams"] -= 1

    resp = Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    direct_passthrough=True)
    return _cors(resp)


@app.route("/preview/state", methods=["GET"])
def preview_state():
    fresh = PREVIEW_ON and _preview["jpeg"] is not None and time.time() - _preview["at"] <= PREVIEW_MAX_AGE_S
    return _cors(jsonify({"enabled": PREVIEW_ON, "fresh": fresh,
                          **(_preview["state"] if fresh else {"hint": None, "tone": "idle", "box": None})}))


ARCHIVE_DIR = "dataset_archive"


@app.route("/reset", methods=["POST"])
@one_at_a_time
def reset_person():
    """A person's face samples (and grant-screen photo) stop being used: they
    are MOVED to dataset_archive/<name>_<time>/ - never deleted - and the
    templates are rebuilt without them. Then capture new samples as usual."""
    if not hmac.compare_digest(request.headers.get("X-Device-Key", ""), DEVICE_KEY):
        return jsonify({"error": "device key required"}), 403
    name = request.args.get("name", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        return jsonify({"error": "bad name"}), 400
    dest = os.path.join(ARCHIVE_DIR, f"{name}_{time.strftime('%Y%m%d-%H%M%S')}")
    moved = 0
    for src, sub in ((os.path.join(DATASET_DIR, name), "lbph"),
                     (os.path.join(SFACE_DATASET_DIR, name), "sface"),
                     (os.path.join(PORTRAIT_DIR, f"{name}.jpg"), "portrait.jpg")):
        if os.path.exists(src):
            os.makedirs(dest, exist_ok=True)
            shutil.move(src, os.path.join(dest, sub))
            moved += 1
    if ENGINE == "sface":
        rebuild_templates({name})
    print(f"[reset] {name}: samples moved to {dest}" if moved else f"[reset] {name}: nothing saved")
    return jsonify({"status": "reset", "name": name, "archived_to": dest if moved else None})


@app.route("/users", methods=["GET"])
def users():
    # "portraits": who has a grant-screen photo (names only, never the image).
    portraits = sorted(f[:-4] for f in os.listdir(PORTRAIT_DIR)
                       if f.endswith(".jpg")) if os.path.isdir(PORTRAIT_DIR) else []
    if not os.path.exists(DATASET_DIR):
        return jsonify({"users": {}, "portraits": portraits})
    return jsonify({"users": {
        n: len(os.listdir(os.path.join(DATASET_DIR, n)))
        for n in sorted(os.listdir(DATASET_DIR))
    }, "portraits": portraits})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_trained": model_trained,
        "known_users": list(label_to_name.values()),
        "threshold": SFACE_THRESHOLD if ENGINE == "sface" else CONFIDENCE_THRESHOLD,
        "engine": ENGINE,
        "templates": sorted(templates) if ENGINE == "sface" else None
    })


if __name__ == "__main__":
    load_model_if_exists()
    if ENGINE == "sface":
        t0 = time.perf_counter()
        rebuild_templates()
        print(f"[startup] Recognizer: SFace (YuNet + embeddings), threshold "
              f"cosine >= {SFACE_THRESHOLD}. Templates: {sorted(templates)} "
              f"({1000 * (time.perf_counter() - t0):.0f} ms)")
    else:
        print("[startup] Recognizer: LBPH (SFace model files missing or FACE_ENGINE=lbph)")
    print()
    print("=" * 60)
    print(" SMART LAB - FACE RECOGNITION SERVER")
    print("=" * 60)
    print(" Listening on port 5000, all interfaces.")
    print(" Find your LAN IP with 'ipconfig' and put it in the ESP32-CAM sketch.")
    print("=" * 60)
    print()
    # waitress, not Flask's built-in server. The built-in one closes the
    # connection after EVERY response, so the camera had to open a new TCP
    # connection for every frame, several times a second - slow, and on
    # Windows a steady source of refused (-1) and timed-out (-11) frames.
    # waitress keeps one connection open and just streams frames down it.
    try:
        from waitress import serve
    except ImportError:
        print(" (waitress not installed - using Flask's slower built-in server."
              " Fix: pip install waitress)")
        # threaded: one slow frame must never queue behind another.
        app.run(host="0.0.0.0", port=5000, threaded=True)
    else:
        serve(app, host="0.0.0.0", port=5000, threads=8)
