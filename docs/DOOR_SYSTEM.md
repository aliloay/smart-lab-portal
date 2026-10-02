# Smart Lab Access Control — How to Run

Full system: RFID **or** QR → fingerprint **or** face → door.

---

## What goes where

| # | Device | Sketch / script | Folder |
|---|--------|-----------------|--------|
| 1 | **Laptop** | `face_server.py` | `firmware\face_server\` |
| 2 | **ESP32-CAM** (AI Thinker) | `ESP32CAM_Vision_FAST.ino` | `firmware\ESP32CAM_Vision_FAST\` |
| 3 | **Master ESP32** (LCD, RFID, fingerprint, relay) | `SmartLab_Master_Portal.ino` | `firmware\SmartLab_Master_Portal\` |

Nothing is wired between the two boards. They talk over WiFi.

---

## Board settings

**ESP32 core (Boards Manager → esp32 by Espressif): `3.3.11`. Do not update to
3.3.12** - with 3.3.12 the ESP32-CAM fails at boot with `frame buffer malloc
failed` / `Camera init failed` (same board, same settings; 3.3.11 works).

**ESP32-CAM**
- Board: `AI Thinker ESP32-CAM`
- PSRAM: `Enabled`
- Partition Scheme: `Huge APP (3MB No OTA/1MB SPIFFS)`
- Upload Speed: `115200`
- IO0 jumper → download position to flash, back to run afterwards, then press RST

**Master ESP32**
- Board: `ESP32 Dev Module`
- Defaults are fine

---

## Launch order — this order matters

### 1. Laptop server

`launch.bat` at the repository root opens it in its own window together with
the portal. To run it on its own, double-click
`firmware\face_server\start_face_server.bat`, or:

```
cd firmware\face_server
python face_server.py
```

It reads `dataset\`, `lbph_model.yml` and `labels.txt` from that folder.

Leave the window open. Expect:

```
 SMART LAB - FACE RECOGNITION SERVER
 Listening on port 5000, all interfaces.
 * Running on http://192.168.1.200:5000
```

If it exits complaining about the face detector, the OpenCV version is wrong:

```
pip install "opencv-python==4.10.0.84" "opencv-contrib-python==4.10.0.84"
```

### 2. ESP32-CAM

Check line 61 points at the laptop:

```cpp
const char *SERVER_IP = "192.168.1.200";
```

Flash, then read Serial at 115200:

```
[INIT] Camera OK: 34567 bytes, 640x480
PUT THIS IP IN THE MASTER SKETCH: 192.168.1.150
```

### 3. Master ESP32

Check line 66 matches the IP the camera just printed:

```cpp
const char *CAMERA_IP = "192.168.1.150";
```

Flash. Expect:

```
[RFID][PASS] MFRC522 communication detected.
[FP][PASS] Fingerprint sensor detected.
[WIFI] Connected. Master IP: 192.168.1.x
                SYSTEM READY
[READY] STEP 1 (identity) : RFID tag/card  OR  QR code
[READY] STEP 2 (biometric): fingerprint    OR  face
```

---

## Test sequence

Run these in order. The last one is the important one.

| # | Action | Expected |
|---|--------|----------|
| 1 | RFID tag → thumb | `HELLO / ALI`, door unlocks |
| 2 | RFID card → index | `HELLO / DR. RAMY`, door unlocks |
| 3 | QR `USER1` → thumb | `HELLO / ALI`, door unlocks |
| 4 | RFID tag → your face | `HELLO / ALI`, door unlocks |
| 5 | QR `USER1` → your face | `HELLO / ALI`, door unlocks |
| 6 | Unknown card | `DENIED / UNKNOWN CARD`, door stays shut |
| 7 | RFID tag → index finger | `DENIED / WRONG FINGER` |
| 8 | **RFID tag (USER1) → Dr. Ramy's photo** | **`DENIED / FACE MISMATCH`** |
| 9 | RFID tag, then wait 20s | `DENIED / FINGER TIMEOUT` |

**Test 8 is the headline result.** It proves the second factor is bound to the
identity from the first — a stolen card plus the thief's own face is refused.
That is the security property worth demonstrating in the defence.

---

## Troubleshooting — both of these happened and both will happen again

### Camera Serial repeats `[ANALYZE] HTTP -1`

The camera cannot open a TCP connection to the laptop. `HTTP -1` is a
connection failure, not a bad request. Check in this order:

1. `ipconfig` on the laptop — if the IPv4 address is no longer `192.168.1.200`,
   the manual IP was lost. Set it back (Wi-Fi > IP assignment > Manual) or update `SERVER_IP` (line 61) in the camera sketch and reflash.
2. `http://192.168.1.200:5000/health` in the laptop's own browser. This goes over
   loopback and bypasses the firewall, so it working proves nothing about the
   network — it only proves the server is alive.
3. Same URL **from a phone on the same WiFi**. If the laptop works and the
   phone hangs, Windows Firewall is blocking inbound port 5000. Fix, in an
   Administrator Command Prompt:

