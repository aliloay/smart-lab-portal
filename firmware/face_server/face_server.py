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
OpenCV's LBPH recognizer. Chosen deliberately over dlib / face_recognition:
it installs on Windows with one pip command and no C++ compiler, and it is
accurate enough for a handful of known users in consistent lighting. It is
NOT as robust as a modern CNN model - state that plainly in your thesis
rather than overclaiming.

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
import csv
import time
import logging
import datetime
import cv2
import numpy as np
from flask import Flask, request, jsonify

DATASET_DIR = "dataset"
MODEL_PATH  = "lbph_model.yml"
LABELS_PATH = "labels.txt"
LOG_PATH    = "recognition_log.csv"

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


def decode_qr(gray):
    """QR payload in the frame, or None. Fast decoder first, WeChat second."""
    try:
        data, _, _ = qr_detector.detectAndDecode(gray)
        if data:
            return data.strip()
    except Exception as e:
        print(f"[analyze] QR decode error: {e}")
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
_stats = {"t0": time.time(), "frames": 0, "ms": 0.0, "qr": 0, "face": 0}


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


def largest_face(gray):
    """Haar cascade finds WHERE the face is. LBPH then decides WHO it is."""
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


# ---------------------------------------------------------------------------
app = Flask(__name__)
ensure_log()

# Werkzeug prints a line for EVERY request. At several frames a second that is
# hundreds of lines a minute, it hides the results you actually care about,
# and console I/O on Windows is slow enough to measurably delay responses.
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/enroll", methods=["GET", "POST"])
def enroll():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "missing ?name="}), 400

    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400

    face = largest_face(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    if face is None:
        print(f"[enroll] {name}: no face found in frame")
        return jsonify({"status": "no face found - try again"}), 200

    user_dir = os.path.join(DATASET_DIR, name)
    os.makedirs(user_dir, exist_ok=True)
    idx = len(os.listdir(user_dir))
    cv2.imwrite(os.path.join(user_dir, f"{idx}.jpg"), face)

    print(f"[enroll] {name}: sample {idx + 1} saved")
    return jsonify({"status": "saved", "name": name, "samples": idx + 1})


@app.route("/train", methods=["GET", "POST"])
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

    summary = {n: len(os.listdir(os.path.join(DATASET_DIR, n))) for n in names}
    print(f"[train] {len(faces)} images across {names}")
    return jsonify({"status": "trained", "users": summary, "total_images": len(faces)})


@app.route("/recognize", methods=["POST"])
def recognize():
    if not model_trained:
        return jsonify({"error": "model not trained"}), 400

    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400

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
    img = decode_jpeg(request.get_data())
    if img is None:
        return jsonify({"error": "no image received"}), 400

    t0 = time.perf_counter()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- QR ---
    # Decoding from the GRAYSCALE image, not the colour one: the detector
    # converts internally anyway, so handing it one channel instead of three
    # saves that conversion on every frame.
    qr_payload = decode_qr(gray)
    t_qr = time.perf_counter()

    # --- Face ---
    face_name, face_distance = None, None
    if model_trained:
        face = largest_face(gray)
        if face is not None:
            label, distance = recognizer.predict(face)
            face_distance = round(float(distance), 1)
            if distance <= CONFIDENCE_THRESHOLD:
                face_name = label_to_name.get(label)

    t_face = time.perf_counter()

    # Timing is printed only when something was actually found, so the console
    # stays readable. These numbers are worth putting in the thesis: they are
    # the measured per-stage latency of the recognition pipeline.
    total_ms = 1000 * (t_face - t0)
    _stats["frames"] += 1
    _stats["ms"] += total_ms
    _stats["qr"] += bool(qr_payload)
    _stats["face"] += bool(face_name)
    elapsed = time.time() - _stats["t0"]
    if elapsed >= STATS_EVERY_S:
        n = _stats["frames"]
        print(f"[stats] {n / elapsed:.1f} frames/s from camera, "
              f"{_stats['ms'] / n:.0f} ms/frame here, "
              f"QR in {_stats['qr']}, face in {_stats['face']} of {n} frames")
        _stats.update(t0=time.time(), frames=0, ms=0.0, qr=0, face=0)
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


@app.route("/users", methods=["GET"])
def users():
    if not os.path.exists(DATASET_DIR):
        return jsonify({"users": {}})
    return jsonify({"users": {
        n: len(os.listdir(os.path.join(DATASET_DIR, n)))
        for n in sorted(os.listdir(DATASET_DIR))
    }})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_trained": model_trained,
        "known_users": list(label_to_name.values()),
        "threshold": CONFIDENCE_THRESHOLD
    })


if __name__ == "__main__":
    load_model_if_exists()
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