```
netsh advfirewall firewall add rule name="SmartLab Flask 5000" dir=in action=allow protocol=TCP localport=5000
```

Also confirm the WiFi network profile is **Private**, not Public — Windows
applies a separate firewall profile to each, and a router reboot can silently
re-classify the network.

### Master repeats `[CAM] camera unreachable` while the camera still POSTs fine

Outbound works, inbound does not: the camera's own HTTP server has run out of
sockets. `esp_http_server` refuses all new connections once `max_open_sockets`
are in use, silently, with no crash and nothing on Serial. Abandoned master
polls and browser tabs fill the slots within minutes.

Fixed in `startServer()`:

```cpp
config.max_open_sockets = 7;
config.lru_purge_enable = true;    // recycle the oldest socket instead of refusing
```

`lru_purge_enable` is the line that matters. Without it the server degrades from
working to permanently silent, which is a slow and confusing thing to diagnose.
Verify with `http://192.168.1.150/status` in a browser — JSON means healthy.

---

## Two design decisions worth explaining in the thesis

### Freshness windows

`VISION_FRESH_MS = 3500` in the master. Any QR or face result older than 3.5
seconds is discarded. Without it, a QR scanned a minute ago could authorize
whoever happens to be standing at the door now. It is the most
security-critical constant in the integration.

### Graceful degradation

WiFi connects **last** in the master's `setup()`, with a bounded timeout, and
failure is a warning rather than a fatal error. If the camera or the network
is down, RFID + fingerprint keep working exactly as before. The door never
depends on the network being up.

---

## Known limitations — state these rather than hide them

1. **No liveness detection.** A printed photo or a phone screen authenticates
   as that person. This is inherent to LBPH, not a bug in the build. It is
   mitigated structurally: face is only the *second* factor, so an attacker
   needs the physical credential **and** a photo of that specific person.

2. **LBPH, not a CNN.** Chosen because it installs with one pip command and
   works well for a handful of users in consistent lighting. Less robust than
   a modern deep model.

3. **Recognition depends on the laptop.** By design — the classic ESP32 cannot
   run face recognition at usable speed. Espressif disabled their own face
   library on this chip because a single frame took roughly 20 seconds.

4. **Denial buzzer disabled.** Energizing it sags the 12V rail enough to drop
   the relay and release the door. Tested at 3000ms, 500ms, 150ms and 30ms
   with a soft-start ramp; every audible duration popped the door. Fix is a
   470–1000µF capacitor across the 12V rail near the relay module, after
   which `DENY_ALERT_ENABLED` can go back to `true`. Denial feedback is
   currently the red LED (own pin, GPIO15) plus the LCD.

---

## Measured pipeline latency

Printed by the server on every detection, e.g. `qr 15ms  face 9ms`.

| Stage | Measured |
|-------|----------|
| QR decode (laptop) | 7 – 26 ms |
| Face detect + recognize (laptop) | 4 – 17 ms |
| Camera analyze interval | 150 ms |
| Master poll interval | 250 ms |

The laptop contributes roughly 20ms of the round trip. The remaining latency
is camera capture, JPEG encoding and the WiFi link — which is where any
further tuning would have to go, not the server.

---

## Timing constants and why they are what they are

| Constant | Value | Reason |
|----------|-------|--------|
| `ANALYZE_INTERVAL_MS` (camera) | 150 | effectively continuous; limited by round-trip, not a timer |
| `CAMERA_POLL_MS` (master) | 250 | 4 Hz — fast enough that the poll is never the delay |
| `CAMERA_TIMEOUT_MS` (master) | 800 | a stalled camera must not block RFID or fingerprint |
| `VISION_FRESH_MS` (master) | 3500 | security-critical; see Freshness windows below |
| `FINGERPRINT_TIMEOUT_MS` (master) | 20000 | the step-2 window a person actually needs |

Both HTTP clients hold a **persistent connection** (`setReuse(true)` on a
`static` object). Re-opening TCP per request cost more than the image
transfer itself at a weak signal.

---

## Evaluation data already collected

Face recognition distance scores (LBPH — lower is a better match):

| Case | Observed range |
|------|----------------|
| Correct match | 31.2 – 63.9 |
| Unknown face | 79.2 – 149.6 |

Clean separation between 63.9 and 79.2. The threshold of 70 sits in that gap,
so it is empirically justified rather than assumed. No cross-matching was
observed between USER1 and USER2.

`face_server.py` writes every recognition to `recognition_log.csv` with a
timestamp, name, distance and accept/reject — use it to extend this table.

### One measurement worth reporting as a finding

Adding `equalizeHist` to the query face crop — while the stored training
samples had been saved without it — raised correct-match distances by roughly
12 points, pushing USER1 from the 40s into the high 60s and close to the
threshold of 70. Histogram equalization must be applied to the enrollment
images and the query images or to neither; applying it to one side only
biases every comparison. It is now applied solely to the detection pass,
where it helps Haar locate the face in uneven light and cannot affect the
match. This is a concrete illustration of LBPH's sensitivity to illumination
normalization and is worth a paragraph in the thesis.

---

## Users

| Internal name | Display name | RFID UID | Fingerprint |
|---------------|--------------|----------|-------------|
| `USER1` | ALI | `89:52:FF:1F` (tag) | ID 1, thumb |
| `USER2` | DR. RAMY | `F5:77:30:8E` (card) | ID 2, index |

The **internal name** must stay identical in the master sketch, the face
server enrollment, and the QR payloads — that is what lets step 2 be checked
against step 1. The **display name** is cosmetic and safe to change.

### Adding a person (USER3, USER4, …) — no firmware edit

The portal gives every new account the next door identity automatically
(`USER3`, `USER4`, …; numbers are never reused). The number **is** the
fingerprint slot, and the same label is the face name. For that person:

1. **Fingerprint** — portal: **Users & roles → Edit → Fingerprint → Enroll
   fingerprint at the door**. The portal only stores a request; the master
   fetches it (it polls every 2 s, and only while the door is idle), prompts
   the person on the LCD and the tablet — place finger, remove, same finger
   again — and reports each step, shown live in the portal. Success ticks
   "Fingerprint registered" and is audited. A request not taken within 90 s
   expires; one request at a time; the door stays locked and watched (a
   forced door stops enrollment and raises the normal alarm).
   Or, without the portal: Arduino IDE → Serial Monitor on the master
   (115200 baud, line ending *Newline*), door idle, `enroll 5` for USER5.
   Other commands: `enroll 5 force` (overwrite), `delete 5`, `count`.
2. **Face (optional)** — open the camera page `http://192.168.1.150`, type
   `USER5` under *Enroll a face*, press **Capture sample** about 20 times
   with the person in front of the camera, then press **Train**.
3. They book a lab in the portal and show the booking QR. The portal names
   `USER5`, and the master then accepts only fingerprint slot 5 or face
   `USER5`. Anyone else's finger or face is refused as an identity mismatch.

RFID cards are still listed in the sketch (only USER1 and USER2 have one);
new people use the booking QR as step 1. Enrolment blocks the master for up
to ~40 s; do it outside lab hours.

### Face recognizer: SFace by default, LBPH as fallback

The face server uses OpenCV's YuNet + SFace (128-d embeddings, cosine ≥
0.363) when `firmware/face_server/models/*.onnx` are present, else LBPH.
Every enrolled sample updates that person's template at once — no training
step (Train still works and also retrains LBPH, so `FACE_ENGINE=lbph`
switches back without re-enrolling). Replies to the camera are unchanged
(`face`, `distance`; for SFace distance = 100 × (1 − cosine)).

Measured offline on the enrolled samples (leave-one-out, USER1 26 + USER2
27 samples, 2026-10-02, `py firmware/tools/eval_face_models.py`):

| | identified and accepted | wrong person accepted | right person refused | CPU per face |
|---|---|---|---|---|
| LBPH (distance ≤ 70) | 46/53 = 86.8 % | 0 | 6 | 6.1 ms |
| SFace (cosine ≥ 0.363) | 51/53 = 96.2 % | 0 | 1 | 18.8 ms |

Limits: two people, one camera, one session each; the stored samples are
grey crops, so SFace was measured at a disadvantage. Re-measure with more
people before stating it as a general result.

### The photo on ACCESS GRANTED — automatic, no reflash

Face enrollment also keeps the best **colour** capture of each person (the
frame with the largest face) as `firmware/face_server/portraits/USERn.jpg`.
When step 1 names a person, the master fetches that photo from the face
server in a background task (other core), so it is shown on the LCD and the
tablet at ACCESS GRANTED. The door never waits for it:

| Situation | Grant screen shows |
|---|---|
| Photo on the face server | that photo (redrawn if it arrives a moment after the grant) |
| Laptop off / no photo, but the person is in `user_photos.h` | the compiled-in photo |
| Neither | the text screen |

- The face server hands a photo only to a device with the device key
  (`DEVICE_API_KEY`, same as the portal) — these are pictures of people.
  `portraits/` is gitignored for the same reason.
- To use a specific photo instead, put it in `portraits/` as `USERn.jpg` and
  delete `USERn.json`. A photo placed by hand is never replaced by
  enrollment.
- Older enrollments (before this feature) have no colour photo: capture a few
  more samples for that person on the camera page and one is created.

---

## Hardware reference (Master ESP32)

| Function | Pin | Notes |
|----------|-----|-------|
| RFID SS / RST | 5 / 22 | VSPI: SCK 18, MISO 19, MOSI 23 |
| TFT SCK / MOSI | 13 / 2 | CS 25, DC 32, RST 33 |
| Fingerprint | RX 16, TX 17 | 57600 baud |
| Door sensor (MC-38) | 27 | INPUT_PULLUP; LOW = CLOSED |
| Relay | 26 | HIGH = LOCKED, solenoid on NC |
| Green LED | 14 | on at grant |
| Red LED | 15 | own pin — keeps it off the buzzer's supply |
| Buzzer | 21 | currently disabled, see limitations |
